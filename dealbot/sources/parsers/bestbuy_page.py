from __future__ import annotations

from bs4 import BeautifulSoup

from .base import ParsedProduct, StoreParser


class BestBuyPageParser(StoreParser):
    link_markers = ("skuId=",)
    link_selector = "a.sku-title[href], a[href*='skuId=']"
    price_selectors = ("[data-testid='customer-price']", ".priceView-customer-price span", "[itemprop='price']")

    def parse_product_page(self, soup: BeautifulSoup) -> ParsedProduct:
        product = super().parse_product_page(soup)
        if not product.sku:
            node = soup.select_one("[data-sku-id]")
            if node:
                product.sku = str(node.get("data-sku-id", ""))
        return product
