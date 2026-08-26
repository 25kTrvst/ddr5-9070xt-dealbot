from __future__ import annotations

import asyncio
import random
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from .browser import BrowserManager
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
from .webstatus import StatusWebServer

CRASH_RESTART_DELAY_SECONDS = 30


class Engine:
    def __init__(self, cfg: Config, on_deal, on_crash=None):
        self.cfg, self.on_deal, self.on_crash = cfg, on_deal, on_crash
        self.client = httpx.AsyncClient(timeout=cfg.http_timeout_seconds, follow_redirects=True)
        self.storage = Storage(cfg.database_path)
        self.browser = BrowserManager()
        self.ebay = EbaySource(cfg, self.client); self.bestbuy = BestBuySource(cfg, self.client)
        self.retailers = [RetailerSource(cfg, s, self.client, self.browser) for s in STORES]
        self.discovery = [RedditDiscovery(cfg, self.client), SlickdealsDiscovery(cfg), ZohoDiscovery(cfg)]
        self.tasks: list[asyncio.Task] = []; self._locks = defaultdict(lambda: asyncio.Semaphore(cfg.store_concurrency))
        self._blocked_until: dict[str, datetime] = {}; self.last_scans: dict[str, str] = {}
        self.web = StatusWebServer(cfg, self) if cfg.status_web_enabled else None

    async def start(self) -> None:
        await self.storage.initialize()
        await self.browser.start()
        if self.web:
            self.web.start()
        self.tasks.extend([
            self._spawn(lambda: self._source_loop(self.ebay, self.cfg.ebay_interval_seconds), "ebay-fast"),
            self._spawn(lambda: self._source_loop(self.bestbuy, self.cfg.bestbuy_interval_seconds, initial_delay=20), "bestbuy-fast"),
            self._spawn(self._watch_loop, "sku-watchlist"),
        ])
        for d in self.discovery:
            interval = self.cfg.reddit_interval_seconds if isinstance(d, RedditDiscovery) else self.cfg.slickdeals_interval_seconds if isinstance(d, SlickdealsDiscovery) else self.cfg.email_interval_seconds
            self.tasks.append(self._spawn(lambda d=d, interval=interval: self._discovery_loop(d, interval), f"{d.name}-discovery"))
        for index, source in enumerate(self.retailers):
            interval = source.store.interval_seconds
            offset = index * interval / max(1, len(self.retailers))
            self.tasks.append(self._spawn(
                lambda source=source, interval=interval, offset=offset: self._source_loop(source, interval, jitter=180, initial_delay=offset),
                f"{source.name}-broad",
            ))

    def _spawn(self, factory, name: str) -> asyncio.Task:
        return asyncio.create_task(self._supervised(factory, name), name=name)

    async def _supervised(self, factory, name: str) -> None:
        """Every background scanner runs forever by design; if one still dies
        from an unhandled bug, this notices, logs it, tells the operator, and
        restarts it — a scanner can never silently stop."""
        while True:
            try:
                await factory()
                exc: Exception = RuntimeError("loop exited without raising")
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - deliberately broad: this is the last-resort safety net
                exc = e
            await self.storage.set_health(name, "crashed", f"{type(exc).__name__}: {exc}; restarting in {CRASH_RESTART_DELAY_SECONDS}s")
            if self.on_crash:
                try:
                    await self.on_crash(name, exc)
                except Exception:
                    pass
            await asyncio.sleep(CRASH_RESTART_DELAY_SECONDS)

    async def stop(self) -> None:
        for t in self.tasks: t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.client.aclose()
        await self.browser.stop()
        if self.web:
            self.web.stop()

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
        # Before identity is known, use the most permissive ceiling across every
        # tracked model just to decide whether a price looks cheap enough to
        # double-check; the real per-model ceiling is resolved after classify().
        precheck_limit = self.cfg.ram_max_price if c.kind == "ram" else self.cfg.gpu_precheck_ceiling
        if c.source == "eBay" and c.price < precheck_limit * self.cfg.unusual_price_ratio and c.metadata.get("price_surface") != "item API":
            detailed = await self.ebay.get_item(c.source_id, c.kind)
            if detailed and abs(detailed.price - c.price) <= max(1.0, c.price * self.cfg.corroboration_tolerance_percent / 100):
                detailed.metadata["price_verification_count"] = 2
                detailed.metadata["price_sources"] = ["eBay search API", "eBay item API"]
                c = detailed
        cl = classify(c, self.cfg)
        if not cl.accepted or cl.confidence < self.cfg.minimum_identity_confidence: return None
        limit = self.cfg.ram_max_price if c.kind == "ram" else self.cfg.gpu_price_ceiling(cl.identity_label)
        if c.price > limit: return None
        observations, previous, low, should_alert, restocked = await self.storage.record(c, cl, self.cfg.watchlist_interval_seconds)
        unconfirmed = False
        if c.price < limit * self.cfg.unusual_price_ratio:
            matches = await self.storage.corroborating_sources(c.kind, cl.model_key, c.price, self.cfg.corroboration_tolerance_percent, c.source)
            if matches < 1 and int(c.metadata.get("price_verification_count", 1)) < 2:
                # Unusually cheap and not yet corroborated by a second price surface.
                # Still surface it as a clearly-flagged warning instead of hiding it.
                unconfirmed = True
                await self.storage.set_health(c.source, "quarantine", f"unusually cheap {cl.model_key}; alerted as UNCONFIRMED pending a second price surface")
        if not should_alert: return None
        sold = await self.storage.sold_prices(cl.model_key, self.cfg.sold_comps_file)
        baseline, low_all, sample_count = await self.storage.market_baseline(c.kind, cl.model_key)
        deal = make_deal(c, cl, self.cfg, observations, previous, low, sold, baseline, low_all, sample_count, limit)
        deal.restocked = restocked
        if unconfirmed:
            deal.unconfirmed = True
            deal.recommendation = "UNCONFIRMED — VERIFY BEFORE BUYING"
            deal.recommendation_reason = "Price is far below the normal range and has only been seen once on one source. " + deal.recommendation_reason
        elif deal.recommendation == "WAIT / WATCH":
            if restocked:
                deal.recommendation = "BACK IN STOCK"
                deal.recommendation_reason = "This exact listing was out of stock and just became available again. " + deal.recommendation_reason
            else:
                return None
        if not emit:
            return None
        await self.on_deal(deal); await self.storage.mark_alerted(c)
        return deal

    async def _watch_loop(self) -> None:
        limiter = asyncio.Semaphore(self.cfg.store_concurrency)
        while True:
            api_counts = defaultdict(int)
            rows = []
            for row in await self.storage.due_watchlist():
                if row["source"] in {"eBay", "Best Buy"}:
                    if api_counts[row["source"]] >= self.cfg.api_watch_batch_size: continue
                    api_counts[row["source"]] += 1
                rows.append(row)

            async def verify(row: dict[str, str]) -> Candidate | None:
                async with limiter:
                    try:
                        c = await self._verify_watch_row(row)
                    except Exception:
                        return None
                    if c is None and row["source"] in {"eBay", "Best Buy"}:
                        # These APIs simply omit an unavailable item rather than
                        # returning it with a stock status, so record it as out
                        # of stock ourselves; a later successful re-check at the
                        # same source/source_id is then recognized as a restock.
                        await self.storage.mark_out_of_stock(row["source"], row["source_id"])
                    return c

            # Verifying due rows is the slow, network-bound part; run them
            # concurrently instead of one at a time. Alerting stays sequential
            # afterward so max_alerts_per_kind_scan is still enforced exactly.
            candidates = await asyncio.gather(*(verify(row) for row in rows))
            alert_counts = defaultdict(int)
            for c in candidates:
                if not c: continue
                try:
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
