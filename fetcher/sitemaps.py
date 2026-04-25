"""XML sitemap index and URL-set parsing."""

from __future__ import annotations

from typing import Iterator, Optional
from xml.etree import ElementTree as ET

from processing.text import parse_datetime

_SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}


def parse_sitemap_index(xml_text: str) -> Iterator[dict[str, object]]:
    root = ET.fromstring(xml_text)
    for node in root.findall("sm:sitemap", _SITEMAP_NS):
        loc = node.findtext("sm:loc", default="", namespaces=_SITEMAP_NS).strip()
        lastmod_text = node.findtext(
            "sm:lastmod", default="", namespaces=_SITEMAP_NS
        ).strip()
        if not loc:
            continue
        lastmod = parse_datetime(lastmod_text) if lastmod_text else None
        yield {"loc": loc, "lastmod": lastmod}


def parse_urlset(xml_text: str) -> Iterator[dict[str, object]]:
    root = ET.fromstring(xml_text)
    for node in root.findall("sm:url", _SITEMAP_NS):
        loc = node.findtext("sm:loc", default="", namespaces=_SITEMAP_NS).strip()
        if not loc:
            continue
        published_text = node.findtext(
            "news:news/news:publication_date", default="", namespaces=_SITEMAP_NS
        ).strip()
        lastmod_text = node.findtext(
            "sm:lastmod", default="", namespaces=_SITEMAP_NS
        ).strip()
        title: Optional[str] = (
            node.findtext(
                "news:news/news:title", default="", namespaces=_SITEMAP_NS
            ).strip()
            or None
        )
        published_at = (
            parse_datetime(published_text)
            if published_text
            else parse_datetime(lastmod_text)
        )
        yield {
            "loc": loc,
            "published_at": published_at,
            "title": title,
        }
