from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # lets the offline self-test run before first-time installation
    def load_dotenv(*_args, **_kwargs):
        return False

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def env_float(name: str, default: float, minimum: float | None = None) -> float:
    value = float(os.getenv(name, str(default)))
    if minimum is not None:
        value = max(minimum, value)
    return value


def env_int(name: str, default: int, minimum: int | None = None) -> int:
    value = int(os.getenv(name, str(default)))
    if minimum is not None:
        value = max(minimum, value)
    return value


def env_list(name: str, default: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())


@dataclass(slots=True)
class TradingConfig:
    """Alerts-only watcher: no keys required to read public market data.

    Crypto uses ccxt (any exchange id, no API key needed for tickers).
    Stocks use yfinance (Yahoo Finance, no API key needed).
    Memecoins use Dexscreener's public API (no API key needed).
    """

    discord_webhook_url: str = field(default_factory=lambda: os.getenv("TRADING_DISCORD_WEBHOOK_URL", "").strip())

    crypto_exchange: str = field(default_factory=lambda: os.getenv("CRYPTO_EXCHANGE", "kraken").strip().lower())
    crypto_symbols: tuple[str, ...] = field(default_factory=lambda: env_list("CRYPTO_SYMBOLS", "BTC/USD,ETH/USD,SOL/USD"))
    crypto_move_percent: float = field(default_factory=lambda: env_float("CRYPTO_MOVE_PERCENT", 3.0, 0.1))
    crypto_interval_seconds: int = field(default_factory=lambda: env_int("CRYPTO_INTERVAL_SECONDS", 60, 15))

    stock_symbols: tuple[str, ...] = field(default_factory=lambda: env_list("STOCK_SYMBOLS", "AAPL,TSLA,NVDA"))
    stock_move_percent: float = field(default_factory=lambda: env_float("STOCK_MOVE_PERCENT", 3.0, 0.1))
    stock_interval_seconds: int = field(default_factory=lambda: env_int("STOCK_INTERVAL_SECONDS", 300, 60))

    memecoin_addresses: tuple[str, ...] = field(default_factory=lambda: env_list("MEMECOIN_ADDRESSES", ""))
    memecoin_move_percent: float = field(default_factory=lambda: env_float("MEMECOIN_MOVE_PERCENT", 8.0, 0.1))
    memecoin_interval_seconds: int = field(default_factory=lambda: env_int("MEMECOIN_INTERVAL_SECONDS", 60, 30))

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.discord_webhook_url:
            issues.append("TRADING_DISCORD_WEBHOOK_URL is not set; alerts will only print to the console")
        if not (self.crypto_symbols or self.stock_symbols or self.memecoin_addresses):
            issues.append("No symbols configured: set CRYPTO_SYMBOLS, STOCK_SYMBOLS, and/or MEMECOIN_ADDRESSES")
        return issues
