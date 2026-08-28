from __future__ import annotations

import asyncio

from .config import TradingConfig
from .crypto_watch import watch_crypto
from .memecoin_watch import watch_memecoins
from .stocks_watch import watch_stocks


async def _run(cfg: TradingConfig) -> None:
    tasks = []
    if cfg.crypto_symbols:
        tasks.append(watch_crypto(cfg))
    if cfg.stock_symbols:
        tasks.append(watch_stocks(cfg))
    if cfg.memecoin_addresses:
        tasks.append(watch_memecoins(cfg))
    if not tasks:
        raise SystemExit("No symbols configured. Set CRYPTO_SYMBOLS, STOCK_SYMBOLS, and/or MEMECOIN_ADDRESSES in .env")
    print(f"Trading alert bot starting: {len(tasks)} watcher(s) running (alerts-only, no orders are ever placed).")
    await asyncio.gather(*tasks)


def run(cfg: TradingConfig | None = None) -> None:
    asyncio.run(_run(cfg or TradingConfig()))
