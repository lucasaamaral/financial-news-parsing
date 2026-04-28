"""HTML metadata extraction utilities."""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from processing.text import (
    clean_space,
    content_tokens,
    dedupe_strings,
    normalize_text,
    parse_datetime,
    split_multi_value_field,
)


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    selectors = (
        ('meta[property="og:title"]', "content"),
        ('meta[name="twitter:title"]', "content"),
        ('meta[name="title"]', "content"),
    )
    for selector, attribute in selectors:
        node = soup.select_one(selector)
        if node and node.get(attribute):
            title = clean_space(node.get(attribute, ""))
            if title:
                return title
    if soup.title and soup.title.string:
        return clean_space(soup.title.string)
    heading = soup.find("h1")
    if heading:
        return clean_space(heading.get_text(" ", strip=True))
    return None


def extract_description(soup: BeautifulSoup) -> Optional[str]:
    selectors = (
        ('meta[name="description"]', "content"),
        ('meta[property="og:description"]', "content"),
        ('meta[name="twitter:description"]', "content"),
        ('meta[name="summary"]', "content"),
        ("h2", None),
        (".subtitle", None),
        (".subheadline", None),
        (".article-subtitle", None),
    )
    for selector, attribute in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        if attribute:
            value = clean_space(node.get(attribute, ""))
        else:
            value = clean_space(node.get_text(" ", strip=True))
        if len(value) >= 20:
            return value
    return None


def extract_published_at(soup: BeautifulSoup):
    candidates = []
    meta_selectors = (
        ('meta[property="article:published_time"]', "content"),
        ('meta[name="article:published_time"]', "content"),
        ('meta[name="pubdate"]', "content"),
        ('meta[itemprop="datePublished"]', "content"),
        ('meta[property="og:updated_time"]', "content"),
    )
    for selector, attribute in meta_selectors:
        node = soup.select_one(selector)
        if node and node.get(attribute):
            candidates.append(node.get(attribute, ""))

    for time_node in soup.find_all("time"):
        if time_node.get("datetime"):
            candidates.append(time_node.get("datetime", ""))

    for script_node in soup.find_all("script", type="application/ld+json"):
        script_text = script_node.string or script_node.get_text(" ", strip=True)
        if not script_text:
            continue
        matches = re.findall(r'"datePublished"\s*:\s*"([^"]+)"', script_text)
        candidates.extend(matches)

    for value in candidates:
        parsed = parse_datetime(value)
        if parsed:
            return parsed
    return None


def extract_tags(soup: BeautifulSoup) -> list[str]:
    tags: list[str] = []
    meta_selectors = (
        ('meta[name="news_keywords"]', "content"),
        ('meta[name="keywords"]', "content"),
        ('meta[property="article:tag"]', "content"),
    )
    for selector, attribute in meta_selectors:
        for node in soup.select(selector):
            if node.get(attribute):
                tags.extend(split_multi_value_field(node.get(attribute, "")))

    for anchor in soup.select('a[rel="tag"], a[href*="/tag/"]'):
        label = clean_space(anchor.get_text(" ", strip=True))
        if label:
            tags.append(label)

    return dedupe_strings(tags)


def sanitize_description(description: Optional[str], *, title: str) -> Optional[str]:
    if not description:
        return None
    description_tokens = content_tokens(description)
    if not description_tokens:
        return None
    reference_tokens = content_tokens(title)
    if not reference_tokens:
        return description
    overlap = description_tokens.intersection(reference_tokens)
    if overlap:
        return description
    return None


def build_sentiment_text(title: str, description: Optional[str]) -> str:
    parts = [f"Titulo: {title}"]
    if description:
        parts.append(f"Resumo: {description}")
    return "\n".join(parts)
