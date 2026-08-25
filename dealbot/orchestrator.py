from __future__ import annotations

import asyncio
import random
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from .classification import classify
from .config import Config, STORES
from .models import Candidate, Deal, Kind
from .scoring import make_deal
from .sources.base import BlockedSource
from .sources.bestbuy import BestBuySource
from .sources.discovery import Lead, RedditDiscovery, SlickdealsDiscovery, ZohoDiscovery
from .sources.ebay import EbaySource
from .sources.retailer import RetailerSource
from .storage import Storage


class Engine:
    def __init__(self, cfg: Config, on_deal):
        self.cfg, self.on_deal = cfg, on_deal
        self.client = httpx.AsyncClient(timeout=cfg.http_timeout_seconds, follow_redirects=True)
        self.storage = Storage(cfg.database_path)
        self.ebay = EbaySource(cfg, self.client); self.bestbuy = BestBuySource(cfg, self.client)
        self.retailers = [RetailerSource(cfg, s, self.client) for s in STORES]
        self.discovery = [RedditDiscovery(cfg, self.client), SlickdealsDiscovery(cfg), ZohoDiscovery(cfg)]
        self.tasks: list[asyncio.Task] = []; self._locks = defaultdict(lambda: asyncio.Semaphore(cfg.store_concurrency))
        self._blocked_until: dict[str, datetime] = {}; self.last_scans: dict[str, str] = {}

    async def start(self) -> None:
        await self.storage.initialize()
        self.tasks.extend([
            asyncio.create_task(self._source_loop(self.ebay, self.cfg.ebay_interval_seconds), name="ebay-fast"),
            asyncio.create_task(self._source_loop(self.bestbuy, self.cfg.bestbuy_interval_seconds, initial_delay=20), name="bestbuy-fast"),
            asyncio.create_task(self._watch_loop(), name="sku-watchlist"),
        ])
        for d in self.discovery:
            interval = self.cfg.reddit_interval_seconds if isinstance(d, RedditDiscovery) else self.cfg.slickdeals_interval_seconds if isinstance(d, SlickdealsDiscovery) else self.cfg.email_interval_seconds
            self.tasks.append(asyncio.create_task(self._discovery_loop(d, interval), name=f"{d.name}-discovery"))
        for index, source in enumerate(self.retailers):
            offset = index * self.cfg.slow_interval_seconds / max(1, len(self.retailers))
            self.tasks.append(asyncio.create_task(self._source_loop(source, self.cfg.slow_interval_seconds, jitter=180, initial_delay=offset), name=f"{source.name}-broad"))

    async def stop(self) -> None:
        for t in self.tasks: t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True); await self.client.aclose()

    async def _source_loop(self, source, interval: int, jitter: int = 10, initial_delay: float = 0) -> None:
        await asyncio.sleep(initial_delay + random.uniform(0, min(15, interval / 4)))
        while True:
            await self.scan_source(source)
            await asyncio.sleep(interval + random.uniform(0, jitter))

    async def scan_source(self, source, kind: Kind | None = None) -> list[Deal]:
        if source.name in self._blocked_until and self._blocked_until[source.name] > datetime.now(timezone.utc): return []
        deals: list[Deal] = []
        async with self._locks[source.name]:
            try:
                for k in ([kind] if kind else ["ram", "gpu"]):
                    emitted_for_kind = 0
                    for candidate in await source.search(k):
                        deal = await self.process(candidate, emit=emitted_for_kind < self.cfg.max_alerts_per_kind_scan)
                        if deal:
                            deals.append(deal); emitted_for_kind += 1
                self.last_scans[source.name] = datetime.now(timezone.utc).isoformat()
                await self.storage.set_health(source.name, "ok", f"verified {len(deals)} alert-worthy deal(s)")
            except BlockedSource as exc:
                delay = random.randint(self.cfg.blocked_backoff_min_seconds, self.cfg.blocked_backoff_max_seconds)
                until = datetime.now(timezone.utc) + timedelta(seconds=delay); self._blocked_until[source.name] = until
                await self.storage.set_health(source.name, "backoff", str(exc), until.isoformat())
            except Exception as exc:
                await self.storage.set_health(source.name, "error", f"{type(exc).__name__}: {exc}")
        return deals

    async def process(self, c: Candidate, emit: bool = True) -> Deal | None:
        if not c.url or await self.storage.is_ignored(c.url): return None
        limit = self.cfg.ram_max_price if c.kind == "ram" else self.cfg.gpu_max_price
        if c.source == "eBay" and c.price < limit * self.cfg.unusual_price_ratio and c.metadata.get("price_surface") != "item API":
            detailed = await self.ebay.get_item(c.source_id, c.kind)
            if detailed and abs(detailed.price - c.price) <= max(1.0, c.price * self.cfg.corroboration_tolerance_percent / 100):
                detailed.metadata["price_verification_count"] = 2
                detailed.metadata["price_sources"] = ["eBay search API", "eBay item API"]
                c = detailed
        cl = classify(c, self.cfg)
        if not cl.accepted or cl.confidence < self.cfg.minimum_identity_confidence: return None
        if c.price > limit: return None
        observations, previous, low, should_alert = await self.storage.record(c, cl, self.cfg.watchlist_interval_seconds)
        if c.price < limit * self.cfg.unusual_price_ratio:
            matches = await self.storage.corroborating_sources(c.kind, cl.model_key, c.price, self.cfg.corroboration_tolerance_percent, c.source)
            if matches < 1 and int(c.metadata.get("price_verification_count", 1)) < 2:
                await self.storage.set_health(c.source, "quarantine", f"unusually cheap {cl.model_key}; requires two matching price surfaces")
                return None
        if not should_alert: return None
        sold = await self.storage.sold_prices(cl.model_key, self.cfg.sold_comps_file)
        deal = make_deal(c, cl, self.cfg, observations, previous, low, sold)
        if deal.recommendation == "WAIT / WATCH":
            return None
        if not emit:
            return None
        await self.on_deal(deal); await self.storage.mark_alerted(c)
        return deal

    async def _watch_loop(self) -> None:
        while True:
            api_counts = defaultdict(int)
            alert_counts = defaultdict(int)
            for row in await self.storage.due_watchlist():
                if row["source"] in {"eBay", "Best Buy"}:
                    if api_counts[row["source"]] >= self.cfg.api_watch_batch_size: continue
                    api_counts[row["source"]] += 1
                try:
                    c = await self._verify_watch_row(row)
                    if c:
                        deal = await self.process(c, emit=alert_counts[c.kind] < self.cfg.max_alerts_per_kind_scan)
                        if deal: alert_counts[c.kind] += 1
                except Exception: pass
            await asyncio.sleep(self.cfg.watchlist_interval_seconds)

    async def _verify_watch_row(self, row: dict[str, str]) -> Candidate | None:
        if row["source"] == "eBay": return await self.ebay.get_item(row["source_id"], row["kind"])
        if row["source"] == "Best Buy": return await self.bestbuy.get_sku(row["source_id"], row["kind"])
        return await self.verify_lead(Lead("watchlist", row["kind"], row["model_key"], row["url"]))

    async def _discovery_loop(self, source, interval: int) -> None:
        while True:
            try:
                leads = await source.discover()
                alert_counts = defaultdict(int)
                for lead in leads:
                    c = await self.verify_lead(lead)
                    if c:
                        deal = await self.process(c, emit=alert_counts[c.kind] < self.cfg.max_alerts_per_kind_scan)
                        if deal: alert_counts[c.kind] += 1
                await self.storage.set_health(source.name, "ok", f"read {len(leads)} lead(s)")
            except Exception as exc:
                await self.storage.set_health(source.name, "error", f"{type(exc).__name__}: {exc}")
            await asyncio.sleep(interval + random.uniform(0, 10))

    async def verify_lead(self, lead: Lead) -> Candidate | None:
        host = urlparse(lead.url).netloc.lower().removeprefix("www.")
        if "ebay.com" in host:
            match = re.search(r"/(?:itm/)?(?:[^/]+/)?(v1\|)?(\d{9,})", lead.url)
            if match: return await self.ebay.get_item(match.group(2), lead.kind)
        if "bestbuy.com" in host:
            sku_match = re.search(r"(?:skuId=|/)(\d{7,8})(?:[/?]|$)", lead.url)
            if sku_match: return await self.bestbuy.get_sku(sku_match.group(1), lead.kind)
        for source in self.retailers:
            if any(host == d.removeprefix("www.") or host.endswith("." + d.removeprefix("www.")) for d in source.store.domains):
                return await source.verify_url(lead.url, lead.kind)
        return None
