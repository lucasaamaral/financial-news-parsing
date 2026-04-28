"""Thread-safe HTTP client with disk-based cache."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from domain.config import (
    DEFAULT_MAX_CONCURRENT_REQUESTS_PER_ORIGIN,
    DEFAULT_REQUEST_DELAY,
)
from domain.models import FetchPayload

_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
_DEFAULT_USER_AGENT = "FinancialNewsResearchBot/1.0"
_MAX_REDIRECTS = 10


class RobotsTxtBlockedError(requests.HTTPError):
    """Raised when a URL is disallowed by the current robots.txt policy."""


@dataclass(slots=True, frozen=True)
class _RobotsPolicy:
    parser: RobotFileParser
    minimum_delay: float
    max_concurrent_requests: int


class CachedHttpClient:
    """Fetches URLs with optional disk cache. Safe for concurrent use across threads."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        request_delay: float = DEFAULT_REQUEST_DELAY,
        max_concurrent_requests_per_origin: int = (
            DEFAULT_MAX_CONCURRENT_REQUESTS_PER_ORIGIN
        ),
        user_agent: str = _DEFAULT_USER_AGENT,
    ) -> None:
        self.cache_dir = cache_dir
        self.request_delay = request_delay
        self.max_concurrent_requests_per_origin = max_concurrent_requests_per_origin
        self.user_agent = user_agent
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        # One session per thread avoids sharing a non-thread-safe socket pool.
        self._local = threading.local()
        # Coarse per-key lock prevents duplicate concurrent writes to cache.
        self._key_locks: dict[str, threading.Lock] = {}
        self._key_locks_lock = threading.Lock()
        self._origin_locks: dict[str, threading.Lock] = {}
        self._origin_locks_lock = threading.Lock()
        self._origin_semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._origin_semaphore_limits: dict[str, int] = {}
        self._origin_semaphores_lock = threading.Lock()
        self._origin_next_request_at: dict[str, float] = {}
        self._robots_policies: dict[str, _RobotsPolicy] = {}
        self._robots_lock = threading.Lock()

    def _session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            session = requests.Session()
            retries = Retry(
                total=4,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET",),
            )
            session.mount("https://", HTTPAdapter(max_retries=retries))
            session.mount("http://", HTTPAdapter(max_retries=retries))
            session.headers.update(_DEFAULT_HEADERS)
            session.headers["User-Agent"] = self.user_agent
            self._local.session = session
        return self._local.session

    def _key(self, url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def _key_lock(self, key: str) -> threading.Lock:
        with self._key_locks_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def _origin(self, url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"

    def _origin_lock(self, origin: str) -> threading.Lock:
        with self._origin_locks_lock:
            if origin not in self._origin_locks:
                self._origin_locks[origin] = threading.Lock()
            return self._origin_locks[origin]

    def _origin_semaphore(
        self, origin: str, max_concurrent_requests: int
    ) -> threading.BoundedSemaphore:
        with self._origin_semaphores_lock:
            semaphore = self._origin_semaphores.get(origin)
            if semaphore is None:
                semaphore = threading.BoundedSemaphore(max_concurrent_requests)
                self._origin_semaphores[origin] = semaphore
                self._origin_semaphore_limits[origin] = max_concurrent_requests
                return semaphore
            expected_limit = self._origin_semaphore_limits[origin]
            if expected_limit != max_concurrent_requests:
                raise RuntimeError(
                    "Origin concurrency changed after initialization for "
                    f"{origin}: {expected_limit} -> {max_concurrent_requests}"
                )
            return semaphore

    def _content_path(self, key: str) -> Path:
        if self.cache_dir is None:
            raise RuntimeError("Disk cache is disabled.")
        return self.cache_dir / f"{key}.content"

    def _meta_path(self, key: str) -> Path:
        if self.cache_dir is None:
            raise RuntimeError("Disk cache is disabled.")
        return self.cache_dir / f"{key}.meta.json"

    def _cached_payload(
        self,
        content_path: Path,
        meta_path: Path,
        requested_url: str,
    ) -> FetchPayload:
        meta = {"final_url": requested_url}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        final_url = meta.get("final_url", requested_url)
        self._ensure_allowed(final_url)
        return FetchPayload(
            text=content_path.read_text(encoding="utf-8"),
            final_url=final_url,
        )

    def _wait_for_origin_slot(self, origin: str, minimum_delay: float) -> None:
        next_request_at = self._origin_next_request_at.get(origin, 0.0)
        now = time.monotonic()
        if next_request_at > now:
            time.sleep(next_request_at - now)

    def _mark_origin_request(self, origin: str, minimum_delay: float) -> None:
        self._origin_next_request_at[origin] = time.monotonic() + minimum_delay

    def _fetch_robots_policy(self, origin: str) -> _RobotsPolicy:
        robots_url = f"{origin}/robots.txt"
        with self._origin_lock(origin):
            self._wait_for_origin_slot(origin, self.request_delay)
            response = self._session().get(robots_url, timeout=30, allow_redirects=True)
            self._mark_origin_request(origin, self.request_delay)

        if response.status_code == 404:
            parser = RobotFileParser()
            parser.parse(["User-agent: *", "Allow: /"])
            return _RobotsPolicy(
                parser=parser,
                minimum_delay=self.request_delay,
                max_concurrent_requests=self.max_concurrent_requests_per_origin,
            )

        response.raise_for_status()
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())

        crawl_delay = parser.crawl_delay(self.user_agent)
        if crawl_delay is None:
            crawl_delay = parser.crawl_delay("*")

        request_rate = parser.request_rate(self.user_agent)
        if request_rate is None:
            request_rate = parser.request_rate("*")

        minimum_delay = self.request_delay
        max_concurrent_requests = self.max_concurrent_requests_per_origin
        if crawl_delay is not None:
            minimum_delay = max(minimum_delay, float(crawl_delay))
            max_concurrent_requests = 1
        elif request_rate is not None and request_rate.requests and request_rate.seconds:
            minimum_delay = max(
                minimum_delay,
                request_rate.seconds / request_rate.requests,
            )
            max_concurrent_requests = 1

        return _RobotsPolicy(
            parser=parser,
            minimum_delay=minimum_delay,
            max_concurrent_requests=max_concurrent_requests,
        )

    def _robots_policy(self, url: str) -> _RobotsPolicy:
        origin = self._origin(url)
        with self._robots_lock:
            cached = self._robots_policies.get(origin)
        if cached is not None:
            return cached

        policy = self._fetch_robots_policy(origin)
        with self._robots_lock:
            existing = self._robots_policies.setdefault(origin, policy)
        return existing

    def can_fetch(self, url: str) -> bool:
        policy = self._robots_policy(url)
        return policy.parser.can_fetch(self.user_agent, url)

    def _ensure_allowed(self, url: str) -> None:
        if self.can_fetch(url):
            return
        raise RobotsTxtBlockedError(
            f"Blocked by robots.txt for {self.user_agent}: {url}"
        )

    def _fetch_uncached(
        self, url: str, *, allow_redirects: bool = True
    ) -> FetchPayload:
        current_url = url
        redirect_count = 0

        while True:
            self._ensure_allowed(current_url)
            policy = self._robots_policy(current_url)
            origin = self._origin(current_url)
            semaphore = self._origin_semaphore(origin, policy.max_concurrent_requests)
            with semaphore:
                with self._origin_lock(origin):
                    self._wait_for_origin_slot(origin, policy.minimum_delay)
                    self._mark_origin_request(origin, policy.minimum_delay)
                response = self._session().get(
                    current_url,
                    timeout=90,
                    allow_redirects=False,
                )

            if allow_redirects and response.is_redirect:
                location = response.headers.get("Location")
                if not location:
                    response.raise_for_status()
                redirect_count += 1
                if redirect_count > _MAX_REDIRECTS:
                    raise requests.TooManyRedirects(
                        f"Too many redirects while fetching {url}"
                    )
                current_url = urljoin(current_url, location)
                continue

            response.raise_for_status()
            return FetchPayload(text=response.text, final_url=current_url)

    def get_text(self, url: str, *, allow_redirects: bool = True) -> FetchPayload:
        self._ensure_allowed(url)
        if self.cache_dir is None:
            return self._fetch_uncached(url, allow_redirects=allow_redirects)
        key = self._key(url)
        content_path = self._content_path(key)
        meta_path = self._meta_path(key)

        # Fast path: cache hit (no lock needed — writes are atomic at OS level).
        if content_path.exists():
            return self._cached_payload(content_path, meta_path, url)

        # Slow path: fetch from network, then cache under per-key lock.
        with self._key_lock(key):
            # Re-check under lock in case another thread wrote it.
            if content_path.exists():
                return self._cached_payload(content_path, meta_path, url)
            payload = self._fetch_uncached(url, allow_redirects=allow_redirects)
            content_path.write_text(payload.text, encoding="utf-8")
            meta_path.write_text(
                json.dumps({"final_url": payload.final_url}, ensure_ascii=False),
                encoding="utf-8",
            )
            return payload
