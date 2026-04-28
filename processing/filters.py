"""Article filtering: gross match, pre-filter, and fine record-level filter."""

from __future__ import annotations

from domain.config import (
    AGGREGATE_RESULTS_MARKERS,
    CORPORATE_ANNOUNCEMENT_TITLE_MARKERS,
    CORPORATE_RESULTS_METRIC_MARKERS,
    CORPORATE_RESULTS_PERIOD_MARKERS,
    DIRECT_BRAZIL_CONTEXT_KEYWORDS,
    FINAL_SECTION_DENYLIST,
    FINANCE_KEYWORDS,
    GENERIC_TITLE_MARKERS,
    FOREIGN_CONTEXT_KEYWORDS,
    GENERIC_TITLE_DENYLIST,
    GROSS_SECTION_ALLOWLIST,
    GROSS_SECTION_DENYLIST,
    RAW_PATH_DENYLIST_MARKERS,
    ROUNDUP_URL_MARKERS,
    STRICT_SECTION_SIGNAL_THRESHOLD,
)
from domain.models import ArticleRecord, CandidateArticle, FilterContext
from processing.analyzer import (
    count_financial_signals,
    count_focused_topic_signals,
)
from processing.text import (
    get_url_path_variants,
    normalize_text,
    slug_title_from_url,
    text_contains_keyword,
)


def is_gross_match(candidate: CandidateArticle) -> bool:
    """Fast section/URL allowlist/denylist check — no I/O required."""
    raw_path, normalized_path = get_url_path_variants(candidate.url)
    if _is_disallowed_raw_path(raw_path):
        return False

    parts = [normalize_text(part) for part in raw_path.split("/") if part]
    allowlist = {
        normalize_text(value)
        for value in GROSS_SECTION_ALLOWLIST.get(candidate.source, set())
    }
    denylist = {
        normalize_text(value)
        for value in GROSS_SECTION_DENYLIST.get(candidate.source, set())
    }
    if any(part in denylist for part in parts):
        if not any(
            text_contains_keyword(normalized_path, keyword)
            for keyword in FINANCE_KEYWORDS
        ):
            return False
    if any(part in allowlist for part in parts):
        return True
    return any(
        text_contains_keyword(normalized_path, keyword) for keyword in FINANCE_KEYWORDS
    )


def is_promising_candidate(candidate: CandidateArticle) -> bool:
    """Signal-based pre-filter using title/slug/section only — no HTTP fetch."""
    normalized_section = normalize_text(candidate.section)
    if normalized_section in FINAL_SECTION_DENYLIST:
        return False

    slug_title = slug_title_from_url(candidate.url)
    headline_context = " ".join(filter(None, [candidate.title, slug_title]))
    normalized_headline = normalize_text(headline_context)
    raw_path, normalized_path = get_url_path_variants(candidate.url)
    if _is_disallowed_raw_path(raw_path):
        return False

    if _looks_like_individual_company_results(
        normalized_headline, normalized_path=normalized_path
    ):
        return False
    if _is_exterior_only_context(f"{normalized_headline} {normalized_path}"):
        return False
    if _has_generic_title_marker(normalized_headline):
        return False

    focused_topic_hits = count_focused_topic_signals(headline_context)
    core_hits, brazil_hits = count_financial_signals(headline_context)
    if focused_topic_hits == 0 and core_hits == 0:
        return False
    if any(marker in normalized_path for marker in ROUNDUP_URL_MARKERS):
        return focused_topic_hits + brazil_hits >= 2

    score = _compute_relevance_score(core_hits, brazil_hits, focused_topic_hits)
    minimum_score = (
        2 if normalized_section not in STRICT_SECTION_SIGNAL_THRESHOLD else 3
    )
    return score >= minimum_score


