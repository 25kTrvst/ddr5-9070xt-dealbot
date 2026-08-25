from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from .models import Candidate, Classification


class Storage:
    def __init__(self, path: Path):
        self.path = path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS listings (
              source TEXT NOT NULL, source_id TEXT NOT NULL, kind TEXT NOT NULL,
              title TEXT NOT NULL, url TEXT NOT NULL, model_key TEXT NOT NULL,
              sku TEXT, upc TEXT, last_price REAL NOT NULL, last_seen TEXT NOT NULL,
              last_alert_price REAL, PRIMARY KEY(source, source_id));
            CREATE TABLE IF NOT EXISTS observations (
              source TEXT, source_id TEXT, observed_at TEXT, price REAL,
              shipping REAL, stock TEXT, condition TEXT);
            CREATE TABLE IF NOT EXISTS watchlist (
              url TEXT PRIMARY KEY, source TEXT, source_id TEXT, kind TEXT,
              model_key TEXT, sku TEXT, upc TEXT, next_check TEXT, failures INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ignores (url TEXT PRIMARY KEY, added_at TEXT);
            CREATE TABLE IF NOT EXISTS source_health (
              source TEXT PRIMARY KEY, state TEXT, detail TEXT, blocked_until TEXT, updated_at TEXT);
            CREATE INDEX IF NOT EXISTS idx_obs_item ON observations(source, source_id, observed_at);
            CREATE INDEX IF NOT EXISTS idx_watch_due ON watchlist(next_check);
            """)
            await db.commit()

    async def record(self, c: Candidate, cl: Classification, watch_seconds: int) -> tuple[int, float | None, float | None, bool]:
        now = datetime.now(timezone.utc)
        next_check = (now + timedelta(seconds=watch_seconds)).isoformat()
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT last_price,last_alert_price FROM listings WHERE source=? AND source_id=?", (c.source, c.source_id))
            old = await cur.fetchone()
            cur = await db.execute("SELECT COUNT(*),MIN(price) FROM observations WHERE source=? AND source_id=? AND observed_at>=?", (c.source, c.source_id, (now-timedelta(days=30)).isoformat()))
            count, low = await cur.fetchone()
            previous = old[0] if old else None
            sku = str(c.metadata.get("sku", ""))
            upc = str(c.metadata.get("upc", ""))
            await db.execute("""INSERT INTO listings(source,source_id,kind,title,url,model_key,sku,upc,last_price,last_seen,last_alert_price)
              VALUES(?,?,?,?,?,?,?,?,?,?,NULL)
              ON CONFLICT(source,source_id) DO UPDATE SET title=excluded.title,url=excluded.url,model_key=excluded.model_key,
              sku=excluded.sku,upc=excluded.upc,last_price=excluded.last_price,last_seen=excluded.last_seen""",
              (c.source,c.source_id,c.kind,c.title,c.url,cl.model_key,sku,upc,c.price,now.isoformat()))
            await db.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?)", (c.source,c.source_id,now.isoformat(),c.price,c.shipping,c.stock,c.condition))
            await db.execute("""INSERT INTO watchlist VALUES(?,?,?,?,?,?,?,?,0)
              ON CONFLICT(url) DO UPDATE SET source=excluded.source,source_id=excluded.source_id,kind=excluded.kind,
              model_key=excluded.model_key,sku=excluded.sku,upc=excluded.upc,next_check=excluded.next_check,failures=0""",
              (c.url,c.source,c.source_id,c.kind,cl.model_key,sku,upc,next_check))
            await db.commit()
        new_or_drop = old is None or (old[1] is None) or c.price <= float(old[1]) - 5
        return int(count), previous, low, new_or_drop

    async def mark_alerted(self, c: Candidate) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE listings SET last_alert_price=? WHERE source=? AND source_id=?", (c.price,c.source,c.source_id))
            await db.commit()

    async def due_watchlist(self, limit: int = 100) -> list[dict[str, str]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM watchlist WHERE next_check<=? ORDER BY next_check LIMIT ?", (datetime.now(timezone.utc).isoformat(),limit))
            return [dict(x) for x in await cur.fetchall()]

    async def is_ignored(self, url: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT 1 FROM ignores WHERE url=?", (url,))
            return await cur.fetchone() is not None

    async def ignore(self, url: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR REPLACE INTO ignores VALUES(?,?)", (url,datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def set_health(self, source: str, state: str, detail: str = "", blocked_until: str = "") -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR REPLACE INTO source_health VALUES(?,?,?,?,?)", (source,state,detail[:500],blocked_until,datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def sold_prices(self, model_key: str, csv_path: Path) -> list[float]:
        if not csv_path.exists() or not model_key:
            return []
        def read() -> list[float]:
            with csv_path.open(newline="", encoding="utf-8-sig") as fh:
                return [float(r["sold_price"]) for r in csv.DictReader(fh) if r.get("model_key", "").strip().lower() == model_key.lower() and r.get("sold_price")]
        import asyncio
        return await asyncio.to_thread(read)

    async def corroborating_sources(self, kind: str, model_key: str, price: float, tolerance_percent: float,
                                    exclude_source: str) -> int:
        lo, hi = price * (1 - tolerance_percent / 100), price * (1 + tolerance_percent / 100)
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""SELECT COUNT(DISTINCT source) FROM listings
              WHERE kind=? AND model_key=? AND source<>? AND last_price BETWEEN ? AND ? AND last_seen>=?""",
              (kind,model_key,exclude_source,lo,hi,since))
            return int((await cur.fetchone())[0])

    async def health(self) -> list[dict[str, str]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM source_health ORDER BY source")
            return [dict(r) for r in await cur.fetchall()]
