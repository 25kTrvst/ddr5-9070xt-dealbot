from __future__ import annotations

from bs4 import BeautifulSoup

from .base import ParsedProduct, StoreParser


class MicroCenterParser(StoreParser):
    link_markers = ("/product/",)
    link_selector = "a.image_link[href], a[href*='/product/']"
    price_selectors = ("[itemprop='price']", ".productPrice", ".price")

    def parse_product_page(self, soup: BeautifulSoup) -> ParsedProduct:
        product = super().parse_product_page(soup)
        if product.stock == "unknown":
            node = soup.select_one(".inventoryCell .storeInStock, .stock-status, .inStoreOnly")
            if node and "in stock" in node.get_text(" ", strip=True).lower():
                product.stock = "in stock"
        return product
