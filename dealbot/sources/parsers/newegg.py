from __future__ import annotations

from .base import StoreParser


class NeweggParser(StoreParser):
    link_markers = ("/p/",)
    link_selector = "a.item-title[href], a[href*='/p/']"
    price_selectors = ("#ProductBuy .price-current", ".product-buy .price-current", ".product-price .price-current")
