from __future__ import annotations

from .base import StoreParser


class AntonlineParser(StoreParser):
    link_markers = ("/",)
    link_selector = "a.product-title[href], a[href]"
    price_selectors = ("[itemprop='price']", ".price")
