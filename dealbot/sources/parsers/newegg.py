from __future__ import annotations

from .base import StoreParser


class NeweggParser(StoreParser):
    link_markers = ("/p/",)
    # Scoped to the search-results grid tile title. A bare a[href*='/p/'] also
    # matches Newegg's "related products" / "customers also viewed" sidebar
    # widgets, which pulled in completely unrelated products (e.g. DDR4 sticks
    # while searching for DDR5) and wasted a browser fetch verifying them.
    link_selector = ".item-cell a.item-title[href]"
    price_selectors = ("#ProductBuy .price-current", ".product-buy .price-current", ".product-price .price-current")
