"""Entry point: argument parsing and pipeline orchestration."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date
from pathlib import Path
from typing import Optional

from domain.config import DEFAULT_ENRICH_WORKERS
from fetcher.client import CachedHttpClient
from pipeline.collection import collect_candidates, select_candidates_for_enrichment
from pipeline.enrichment import enrich_selected_candidates, load_seen_urls
from fetcher.adapters import build_adapters

LOGGER = logging.getLogger(__name__)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collects news from InfoMoney, Valor and Exame, "
            "selecting approximately 100 articles per week with lower weight on weekends."
        )
    )
    parser.add_argument(
        "--start-date", default="2016-01-01", help="Start date in YYYY-MM-DD format."
    )
    parser.add_argument(
        "--end-date", default="2025-12-31", help="End date in YYYY-MM-DD format."
    )
    parser.add_argument(
        "--output",
        default="data/financial_news_br.jsonl",
        help="Output JSONL file path.",
    )
    parser.add_argument(
        "--cache-dir",
        help="Optional HTTP cache directory for persistent on-disk response reuse.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from an existing JSONL file, skipping already saved URLs.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_ENRICH_WORKERS,
        help=(
            "Number of parallel threads for the enrichment phase. "
            "Default: %(default)s. Use 1 to disable parallelism."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    if end_date < start_date:
        raise ValueError("End date must be greater than or equal to start date.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    client = CachedHttpClient(cache_dir=cache_dir)

    LOGGER.info(
        "Requested interval: %s to %s", start_date.isoformat(), end_date.isoformat()
    )

    # Phase 1: collect candidates from sitemaps
    t0 = time.time()
    adapters = build_adapters(client)
    candidates = collect_candidates(adapters, start_date, end_date)
    t1 = time.time()
    LOGGER.info(
        "Phase 1 (sitemaps): %s unique candidates collected in %.1fs",
        len(candidates),
        t1 - t0,
    )
    if not candidates:
        LOGGER.warning("No candidates found.")
        return 0

    # Phase 2: in-memory pre-filter — no article I/O
    seen_urls = load_seen_urls(output_path) if args.resume else set()
    selected_candidates = select_candidates_for_enrichment(
        candidates,
        seen_urls=seen_urls,
    )
    t2 = time.time()
    LOGGER.info(
        "Phase 2 (pre-filter): %s candidates selected in %.1fs",
        len(selected_candidates),
        t2 - t1,
    )
    if not selected_candidates:
        LOGGER.warning("No promising candidates found for enrichment.")
        return 0

    # Phase 3: enrichment — download and fine-grained filter per article
    enrich_selected_candidates(
        client,
        selected_candidates,
        start_date=start_date,
        end_date=end_date,
        output_path=output_path,
        resume=args.resume,
        workers=args.workers,
    )
    t3 = time.time()
    LOGGER.info("Phase 3 (enrichment): completed in %.1fs", t3 - t2)
    LOGGER.info("Total elapsed time: %.1fs", t3 - t0)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
