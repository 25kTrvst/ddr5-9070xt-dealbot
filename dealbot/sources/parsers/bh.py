from __future__ import annotations

from .base import StoreParser


class BHPhotoParser(StoreParser):
    link_markers = ("/c/product/",)
    link_selector = "a[href*='/c/product/']"
    price_selectors = ("[data-selenium='pricingPrice']", "[itemprop='price']")
