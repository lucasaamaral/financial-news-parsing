"""Thread-safe HTTP client with disk-based cache."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from domain.config import DEFAULT_REQUEST_DELAY
from domain.models import FetchPayload

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


class CachedHttpClient:
    """Fetches URLs with a disk cache. Safe for concurrent use across threads."""

    def __init__(
        self, cache_dir: Path, request_delay: float = DEFAULT_REQUEST_DELAY
    ) -> None:
        self.cache_dir = cache_dir
        self.request_delay = request_delay
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # One session per thread avoids sharing a non-thread-safe socket pool.
        self._local = threading.local()
        # Coarse per-key lock prevents duplicate concurrent writes to cache.
        self._key_locks: dict[str, threading.Lock] = {}
        self._key_locks_lock = threading.Lock()

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
            self._local.session = session
        return self._local.session

    def _key(self, url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def _key_lock(self, key: str) -> threading.Lock:
        with self._key_locks_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def _content_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.content"

    def _meta_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.meta.json"

    def get_text(self, url: str, *, allow_redirects: bool = True) -> FetchPayload:
        key = self._key(url)
        content_path = self._content_path(key)
        meta_path = self._meta_path(key)

        # Fast path: cache hit (no lock needed — writes are atomic at OS level).
        if content_path.exists():
            meta = {"final_url": url}
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return FetchPayload(
                text=content_path.read_text(encoding="utf-8"),
                final_url=meta.get("final_url", url),
            )

        # Slow path: fetch from network, then cache under per-key lock.
        with self._key_lock(key):
            # Re-check under lock in case another thread wrote it.
            if content_path.exists():
                meta = {"final_url": url}
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                return FetchPayload(
                    text=content_path.read_text(encoding="utf-8"),
                    final_url=meta.get("final_url", url),
                )
            response = self._session().get(
                url, timeout=90, allow_redirects=allow_redirects
            )
            response.raise_for_status()
            content_path.write_text(response.text, encoding="utf-8")
            meta_path.write_text(
                json.dumps({"final_url": response.url}, ensure_ascii=False),
                encoding="utf-8",
            )
            time.sleep(self.request_delay)
            return FetchPayload(text=response.text, final_url=response.url)
