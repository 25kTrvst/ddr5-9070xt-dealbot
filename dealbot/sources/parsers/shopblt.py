from __future__ import annotations

from .base import StoreParser


class ShopBLTParser(StoreParser):
    # Best-effort: ShopBLT's real product-page URL pattern isn't confirmed
    # (no direct access to inspect their markup). If /status shows this store
    # as "ok" but always 0 candidates - not blocked, just consistently empty -
    # that's the signal these markers need adjusting from a real example link.
    link_markers = ("/product", "/item", ".html")
    link_selector = "a[href]"
    price_selectors = ("[itemprop='price']", ".price", "#price")
