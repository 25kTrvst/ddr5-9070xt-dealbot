from __future__ import annotations

import asyncio

import ccxt.async_support as ccxt_async

from .alerts import DOWN_COLOR, UP_COLOR, send_alert
from .config import TradingConfig
from .utils import pct_change


async def watch_crypto(cfg: TradingConfig) -> None:
    if not cfg.crypto_symbols:
        return
    try:
        exchange_cls = getattr(ccxt_async, cfg.crypto_exchange)
    except AttributeError:
        print(f"[crypto] Unknown ccxt exchange id: {cfg.crypto_exchange!r}. See github.com/ccxt/ccxt for valid ids.")
        return
    exchange = exchange_cls()
    last_prices: dict[str, float] = {}
    try:
        while True:
            for symbol in cfg.crypto_symbols:
                try:
                    ticker = await exchange.fetch_ticker(symbol)
                except Exception as exc:
                    print(f"[crypto] {symbol} fetch failed: {exc}")
                    continue
                price = ticker.get("last")
                if price is None:
                    continue
                previous = last_prices.get(symbol)
                if previous:
                    change = pct_change(previous, price)
                    if abs(change) >= cfg.crypto_move_percent:
                        direction = "up" if change > 0 else "down"
                        await send_alert(
                            cfg,
                            title=f"{symbol} {direction} {abs(change):.1f}% on {cfg.crypto_exchange}",
                            description=f"Last price ${price:,.4f} (was ${previous:,.4f})",
                            color=UP_COLOR if change > 0 else DOWN_COLOR,
                        )
                last_prices[symbol] = price
            await asyncio.sleep(cfg.crypto_interval_seconds)
    finally:
        await exchange.close()
