"""General-purpose text and date utilities with no domain dependencies."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Iterable, Optional
from urllib.parse import unquote, urlparse

from dateutil import parser as dateparser


def parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = dateparser.parse(value)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return clean_space(ascii_only.lower())


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def text_contains_keyword(normalized_text: str, keyword: str) -> bool:
    escaped = re.escape(normalize_text(keyword)).replace(r"\ ", r"\s+")
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def slug_title_from_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"-\d+$", "", slug)
    slug = unquote(slug)
    slug = slug.replace("-", " ")
    return clean_space(slug)


def extract_section(url: str) -> Optional[str]:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if not parts:
        return None
    return parts[0]


def get_week_bounds(moment: datetime) -> tuple[date, date]:
    iso_year, iso_week, _ = moment.isocalendar()
    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    week_end = date.fromisocalendar(iso_year, iso_week, 7)
    return week_start, week_end


def split_multi_value_field(value: str) -> list[str]:
    return [
        clean_space(item) for item in re.split(r"[;,|]", value) if clean_space(item)
    ]


def dedupe_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(clean_space(value))
    return ordered


def content_tokens(value: Optional[str]) -> set[str]:
    normalized = normalize_text(value)
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) >= 4 and token not in {"com", "para", "pela", "pelos", "sobre"}
    }
