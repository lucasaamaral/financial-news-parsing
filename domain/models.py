"""Domain data models (dataclasses only, no business logic)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class CandidateArticle:
    source: str
    url: str
    published_at: datetime
    title: Optional[str] = None
    section: Optional[str] = None

    @property
    def weekday(self) -> int:
        return self.published_at.weekday()

    @property
    def week_key(self) -> str:
        iso = self.published_at.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"


@dataclass(slots=True)
class ArticleRecord:
    source: str
    url: str
    title: str
    description: Optional[str]
    published_at: str
    week_key: str
    week_start: str
    week_end: str
    weekday: int
    section: Optional[str]
    authors: list[str]
    tags: list[str]
    lead: Optional[str]
    sentiment_text: str


@dataclass(slots=True)
class FilterContext:
    section: Optional[str]
    authors: list[str]
    tags: list[str]
    finance_keyword_hits: int
    brazil_market_keyword_hits: int
    text: Optional[str]


@dataclass(slots=True)
class FetchPayload:
    text: str
    final_url: str