def looks_financial_record(record: ArticleRecord, context: FilterContext) -> bool:
    """Fine-grained filter applied after page-metadata fetch."""
    normalized_section = normalize_text(context.section)
    if normalized_section in FINAL_SECTION_DENYLIST:
        return False
    raw_path, _ = get_url_path_variants(record.url)
    if _is_disallowed_raw_path(raw_path):
        return False
    if _is_corporate_announcement_record(record):
        return False
    if _is_exterior_only_record(record, context):
        return False
    if _is_roundup_like_record(record, context):
        return False
    if _has_generic_title_marker(normalize_text(record.title)):
        return False
    if not _has_direct_brazil_context(record, context):
        return False

    combined = " ".join(
        filter(
            None,
            [
                record.title,
                record.description,
                " ".join(context.tags),
            ],
        )
    )
    headline_context = " ".join(
        filter(
            None,
            [
                record.title,
                " ".join(context.tags),
            ],
        )
    )
    core_hits = context.finance_keyword_hits
    brazil_hits = context.brazil_market_keyword_hits
    focused_topic_hits = count_focused_topic_signals(combined)
    if focused_topic_hits == 0 and core_hits == 0:
        return False

    score = _compute_relevance_score(core_hits, brazil_hits, focused_topic_hits)
    if normalized_section in STRICT_SECTION_SIGNAL_THRESHOLD:
        headline_topic_hits = count_focused_topic_signals(headline_context)
        if headline_topic_hits == 0 and focused_topic_hits < 2:
            return False
    minimum_score = STRICT_SECTION_SIGNAL_THRESHOLD.get(normalized_section, 2)
    return score >= minimum_score


# ---------------------------------------------------------------------------
# Private helpers — used only by looks_financial_record
# ---------------------------------------------------------------------------


def _is_roundup_like_record(record: ArticleRecord, context: FilterContext) -> bool:
    normalized_title = normalize_text(record.title)
    if normalized_title in GENERIC_TITLE_DENYLIST:
        return True
    _, normalized_path = get_url_path_variants(record.url)
    if not any(marker in normalized_path for marker in ROUNDUP_URL_MARKERS):
        return False
    score = context.finance_keyword_hits + (context.brazil_market_keyword_hits * 2)
    return score < 4


def _is_corporate_announcement_record(record: ArticleRecord) -> bool:
    """Rejects pure corporate-event announcements (dividends, results, debentures)."""
    normalized_headline = normalize_text(record.title)
    _, normalized_path = get_url_path_variants(record.url)
    return _looks_like_individual_company_results(
        normalized_headline, normalized_path=normalized_path
    )


def _has_direct_brazil_context(record: ArticleRecord, context: FilterContext) -> bool:
    headline_context = " ".join(
        filter(
            None,
            [
                record.title,
                record.description,
                " ".join(context.tags),
            ],
        )
    )
    return _has_brazil_market_context(normalize_text(headline_context))


def _is_exterior_only_record(record: ArticleRecord, context: FilterContext) -> bool:
    headline_context = " ".join(
        filter(
            None,
            [
                record.title,
                record.description,
                " ".join(context.tags),
            ],
        )
    )
    return _is_exterior_only_context(normalize_text(headline_context))


def _has_brazil_market_context(normalized_text: str) -> bool:
    if any(
        text_contains_keyword(normalized_text, keyword)
        for keyword in DIRECT_BRAZIL_CONTEXT_KEYWORDS
    ):
        return True
    return text_contains_keyword(normalized_text, "dolar") and "r$" in normalized_text


def _is_exterior_only_context(normalized_text: str) -> bool:
    return any(
        text_contains_keyword(normalized_text, keyword)
        for keyword in FOREIGN_CONTEXT_KEYWORDS
    ) and not _has_brazil_market_context(normalized_text)


def _is_editorial_url(raw_path: str) -> bool:
    return (
        "/post/" in raw_path
        or "/coluna/" in raw_path
        or "/minhas-financas/" in raw_path
    )


def _is_disallowed_raw_path(raw_path: str) -> bool:
    return any(marker in raw_path for marker in RAW_PATH_DENYLIST_MARKERS)


def _has_generic_title_marker(normalized_title: str) -> bool:
    return any(
        text_contains_keyword(normalized_title, marker)
        for marker in GENERIC_TITLE_MARKERS
    )


def _compute_relevance_score(
    core_hits: int,
    brazil_hits: int,
    focused_topic_hits: int,
) -> int:
    return core_hits + (brazil_hits * 2) + focused_topic_hits


def _looks_like_individual_company_results(
    normalized_text: str, *, normalized_path: str = ""
) -> bool:
    combined = f"{normalized_text} {normalized_path}".strip()
    if any(
        text_contains_keyword(combined, marker)
        for marker in CORPORATE_ANNOUNCEMENT_TITLE_MARKERS
    ):
        return True
    if any(
        text_contains_keyword(normalized_text, marker)
        for marker in AGGREGATE_RESULTS_MARKERS
    ):
        return False
    has_metric = any(
        text_contains_keyword(normalized_text, marker)
        for marker in CORPORATE_RESULTS_METRIC_MARKERS
    )
    has_period = any(
        text_contains_keyword(normalized_text, marker)
        for marker in CORPORATE_RESULTS_PERIOD_MARKERS
    )
    return has_metric and has_period
