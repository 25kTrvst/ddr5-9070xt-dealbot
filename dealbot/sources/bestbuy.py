from __future__ import annotations

import httpx

from ..config import Config
from ..models import Candidate, Kind
from .base import Source, money


class BestBuySource(Source):
    name = "Best Buy"

    def __init__(self, cfg: Config, client: httpx.AsyncClient):
        self.cfg, self.client = cfg, client

    @property
    def configured(self) -> bool:
        return bool(self.cfg.bestbuy_api_key)

    async def search(self, kind: Kind) -> list[Candidate]:
        if not self.configured:
            return []
        terms = ["32GB", "DDR5"] if kind == "ram" else ["RX", "9070", "XT"]
        fields = "sku,name,salePrice,regularPrice,url,onlineAvailability,condition,manufacturer,modelNumber,upc,categoryPath"
        url = "https://api.bestbuy.com/v1/products(" + "&".join(f"(search={term})" for term in terms) + ")"
        response = await self.client.get(url, params={"apiKey": self.cfg.bestbuy_api_key, "format": "json", "show": fields, "pageSize": 100})
        response.raise_for_status()
        out: list[Candidate] = []
        for p in response.json().get("products", []):
            price = money(p.get("salePrice"))
            if price is None or not p.get("onlineAvailability"):
                continue
            title = f"{p.get('manufacturer','')} {p.get('name','')} {p.get('modelNumber','')}"
            out.append(Candidate(self.name, str(p.get("sku", "")), kind, title, str(p.get("url", "")), price,
                condition=str(p.get("condition", "new")), stock="in stock", category_name=" / ".join(str(x.get("name", "")) for x in p.get("categoryPath", [])),
                source_confidence=98, metadata={"sku": p.get("sku", ""), "upc": p.get("upc", ""), "model": p.get("modelNumber", "")}))
        return out

    async def get_sku(self, sku: str, kind: Kind) -> Candidate | None:
        if not self.configured or not sku: return None
        fields = "sku,name,salePrice,url,onlineAvailability,condition,manufacturer,modelNumber,upc,categoryPath"
        r = await self.client.get(f"https://api.bestbuy.com/v1/products(sku={sku})",
            params={"apiKey": self.cfg.bestbuy_api_key, "format": "json", "show": fields})
        r.raise_for_status(); products = r.json().get("products", [])
        if not products: return None
        p = products[0]; price = money(p.get("salePrice"))
        if price is None or not p.get("onlineAvailability"): return None
        return Candidate(self.name, str(p.get("sku", "")), kind,
            f"{p.get('manufacturer','')} {p.get('name','')} {p.get('modelNumber','')}", str(p.get("url", "")), price,
            condition=str(p.get("condition", "new")), stock="in stock", source_confidence=99,
            metadata={"sku": p.get("sku", ""), "upc": p.get("upc", ""), "model": p.get("modelNumber", "")})
