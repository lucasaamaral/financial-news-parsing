"""Financial signal counting."""

from __future__ import annotations

from domain.config import (
    AMBIGUOUS_STRONG_FINANCE_KEYWORDS,
    BRAZIL_MARKET_KEYWORDS,
    DIRECTIONAL_SIGNAL_KEYWORDS,
    FINANCE_KEYWORDS,
    FOCUSED_TOPIC_KEYWORDS,
    STRONG_FINANCE_KEYWORDS,
)
from .text import normalize_text, text_contains_keyword


def count_financial_signals(text: str) -> tuple[int, int]:
    normalized = normalize_text(text)
    core_hits = sum(
        1 for keyword in FINANCE_KEYWORDS if text_contains_keyword(normalized, keyword)
    )
    brazil_hits = sum(
        1
        for keyword in BRAZIL_MARKET_KEYWORDS
        if text_contains_keyword(normalized, keyword)
    )
    return core_hits, brazil_hits


def count_focused_topic_signals(text: str) -> int:
    normalized = normalize_text(text)
    return sum(
        1
        for keyword in FOCUSED_TOPIC_KEYWORDS
        if text_contains_keyword(normalized, keyword)
    )


def count_directional_signals(text: str) -> int:
    normalized = normalize_text(text)
    return sum(
        1
        for keyword in DIRECTIONAL_SIGNAL_KEYWORDS
        if text_contains_keyword(normalized, keyword)
    )


def count_clear_strong_finance_signals(text: str) -> int:
    normalized = normalize_text(text)
    return sum(
        1
        for keyword in STRONG_FINANCE_KEYWORDS
        if keyword not in AMBIGUOUS_STRONG_FINANCE_KEYWORDS
        and text_contains_keyword(normalized, keyword)
    )
