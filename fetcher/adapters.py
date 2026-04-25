"""Source adapters: one concrete class per news outlet."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Iterator

import requests

from processing.filters import is_gross_match
from fetcher.client import CachedHttpClient
from domain.config import DEFAULT_SITEMAP_WORKERS
from domain.models import CandidateArticle
from fetcher.sitemaps import parse_sitemap_index, parse_urlset
from processing.text import extract_section


class BaseAdapter(ABC):
    def __init__(self, client: CachedHttpClient) -> None:
        self.client = client

    @property
    @abstractmethod
    def source(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def iter_candidates(
        self, start_date: date, end_date: date
    ) -> Iterator[CandidateArticle]:
        raise NotImplementedError


class BaseSitemapAdapter(BaseAdapter):
    index_url: str

    def iter_candidates(
        self, start_date: date, end_date: date
    ) -> Iterator[CandidateArticle]:
        payload = self.client.get_text(self.index_url)
        sitemap_urls = list(self.select_sitemaps(payload.text, start_date, end_date))

        def _fetch_entries(url: str) -> list[CandidateArticle]:
            child = self.client.get_text(url)
            results: list[CandidateArticle] = []
            for entry in parse_urlset(child.text):
                published_at = entry.get("published_at")
                if not published_at:
                    continue
                if not (start_date <= published_at.date() <= end_date):
                    continue
                candidate = CandidateArticle(
                    source=self.source,
                    url=entry["loc"],
                    title=entry.get("title"),
                    section=extract_section(entry["loc"]),
                    published_at=published_at,
                )
                if is_gross_match(candidate):
                    results.append(candidate)
            return results

        with ThreadPoolExecutor(max_workers=DEFAULT_SITEMAP_WORKERS) as pool:
            for candidates in pool.map(_fetch_entries, sitemap_urls):
                yield from candidates

    @abstractmethod
    def select_sitemaps(
        self, index_xml: str, start_date: date, end_date: date
    ) -> Iterator[str]:
        raise NotImplementedError


class InfoMoneyAdapter(BaseSitemapAdapter):
    source = "InfoMoney"
    index_url = "https://www.infomoney.com.br/sitemap_index.xml"
    _allowed_prefixes = (
        "https://www.infomoney.com.br/post-sitemap",
        "https://www.infomoney.com.br/fundos-sitemap",
        "https://www.infomoney.com.br/colunistas-sitemap",
    )

    def select_sitemaps(
        self, index_xml: str, start_date: date, end_date: date
    ) -> Iterator[str]:
        lower_bound = start_date - timedelta(days=45)
        upper_bound = end_date + timedelta(days=3)
        for entry in parse_sitemap_index(index_xml):
            loc = entry["loc"]
            if not loc.startswith(self._allowed_prefixes):
                continue
            lastmod = entry.get("lastmod")
            if lastmod and lower_bound <= lastmod.date() <= upper_bound:
                yield loc


class ExameAdapter(BaseSitemapAdapter):
    source = "Exame"
    index_url = "https://exame.com/artigos/sitemap.xml"

    def select_sitemaps(
        self, index_xml: str, start_date: date, end_date: date
    ) -> Iterator[str]:
        for entry in parse_sitemap_index(index_xml):
            loc = entry["loc"]
            match = re.search(r"/artigos/(\d{4})-(\d{2})/sitemap\.xml$", loc)
            if not match:
                continue
            year, month = int(match.group(1)), int(match.group(2))
            month_start = date(year, month, 1)
            month_end = (
                date(year + 1, 1, 1) - timedelta(days=1)
                if month == 12
                else date(year, month + 1, 1) - timedelta(days=1)
            )
            if month_end < start_date or month_start > end_date:
                continue
            monthly_payload = self.client.get_text(loc)
            for daily_entry in parse_sitemap_index(monthly_payload.text):
                daily_loc = daily_entry["loc"]
                daily_match = re.search(
                    r"/artigos/(\d{4})-(\d{2})/(\d{2})/sitemap\.xml$", daily_loc
                )
                if not daily_match:
                    continue
                sitemap_day = date(
                    int(daily_match.group(1)),
                    int(daily_match.group(2)),
                    int(daily_match.group(3)),
                )
                if start_date <= sitemap_day <= end_date:
                    yield daily_loc


class ValorAdapter(BaseSitemapAdapter):
    source = "Valor Econômico"
    index_url = "https://valor.globo.com/sitemap/valor/sitemap.xml"

    def select_sitemaps(
        self, index_xml: str, start_date: date, end_date: date
    ) -> Iterator[str]:
        for entry in parse_sitemap_index(index_xml):
            loc = entry["loc"]
            match = re.search(r"/sitemap/valor/(\d{4})/(\d{2})/(\d{2})_\d+\.xml$", loc)
            if not match:
                continue
            sitemap_day = date(
                int(match.group(1)), int(match.group(2)), int(match.group(3))
            )
            if start_date <= sitemap_day <= end_date:
                yield loc


def build_adapters(client: CachedHttpClient) -> list[BaseAdapter]:
    """Factory: returns all active source adapters."""
    return [InfoMoneyAdapter(client), ValorAdapter(client), ExameAdapter(client)]
