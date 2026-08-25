from __future__ import annotations

from .base import StoreParser


class CentralComputersParser(StoreParser):
    link_markers = (".html",)
    link_selector = "a.product-item-link[href], a[href$='.html']"
    price_selectors = ("[itemprop='price']", ".price")
