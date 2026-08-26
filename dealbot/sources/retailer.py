from __future__ import annotations

import asyncio
import re
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from ..browser import BrowserManager
from ..config import Config, StoreConfig
from ..models import Candidate, Kind
from .base import BlockedSource, Source, SourceError
from .parsers import get_parser


class RetailerSource(Source):
    def __init__(self, cfg: Config, store: StoreConfig, client: httpx.AsyncClient, browser: BrowserManager):
        self.cfg, self.store, self.client, self.browser, self.name = cfg, store, client, browser, store.name
        self.parser = get_parser(store.name)

    async def _get(self, url: str) -> str:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; DealBot/6.0; personal price monitor)"}
        if self.name == "Micro Center" and self.cfg.microcenter_store_id:
            headers["Cookie"] = f"storeSelected={self.cfg.microcenter_store_id}"
        r = await self.client.get(url, headers=headers, follow_redirects=True)
        if r.status_code in {403, 429}:
            raise BlockedSource(f"HTTP {r.status_code}; backing off without bypassing the challenge")
        if r.status_code >= 400:
            raise SourceError(f"HTTP {r.status_code}")
        return r.text

    async def _browser_get(self, url: str) -> str:
        if not self.cfg.browser_fallback:
            return ""
        return await self.browser.fetch(url, self.cfg.browser_timeout_seconds)

    async def search(self, kind: Kind) -> list[Candidate]:
        queries = self.cfg.ram_queries if kind == "ram" else self.cfg.gpu_queries
        # One shared budget for both search-page and detail-page requests to this
        # store, so parallelizing the per-speed RAM search doesn't raise the total
        # number of simultaneous requests a store sees beyond STORE_CONCURRENCY.
        limiter = asyncio.Semaphore(self.cfg.store_concurrency)

        async def collect(query: str) -> list[str]:
            search_url = self.store.search_url.format(query=quote_plus(query))
            try:
                async with limiter:
                    return await self._collect_links(search_url)
            except (SourceError, httpx.HTTPError):
                return []

        batches = await asyncio.gather(*(collect(q) for q in queries))
        urls: list[str] = []
        for batch in batches:
            for found in batch:
                if found not in urls:
                    urls.append(found)

        async def one(product_url: str) -> Candidate | None:
            try:
                async with limiter:
                    return await self.verify_url(product_url, kind)
            except (SourceError, httpx.HTTPError):
                return None

        checked = await asyncio.gather(*(one(u) for u in urls[: self.cfg.max_detail_pages_per_store]))
        return [x for x in checked if x is not None]

    async def _collect_links(self, search_url: str) -> list[str]:
        html = await self._get(search_url)
        links = self.parser.find_product_links(BeautifulSoup(html, "lxml"), search_url)
        if not links and self.cfg.browser_fallback:
            rendered = await self._browser_get(search_url)
            if rendered:
                links = self.parser.find_product_links(BeautifulSoup(rendered, "lxml"), search_url)
        return links

    async def verify_url(self, url: str, kind: Kind) -> Candidate | None:
        html = await self._get(url)
        product = self.parser.parse_product_page(BeautifulSoup(html, "lxml"))
        if not product.is_complete and self.cfg.browser_fallback:
            rendered = await self._browser_get(url)
            if rendered:
                self.parser.refine_from_rendered(BeautifulSoup(rendered, "lxml"), product)
        if not product.is_complete:
            return None
        source_id = product.sku or re.sub(r"\W+", "-", url.rstrip("/").rsplit("/", 1)[-1])[:100]
        return Candidate(self.name, source_id, kind, product.title, url, product.price,
            condition=product.condition, stock=product.stock, source_confidence=82,
            metadata={"sku": product.sku, "upc": product.upc, "model": product.model})
