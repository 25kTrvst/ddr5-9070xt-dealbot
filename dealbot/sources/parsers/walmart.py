from __future__ import annotations

from .base import StoreParser


class WalmartParser(StoreParser):
    # Walmart item pages are consistently under /ip/.
    link_markers = ("/ip/",)
    link_selector = "a[href*='/ip/']"
    price_selectors = ("[itemprop='price']", "[data-testid='price-wrap'] span", ".price")
