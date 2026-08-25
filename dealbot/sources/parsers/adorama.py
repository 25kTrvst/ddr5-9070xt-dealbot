from __future__ import annotations

from .base import StoreParser


class AdoramaParser(StoreParser):
    link_markers = ("/p/", ".html")
    link_selector = "a.item-box-link[href], a[href*='/p/']"
    price_selectors = ("[itemprop='price']", ".your-price", ".price")
