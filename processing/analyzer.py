"""Financial signal counting."""

from __future__ import annotations

from domain.config import (
    BRAZIL_MARKET_KEYWORDS,
    FINANCE_KEYWORDS,
    FOCUSED_TOPIC_KEYWORDS,
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
