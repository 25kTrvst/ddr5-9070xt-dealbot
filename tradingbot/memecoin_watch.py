from __future__ import annotations

import asyncio

import httpx

from .alerts import DOWN_COLOR, UP_COLOR, send_alert
from .config import TradingConfig
from .utils import pct_change

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{addresses}"


async def watch_memecoins(cfg: TradingConfig) -> None:
    if not cfg.memecoin_addresses:
        return
    addresses = ",".join(addr.split(":", 1)[-1] for addr in cfg.memecoin_addresses)
    last_prices: dict[str, float] = {}
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            try:
                resp = await client.get(DEXSCREENER_URL.format(addresses=addresses))
                resp.raise_for_status()
                pairs = resp.json().get("pairs") or []
            except Exception as exc:
                print(f"[memecoin] fetch failed: {exc}")
                await asyncio.sleep(cfg.memecoin_interval_seconds)
                continue
            for pair in pairs:
                base = pair.get("baseToken", {})
                price_raw = pair.get("priceUsd")
                if price_raw is None:
                    continue
                price = float(price_raw)
                key = base.get("address") or base.get("symbol", "?")
                previous = last_prices.get(key)
                if previous:
                    change = pct_change(previous, price)
                    if abs(change) >= cfg.memecoin_move_percent:
                        direction = "up" if change > 0 else "down"
                        volume = float((pair.get("volume") or {}).get("h24", 0) or 0)
                        await send_alert(
                            cfg,
                            title=f"{base.get('symbol', '?')} {direction} {abs(change):.1f}% on {pair.get('dexId', 'dex')}",
                            description=f"Last price ${price:.8f} (was ${previous:.8f})\n24h volume: ${volume:,.0f}",
                            url=pair.get("url"),
                            color=UP_COLOR if change > 0 else DOWN_COLOR,
                        )
                last_prices[key] = price
            await asyncio.sleep(cfg.memecoin_interval_seconds)
