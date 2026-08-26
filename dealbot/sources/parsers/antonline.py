from __future__ import annotations

from .base import StoreParser


class AntonlineParser(StoreParser):
    # Best-effort, unverified: the previous "a[href]" fallback matched nearly
    # every link on the page (nav, footer, ads - anything with a "/" in its
    # href), not just products. Scoped to a plausible product-tile class, but
    # like ShopBLT this hasn't been confirmed against real markup - if this
    # store shows "ok" but consistently 0 candidates, send a real example
    # product link from a search results page.
    link_markers = ("/p/", "/product/")
    link_selector = "a.product-title[href], a[href*='/p/'], a[href*='/product/']"
    price_selectors = ("[itemprop='price']", ".price")
