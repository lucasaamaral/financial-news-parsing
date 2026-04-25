"""Article filtering: gross match, pre-filter, and fine record-level filter."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from domain.config import (
    ADVISORY_SECTIONS,
    AGGREGATE_RESULTS_MARKERS,
    CORPORATE_ANNOUNCEMENT_TITLE_MARKERS,
    CORPORATE_RESULTS_METRIC_MARKERS,
    CORPORATE_RESULTS_PERIOD_MARKERS,
    DIRECT_BRAZIL_CONTEXT_KEYWORDS,
    EDITORIAL_LEAD_MARKERS,
    EDITORIAL_SECTIONS,
    EDITORIAL_TITLE_MARKERS,
    FINAL_SECTION_DENYLIST,
    FINANCE_KEYWORDS,
    FOREIGN_CONTEXT_KEYWORDS,
    GENERIC_TITLE_DENYLIST,
    GROSS_SECTION_ALLOWLIST,
    GROSS_SECTION_DENYLIST,
    HIGH_SCRUTINY_SECTIONS,
    ROUNDUP_URL_MARKERS,
    SPONSORED_AUTHOR_MARKERS,
    SPONSORED_TEXT_MARKERS,
    STRICT_SECTION_SIGNAL_THRESHOLD,
)
from domain.models import ArticleRecord, CandidateArticle, FilterContext
from processing.analyzer import (
    count_clear_strong_finance_signals,
    count_directional_signals,
    count_financial_signals,
    count_focused_topic_signals,
)
from processing.text import normalize_text, slug_title_from_url, text_contains_keyword


def is_gross_match(candidate: CandidateArticle) -> bool:
    """Fast section/URL allowlist/denylist check — no I/O required."""
    normalized_path = normalize_text(unquote(urlparse(candidate.url).path))
    parts = [
        normalize_text(part) for part in urlparse(candidate.url).path.split("/") if part
    ]
    allowlist = GROSS_SECTION_ALLOWLIST.get(candidate.source, set())
    denylist = GROSS_SECTION_DENYLIST.get(candidate.source, set())
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
    headline_context = " ".join(
        filter(None, [candidate.title, slug_title, candidate.section])
    )
    normalized_headline = normalize_text(headline_context)
    normalized_path = normalize_text(unquote(urlparse(candidate.url).path))

    if _looks_like_individual_company_results(
        normalized_headline, normalized_path=normalized_path
    ):
        return False
    if _is_exterior_only_context(f"{normalized_headline} {normalized_path}"):
        return False

    if normalized_section in EDITORIAL_SECTIONS and any(
        marker in normalized_headline for marker in EDITORIAL_TITLE_MARKERS
    ):
        return False

    focused_topic_hits = count_focused_topic_signals(headline_context)
    if focused_topic_hits == 0:
        return False

    if any(marker in normalized_path for marker in ROUNDUP_URL_MARKERS):
        if focused_topic_hits < 2:
            return False

    core_hits, brazil_hits = count_financial_signals(headline_context)
    directional_hits = count_directional_signals(headline_context)
    clear_strong_finance_hits = count_clear_strong_finance_signals(headline_context)

    if (
        directional_hits == 0
        and normalized_section in HIGH_SCRUTINY_SECTIONS
        and focused_topic_hits < 2
    ):
        return False
    if clear_strong_finance_hits == 0 and brazil_hits == 0:
        return False

    score = (
        core_hits
        + (brazil_hits * 2)
        + focused_topic_hits
        + directional_hits
    )
    minimum_score = max(
        2,
        STRICT_SECTION_SIGNAL_THRESHOLD.get(normalized_section, 2) - 2,
    )
    return score >= minimum_score


def looks_financial_record(record: ArticleRecord, context: FilterContext) -> bool:
    """Fine-grained filter applied after full article fetch."""
    normalized_section = normalize_text(context.section)
    if normalized_section in FINAL_SECTION_DENYLIST:
        return False
    if _is_sponsored_record(record, context):
        return False
    if _is_editorial_corporate_record(record, context):
        return False
    if _is_corporate_announcement_record(record):
        return False
    if _is_exterior_only_record(record, context):
        return False
    if _is_roundup_like_record(record, context):
        return False
    if not _has_direct_brazil_context(record, context):
        return False

    combined = " ".join(
        filter(
            None,
            [
                record.title,
                record.description,
                record.lead,
                context.text,
                " ".join(context.tags),
            ],
        )
    )
    headline_context = " ".join(
        filter(
            None,
            [
                record.title,
                record.lead,
                " ".join(context.tags),
            ],
        )
    )
    core_hits, brazil_hits = count_financial_signals(combined)
    focused_topic_hits = count_focused_topic_signals(combined)
    headline_topic_hits = count_focused_topic_signals(headline_context)
    directional_hits = count_directional_signals(headline_context)
    clear_strong_finance_hits = count_clear_strong_finance_signals(combined)

    if focused_topic_hits == 0:
        return False
    if headline_topic_hits == 0:
        if normalized_section not in ADVISORY_SECTIONS or focused_topic_hits < 2:
            return False
    if directional_hits == 0:
        return False
    if clear_strong_finance_hits == 0:
        return False

    score = core_hits + (brazil_hits * 2)
    if (
        normalized_section in STRICT_SECTION_SIGNAL_THRESHOLD
        and clear_strong_finance_hits < 2
    ):
        return False
    if normalized_section in HIGH_SCRUTINY_SECTIONS:
        if headline_topic_hits < 2 and focused_topic_hits < 3:
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
    normalized_path = normalize_text(urlparse(record.url).path)
    if not any(marker in normalized_path for marker in ROUNDUP_URL_MARKERS):
        return False
    score = (
        context.finance_keyword_hits
        + (context.brazil_market_keyword_hits * 2)
    )
    return score < 4


def _is_sponsored_record(record: ArticleRecord, context: FilterContext) -> bool:
    if any(
        marker in normalize_text(author)
        for author in context.authors
        for marker in SPONSORED_AUTHOR_MARKERS
    ):
        return True
    fields = [record.title, record.description, record.lead, context.text]
    return any(
        marker in normalize_text(value)
        for value in fields
        if value
        for marker in SPONSORED_TEXT_MARKERS
    )


def _is_corporate_announcement_record(record: ArticleRecord) -> bool:
    """Rejects pure corporate-event announcements (dividends, results, debentures)."""
    normalized_headline = normalize_text(record.title)
    normalized_path = normalize_text(urlparse(record.url).path)
    return _looks_like_individual_company_results(
        normalized_headline, normalized_path=normalized_path
    )


def _is_editorial_corporate_record(
    record: ArticleRecord, context: FilterContext
) -> bool:
    normalized_section = normalize_text(context.section)
    if normalized_section not in EDITORIAL_SECTIONS:
        return False
    title_fields = [record.title, record.description]
    if any(
        marker in normalize_text(value)
        for value in title_fields
        if value
        for marker in EDITORIAL_TITLE_MARKERS
    ):
        return True
    lead = normalize_text(record.lead)
    return any(marker in lead for marker in EDITORIAL_LEAD_MARKERS)


def _has_direct_brazil_context(record: ArticleRecord, context: FilterContext) -> bool:
    headline_context = " ".join(
        filter(
            None,
            [
                record.title,
                record.lead,
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
                record.lead,
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
