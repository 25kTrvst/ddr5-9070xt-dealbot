from __future__ import annotations

from .base import StoreParser


class ProvantageParser(StoreParser):
    # Provantage's product pages are static, tilde-prefixed codes, e.g.
    # https://www.provantage.com/~880DIAM1.htm - distinctive enough to match on.
    link_markers = ("~",)
    link_selector = "a[href*='~']"
    price_selectors = ("[itemprop='price']", ".price", "#price")
