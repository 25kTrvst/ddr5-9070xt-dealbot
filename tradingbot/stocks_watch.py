from __future__ import annotations

import asyncio

import yfinance as yf

from .alerts import DOWN_COLOR, UP_COLOR, send_alert
from .config import TradingConfig
from .utils import pct_change


def _fetch_price(symbol: str) -> float | None:
    price = yf.Ticker(symbol).fast_info.get("last_price")
    return float(price) if price is not None else None


async def watch_stocks(cfg: TradingConfig) -> None:
    if not cfg.stock_symbols:
        return
    last_prices: dict[str, float] = {}
    while True:
        for symbol in cfg.stock_symbols:
            try:
                price = await asyncio.to_thread(_fetch_price, symbol)
            except Exception as exc:
                print(f"[stocks] {symbol} fetch failed: {exc}")
                continue
            if price is None:
                continue
            previous = last_prices.get(symbol)
            if previous:
                change = pct_change(previous, price)
                if abs(change) >= cfg.stock_move_percent:
                    direction = "up" if change > 0 else "down"
                    await send_alert(
                        cfg,
                        title=f"{symbol} {direction} {abs(change):.1f}%",
                        description=f"Last price ${price:,.2f} (was ${previous:,.2f})",
                        color=UP_COLOR if change > 0 else DOWN_COLOR,
                    )
            last_prices[symbol] = price
        await asyncio.sleep(cfg.stock_interval_seconds)
