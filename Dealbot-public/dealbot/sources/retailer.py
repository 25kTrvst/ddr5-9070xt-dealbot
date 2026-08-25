from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from ..config import Config, StoreConfig
from ..models import Candidate, Kind
from .base import BlockedSource, Source, SourceError, money


class RetailerSource(Source):
    def __init__(self, cfg: Config, store: StoreConfig, client: httpx.AsyncClient):
        self.cfg, self.store, self.client, self.name = cfg, store, client, store.name

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
        if not self.cfg.browser_fallback: return ""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=self.cfg.browser_timeout_seconds * 1000)
                html = await page.content()
                if (response and response.status in {403, 429}) or re.search(r"access denied|verify you are human|captcha", html, re.I):
                    raise BlockedSource("browser was challenged; respecting a 30–60 minute cooldown")
                return html
            finally:
                await browser.close()

    async def search(self, kind: Kind) -> list[Candidate]:
        query = self.cfg.ram_query if kind == "ram" else self.cfg.gpu_query
        url = self.store.search_url.format(query=quote_plus(query))
        html = await self._get(url); soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        for a in soup.select("a[href]"):
            href = str(a.get("href", ""))
            if any(marker in href for marker in self.store.product_markers):
                full = urljoin(url, href).split("?")[0]
                if full not in urls:
                    urls.append(full)
        if not urls and self.cfg.browser_fallback:
            soup = BeautifulSoup(await self._browser_get(url), "lxml")
            for a in soup.select("a[href]"):
                href = str(a.get("href", ""))
                if any(marker in href for marker in self.store.product_markers):
                    full = urljoin(url, href).split("?")[0]
                    if full not in urls: urls.append(full)
        limiter = asyncio.Semaphore(self.cfg.store_concurrency)
        async def one(product_url: str) -> Candidate | None:
            try:
                async with limiter: return await self.verify_url(product_url, kind)
            except (SourceError, httpx.HTTPError):
                return None
        checked = await asyncio.gather(*(one(u) for u in urls[: self.cfg.max_detail_pages_per_store]))
        return [x for x in checked if x is not None]

    async def verify_url(self, url: str, kind: Kind) -> Candidate | None:
        html = await self._get(url); soup = BeautifulSoup(html, "lxml")
        title = ""
        price: float | None = None
        condition = "unknown"
        stock = "unknown"
        sku = ""
        upc = ""
        model = ""
        for node in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(node.get_text(strip=True))
                entries = data if isinstance(data, list) else [data]
                for entry in entries:
                    if not isinstance(entry, dict) or entry.get("@type") != "Product":
                        continue
                    title = str(entry.get("name", title))
                    sku, upc = str(entry.get("sku", "")), str(entry.get("gtin12", entry.get("gtin", "")))
                    model = str(entry.get("mpn", entry.get("model", "")))
                    offers = entry.get("offers") or {}
                    if isinstance(offers, list): offers = offers[0] if offers else {}
                    price = money(offers.get("price", price))
                    stock = "in stock" if "instock" in str(offers.get("availability", "")).lower() else "unknown"
                    condition = "new" if "new" in str(offers.get("itemCondition", "")).lower() else condition
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
        title = title or (soup.title.get_text(" ", strip=True) if soup.title else "")
        if price is None:
            for selector in self.store.price_selectors:
                node = soup.select_one(selector)
                if node:
                    price = money(node.get("content") or re.sub(r"[^0-9.]", "", node.get_text()))
                    if price is not None: break
        if not title or price is None:
            if self.cfg.browser_fallback:
                soup = BeautifulSoup(await self._browser_get(url), "lxml")
                title = soup.title.get_text(" ", strip=True) if soup.title else title
                for selector in self.store.price_selectors:
                    node = soup.select_one(selector)
                    if node:
                        price = money(node.get("content") or re.sub(r"[^0-9.]", "", node.get_text()))
                        if price is not None: break
            if not title or price is None: return None
        source_id = sku or re.sub(r"\W+", "-", url.rstrip("/").rsplit("/", 1)[-1])[:100]
        return Candidate(self.name, source_id, kind, title, url, price, condition=condition,
            stock=stock, source_confidence=82, metadata={"sku": sku, "upc": upc, "model": model})
