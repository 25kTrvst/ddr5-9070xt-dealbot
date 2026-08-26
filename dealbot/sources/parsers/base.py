from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base import money


@dataclass(slots=True)
class ParsedProduct:
    title: str = ""
    price: float | None = None
    condition: str = "unknown"
    stock: str = "unknown"
    sku: str = ""
    upc: str = ""
    model: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.title) and self.price is not None


class StoreParser:
    """Shared JSON-LD product extraction, with per-store link discovery and
    price-selector overrides. Each functioning store gets its own subclass
    below instead of every store sharing one generic scrape path."""

    link_markers: tuple[str, ...] = ()
    link_selector: str = "a[href]"
    price_selectors: tuple[str, ...] = ()

    def find_product_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        urls: list[str] = []
        for a in soup.select(self.link_selector):
            href = str(a.get("href", ""))
            if any(marker in href for marker in self.link_markers):
                full = urljoin(base_url, href).split("?")[0]
                if full not in urls:
                    urls.append(full)
        return urls

    def parse_product_page(self, soup: BeautifulSoup) -> ParsedProduct:
        product = ParsedProduct()
        for node in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(node.get_text(strip=True))
            except (json.JSONDecodeError, TypeError):
                continue
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("@type") != "Product":
                    continue
                product.title = str(entry.get("name", product.title))
                product.sku = str(entry.get("sku", product.sku))
                product.upc = str(entry.get("gtin12", entry.get("gtin", product.upc)))
                product.model = str(entry.get("mpn", entry.get("model", product.model)))
                offers = entry.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = money(offers.get("price", product.price))
                if price is not None:
                    product.price = price
                availability = str(offers.get("availability", "")).lower()
                if "instock" in availability:
                    product.stock = "in stock"
                elif any(x in availability for x in ("outofstock", "soldout", "discontinued", "backorder")):
                    product.stock = "out of stock"
                if "new" in str(offers.get("itemCondition", "")).lower():
                    product.condition = "new"
        product.title = product.title or (soup.title.get_text(" ", strip=True) if soup.title else "")
        if product.price is None:
            product.price = self._price_from_selectors(soup)
        return product

    def _price_from_selectors(self, soup: BeautifulSoup) -> float | None:
        for selector in self.price_selectors:
            node = soup.select_one(selector)
            if node:
                price = money(node.get("content") or re.sub(r"[^0-9.]", "", node.get_text()))
                if price is not None:
                    return price
        return None

    def refine_from_rendered(self, soup: BeautifulSoup, product: ParsedProduct) -> None:
        """Applied to the Playwright-rendered DOM when the static fetch was incomplete."""
        if not product.title and soup.title:
            product.title = soup.title.get_text(" ", strip=True)
        if product.price is None:
            product.price = self._price_from_selectors(soup)
