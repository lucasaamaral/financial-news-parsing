"""Phase 1 & 2 of the pipeline: sitemap crawl and in-memory pre-filter."""

from __future__ import annotations

import logging
import random
from collections import defaultdict, deque
from datetime import date
from typing import Iterable, Iterator, Optional

import requests

from fetcher.adapters import BaseAdapter
from domain.config import (
    DEFAULT_ATTEMPT_MULTIPLIER,
    DEFAULT_RANDOM_SEED,
    SOURCE_PRIORITY,
)
from processing.filters import is_promising_candidate
from domain.models import CandidateArticle

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 1 – candidate collection from sitemaps
# ---------------------------------------------------------------------------


def collect_candidates(
    adapters: list[BaseAdapter],
    start_date: date,
    end_date: date,
) -> list[CandidateArticle]:
    collected: list[CandidateArticle] = []
    for adapter in adapters:
        LOGGER.info("Collecting metadata from %s", adapter.source)
        count = 0
        oldest = None
        newest = None
        try:
            for candidate in adapter.iter_candidates(start_date, end_date):
                collected.append(candidate)
                count += 1
                oldest = (
                    candidate.published_at
                    if oldest is None
                    else min(oldest, candidate.published_at)
                )
                newest = (
                    candidate.published_at
                    if newest is None
                    else max(newest, candidate.published_at)
                )
        except requests.RequestException as exc:
            LOGGER.warning("%s is currently unavailable: %s", adapter.source, exc)
            continue
        if count:
            LOGGER.info(
                "%s: %s entries between %s and %s",
                adapter.source,
                count,
                oldest.date().isoformat() if oldest else "-",
                newest.date().isoformat() if newest else "-",
            )
        else:
            LOGGER.info("%s: no entries in range", adapter.source)

    unique = _dedupe_candidates(collected)
    unique.sort(key=lambda item: item.published_at)
    return unique


# ---------------------------------------------------------------------------
# Phase 2 – in-memory pre-filter and quota selection
# ---------------------------------------------------------------------------


def select_candidates_for_enrichment(
    candidates: Iterable[CandidateArticle],
    *,
    seen_urls: Optional[set[str]] = None,
) -> list[CandidateArticle]:
    grouped = _group_by_week_and_day(candidates)
    selected_urls = set(seen_urls or ())
    selected_candidates: list[CandidateArticle] = []

    for week_key in sorted(grouped):
        week_groups = grouped[week_key]
        week_pool_size = 0
        week_pre_filter_rejected = 0
        for weekday in range(7):
            pool = week_groups.get(weekday, [])
            if not pool:
                continue
            ordered = _order_candidates_for_day(
                pool, seed=DEFAULT_RANDOM_SEED + weekday
            )
            for candidate in ordered:
                if candidate.url in selected_urls:
                    continue
                week_pool_size += 1
                if not is_promising_candidate(candidate):
                    week_pre_filter_rejected += 1
                    continue
                selected_candidates.append(candidate)
                selected_urls.add(candidate.url)
        LOGGER.info(
            "Week %s: %s/%s candidates passed pre-filter",
            week_key,
            week_pool_size - week_pre_filter_rejected,
            week_pool_size,
        )

    return selected_candidates


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dedupe_candidates(
    candidates: Iterable[CandidateArticle],
) -> list[CandidateArticle]:
    best_by_url: dict[str, CandidateArticle] = {}
    for candidate in candidates:
        existing = best_by_url.get(candidate.url)
        if existing is None or candidate.published_at > existing.published_at:
            best_by_url[candidate.url] = candidate
    return list(best_by_url.values())


def _group_by_week_and_day(
    candidates: Iterable[CandidateArticle],
) -> dict[str, dict[int, list[CandidateArticle]]]:
    grouped: dict[str, dict[int, list[CandidateArticle]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for candidate in candidates:
        grouped[candidate.week_key][candidate.weekday].append(candidate)
    return grouped


def _order_candidates_for_day(
    candidates: list[CandidateArticle], seed: int
) -> list[CandidateArticle]:
    by_source: dict[str, deque[CandidateArticle]] = defaultdict(deque)
    randomizer = random.Random(seed)
    grouped: dict[str, list[CandidateArticle]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.source].append(candidate)

    for source, items in grouped.items():
        items.sort(key=lambda item: item.published_at)
        randomizer.shuffle(items)
        by_source[source] = deque(items)

    ordered_sources = sorted(
        grouped, key=lambda source: (SOURCE_PRIORITY.get(source, 99), source)
    )
    ordered_candidates: list[CandidateArticle] = []
    while ordered_sources:
        next_round: list[str] = []
        for source in ordered_sources:
            queue = by_source[source]
            if queue:
                ordered_candidates.append(queue.popleft())
            if queue:
                next_round.append(source)
        ordered_sources = next_round
    return ordered_candidates
