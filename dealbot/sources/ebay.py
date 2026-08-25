from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import httpx

from ..config import Config
from ..models import Candidate, Kind
from .base import Source, SourceError, money


class EbaySource(Source):
    name = "eBay"

    def __init__(self, cfg: Config, client: httpx.AsyncClient):
        self.cfg, self.client = cfg, client
        self._token = ""
        self._expires = 0.0
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.cfg.ebay_client_id and self.cfg.ebay_client_secret)

    async def _oauth(self) -> str:
        if self._token and self._expires > time.monotonic() + 60:
            return self._token
        async with self._lock:
            if self._token and self._expires > time.monotonic() + 60:
                return self._token
            basic = base64.b64encode(f"{self.cfg.ebay_client_id}:{self.cfg.ebay_client_secret}".encode()).decode()
            response = await self.client.post(
                "https://api.ebay.com/identity/v1/oauth2/token",
                headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
            )
            if response.status_code == 401:
                raise SourceError("eBay Production Client ID/Secret rejected (401)")
            response.raise_for_status()
            body = response.json()
            self._token = body["access_token"]
            self._expires = time.monotonic() + int(body.get("expires_in", 7200))
            return self._token

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._oauth()}", "X-EBAY-C-MARKETPLACE-ID": self.cfg.ebay_marketplace_id}

    async def search(self, kind: Kind) -> list[Candidate]:
        if not self.configured:
            return []
        query = self.cfg.ram_query if kind == "ram" else self.cfg.gpu_query
        category = self.cfg.ebay_ram_category_id if kind == "ram" else self.cfg.ebay_gpu_category_id
        ceiling = self.cfg.ram_max_price if kind == "ram" else self.cfg.gpu_max_price
        response = await self.client.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers=await self._headers(),
            params={
                "q": query, "category_ids": category, "limit": self.cfg.ebay_max_results,
                "sort": "newlyListed", "filter": f"conditions:{{NEW}},price:[1..{ceiling}],priceCurrency:USD,buyingOptions:{{FIXED_PRICE}}",
                "fieldgroups": "EXTENDED",
            },
        )
        response.raise_for_status()
        output: list[Candidate] = []
        for item in response.json().get("itemSummaries", []):
            price = money(item.get("price"))
            if price is None:
                continue
            seller = item.get("seller") or {}
            feedback_score = int(seller.get("feedbackScore") or 0)
            feedback_pct = float(seller.get("feedbackPercentage") or 0)
            if feedback_score < self.cfg.ebay_min_feedback_score or feedback_pct < self.cfg.ebay_min_feedback_percent:
                continue
            shipping_options = item.get("shippingOptions") or []
            shipping = money(shipping_options[0].get("shippingCost")) if shipping_options else None
            output.append(Candidate(
                source=self.name, source_id=str(item.get("itemId", "")), kind=kind,
                title=str(item.get("title", "")), url=str(item.get("itemWebUrl", "")), price=price,
                shipping=shipping, condition=str(item.get("condition", "unknown")), stock="in stock",
                category_id=str(item.get("categoryId", category)), category_name=str((item.get("categories") or [{}])[0].get("categoryName", "")),
                seller_feedback_score=feedback_score, seller_feedback_percent=feedback_pct, source_confidence=95,
                metadata={"listing_type": "fixed price", "sku": item.get("legacyItemId", ""), "image": (item.get("image") or {}).get("imageUrl", "")},
            ))
        return output

    async def get_item(self, item_id: str, kind: Kind) -> Candidate | None:
        response = await self.client.get(f"https://api.ebay.com/buy/browse/v1/item/{item_id}", headers=await self._headers())
        if response.status_code == 404:
            return None
        response.raise_for_status()
        item: dict[str, Any] = response.json()
        price = money(item.get("price"))
        if price is None:
            return None
        shipping_options = item.get("shippingOptions") or []
        seller = item.get("seller") or {}
        score = int(seller.get("feedbackScore") or 0); percent = float(seller.get("feedbackPercentage") or 0)
        if score < self.cfg.ebay_min_feedback_score or percent < self.cfg.ebay_min_feedback_percent:
            return None
        aspects = {str(a.get("name", "")): [str(v) for v in a.get("values", [])] for a in item.get("localizedAspects", [])}
        return Candidate(self.name, item_id, kind, str(item.get("title", "")), str(item.get("itemWebUrl", "")), price,
            shipping=money(shipping_options[0].get("shippingCost")) if shipping_options else None,
            condition=str(item.get("condition", "unknown")), stock="in stock", category_id=str(item.get("categoryId", "")),
            aspects=aspects, seller_feedback_score=score,
            seller_feedback_percent=percent, source_confidence=99,
            metadata={"sku": item.get("legacyItemId", ""), "description": item.get("shortDescription", ""), "price_surface": "item API"})
