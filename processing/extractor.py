"""HTML metadata and full-text extraction utilities."""

from __future__ import annotations

import re
from typing import Iterable, Optional

import trafilatura
from bs4 import BeautifulSoup

from domain.config import BOILERPLATE_SNIPPETS
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


def extract_authors(soup: BeautifulSoup) -> list[str]:
    authors: list[str] = []
    meta_selectors = (
        ('meta[name="author"]', "content"),
        ('meta[property="article:author"]', "content"),
    )
    for selector, attribute in meta_selectors:
        node = soup.select_one(selector)
        if node and node.get(attribute):
            authors.extend(split_multi_value_field(node.get(attribute, "")))

    for script_node in soup.find_all("script", type="application/ld+json"):
        script_text = script_node.string or script_node.get_text(" ", strip=True)
        if not script_text:
            continue
        for match in re.findall(r'"author"\s*:\s*(\[[^\]]+\]|\{[^\}]+\})', script_text):
            authors.extend(re.findall(r'"name"\s*:\s*"([^"]+)"', match))

    return dedupe_strings(authors)


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


def extract_article_text(html: str, soup: BeautifulSoup, url: str) -> Optional[str]:
    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if extracted:
        return extracted

    selectors = (
        "[itemprop='articleBody']",
        ".article-body",
        ".entry-content",
        ".post-content",
        ".content-body",
        "article",
        "main",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        paragraphs = [
            clean_space(paragraph.get_text(" ", strip=True))
            for paragraph in node.find_all("p")
            if len(clean_space(paragraph.get_text(" ", strip=True))) >= 40
        ]
        if paragraphs:
            return "\n".join(paragraphs)

    paragraphs = [
        clean_space(paragraph.get_text(" ", strip=True))
        for paragraph in soup.find_all("p")
        if len(clean_space(paragraph.get_text(" ", strip=True))) >= 50
    ]
    if paragraphs:
        return "\n".join(paragraphs[:80])
    return None


def normalize_article_text(text: str) -> str:
    paragraphs = []
    for paragraph in text.splitlines():
        cleaned = clean_space(paragraph)
        if (
            not cleaned
            or _is_boilerplate_paragraph(cleaned)
            or _is_byline_paragraph(cleaned)
        ):
            continue
        paragraphs.append(cleaned)
    return "\n\n".join(paragraphs)


def extract_lead_paragraph(
    text: Optional[str], *, title: str, description: Optional[str]
) -> Optional[str]:
    if not text:
        return None
    ignored = {normalize_text(title)}
    if description:
        ignored.add(normalize_text(description))
    for paragraph in text.split("\n\n"):
        cleaned = clean_space(paragraph)
        normalized = normalize_text(cleaned)
        if cleaned and normalized not in ignored and len(cleaned) >= 40:
            return cleaned
    return None


def sanitize_description(
    description: Optional[str], *, title: str, lead: Optional[str]
) -> Optional[str]:
    if not description:
        return None
    description_tokens = content_tokens(description)
    if not description_tokens:
        return None
    reference_tokens = content_tokens(title)
    reference_tokens.update(content_tokens(lead))
    if not reference_tokens:
        return description
    overlap = description_tokens.intersection(reference_tokens)
    if overlap:
        return description
    return None


def build_sentiment_text(
    *,
    title: str,
    description: Optional[str],
    lead: Optional[str],
) -> str:
    parts = [
        f"Titulo: {title}",
        f"Resumo: {description}" if description else None,
        f"Lead: {lead}" if lead else None,
    ]
    return "\n".join(part for part in parts if part)


def _is_boilerplate_paragraph(paragraph: str) -> bool:
    normalized = normalize_text(paragraph)
    return any(snippet in normalized for snippet in BOILERPLATE_SNIPPETS)


def _is_byline_paragraph(paragraph: str) -> bool:
    """Detect short author/location attribution lines, e.g. 'Por Name, De City — Source'."""
    if len(paragraph) > 200:
        return False
    normalized = normalize_text(paragraph)
    if not normalized.startswith("por "):
        return False
    # Bylines have a location component (', de [city]') or an em-dash source separator
    return ", de " in normalized or "\u2014" in paragraph
