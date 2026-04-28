"""Phase 3: article enrichment — HTTP fetch, extraction, fine filter, persistence."""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date, timezone
from pathlib import Path
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup

from .collection import group_by_week_and_day
from domain.config import DEFAULT_ENRICH_WORKERS, OUTPUT_FIELDS
from processing.filters import looks_financial_record
from processing.extractor import (
    build_sentiment_text,
    extract_description,
    extract_published_at,
    extract_tags,
    extract_title,
    sanitize_description,
)
from fetcher.client import CachedHttpClient, RobotsTxtBlockedError
from domain.models import ArticleRecord, CandidateArticle, FilterContext
from processing.analyzer import count_financial_signals
from processing.text import get_week_bounds, slug_title_from_url

LOGGER = logging.getLogger(__name__)


def load_seen_urls(output_path: Path) -> set[str]:
    """Return all URLs already persisted in a JSONL output file."""
    seen: set[str] = set()
    if not output_path.exists():
        return seen
    with output_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = data.get("url")
            if url:
                seen.add(url)
    return seen


def fetch_article_record(
    client: CachedHttpClient,
    candidate: CandidateArticle,
    start_date: date,
    end_date: date,
) -> Optional[ArticleRecord]:
    """Download and enrich a single candidate using page metadata only."""
    try:
        payload = client.get_text(candidate.url)
    except RobotsTxtBlockedError as exc:
        LOGGER.info("Skipped by robots.txt: %s", exc)
        return None
    except requests.HTTPError as exc:
        LOGGER.debug("Failed to fetch %s: %s", candidate.url, exc)
        return None

    soup = BeautifulSoup(payload.text, "lxml")
    title = extract_title(soup) or candidate.title or slug_title_from_url(candidate.url)
    published_at = extract_published_at(soup) or candidate.published_at
    if not (start_date <= published_at.date() <= end_date):
        return None
    description = extract_description(soup)
    tags = extract_tags(soup)
    description = sanitize_description(description, title=title)
    if not title:
        return None

    metadata_surface = " ".join(filter(None, [title, description, " ".join(tags)]))
    finance_keyword_hits, brazil_market_keyword_hits = count_financial_signals(
        metadata_surface
    )
    iso = published_at.isocalendar()
    week_start, week_end = get_week_bounds(published_at)
    context = FilterContext(
        section=candidate.section,
        tags=tags,
        finance_keyword_hits=finance_keyword_hits,
        brazil_market_keyword_hits=brazil_market_keyword_hits,
    )
    record = ArticleRecord(
        source=candidate.source,
        url=candidate.url,
        title=title,
        description=description,
        sentiment_text=build_sentiment_text(title, description),
        published_at=published_at.astimezone(timezone.utc).isoformat(),
        week_key=f"{iso.year}-W{iso.week:02d}",
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        tags=tags,
    )
    if not looks_financial_record(record, context):
        return None
    return record


def enrich_selected_candidates(
    client: CachedHttpClient,
    candidates: Iterable[CandidateArticle],
    *,
    start_date: date,
    end_date: date,
    output_path: Path,
    resume: bool,
    workers: int = DEFAULT_ENRICH_WORKERS,
) -> int:
    """Fetch page metadata, filter, and persist approved candidates."""
    grouped = group_by_week_and_day(candidates)
    seen_urls = load_seen_urls(output_path) if resume else set()
    total_candidates = sum(
        len(pool) for week_groups in grouped.values() for pool in week_groups.values()
    )
    LOGGER.info(
        "Starting enrichment of %s candidate articles with %s worker(s)...",
        total_candidates,
        workers,
    )
    selected_count = 0
    output_lock = threading.Lock()
    output_mode = "a" if resume else "w"

    with output_path.open(output_mode, encoding="utf-8") as jsonl_handle:

        def _write_record(record: ArticleRecord) -> None:
            payload = _serialize_record(record)
            with output_lock:
                jsonl_handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
                jsonl_handle.flush()

        for week_key in sorted(grouped):
            week_groups = grouped[week_key]
            week_selected = 0
            week_fetched = 0
            week_pool: list[CandidateArticle] = []

            for weekday in range(7):
                pool = week_groups.get(weekday, [])
                if not pool:
                    continue
                for candidate in pool:
                    if candidate.url in seen_urls:
                        continue
                    week_pool.append(candidate)

            if not week_pool:
                continue

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        fetch_article_record,
                        client,
                        cand,
                        start_date,
                        end_date,
                    ): cand
                    for cand in week_pool
                }
                for future in as_completed(futures):
                    candidate = futures[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        LOGGER.debug("Error fetching %s: %s", candidate.url, exc)
                        record = None
                    week_fetched += 1
                    if record is None:
                        LOGGER.debug("Rejected by fine filter: %s", candidate.url)
                        continue
                    _write_record(record)
                    seen_urls.add(candidate.url)
                    selected_count += 1
                    week_selected += 1

            LOGGER.info(
                "Week %s: %s approved out of %s fetched (total: %s)",
                week_key,
                week_selected,
                week_fetched,
                selected_count,
            )

    LOGGER.info("Records saved to %s", output_path)
    LOGGER.info("Final total: %s", selected_count)
    return selected_count


def _serialize_record(record: ArticleRecord) -> dict[str, object]:
    payload = asdict(record)
    return {field: payload[field] for field in OUTPUT_FIELDS}
