from __future__ import annotations

from statistics import median

from .config import Config
from .models import Candidate, Classification, Deal


def resale_profit(c: Candidate, sold_prices: list[float], cfg: Config) -> tuple[float | None, float | None]:
    if len(sold_prices) < 3:
        return None, None
    sale = median(sold_prices[-20:])
    fees = sale * cfg.resale_fee_percent / 100 + cfg.resale_fixed_fee
    reserve = sale * cfg.resale_return_reserve_percent / 100
    acquisition = (c.price + (c.shipping or 0)) * (1 + cfg.tax_rate_percent / 100)
    return round(sale, 2), round(sale - fees - reserve - cfg.resale_outbound_shipping - acquisition, 2)


def make_deal(c: Candidate, cl: Classification, cfg: Config, observations: int = 0,
              previous: float | None = None, low_30d: float | None = None,
              sold_prices: list[float] | None = None) -> Deal:
    limit = cfg.ram_max_price if c.kind == "ram" else cfg.gpu_max_price
    ratio = c.price / limit
    score = 55 + max(0, min(30, int((1 - ratio) * 100))) + max(0, (cl.confidence - 85) // 2)
    if c.condition.lower() == "new":
        score += 3
    if observations == 0:
        score = min(score, 82)  # first sighting cannot be called "insane"
    if previous and c.price < previous:
        score += min(8, int(previous - c.price))
    score = max(0, min(100, score))

    sale, profit = resale_profit(c, sold_prices or [], cfg)
    if profit is not None and profit >= cfg.resale_min_profit:
        recommendation = "BUY / RESALE MARGIN"
        reason = f"Exact-model sold median ${sale:.2f}; estimated net profit ${profit:.2f}."
    elif score >= 78 and observations >= 1:
        recommendation = "BUY"
        reason = "Verified exact product and price; price is strong against your configured limit."
    else:
        recommendation = "WAIT / WATCH"
        reason = "Let the watchlist confirm the same SKU again or wait for a lower price."
    tax = round((c.price + (c.shipping or 0)) * cfg.tax_rate_percent / 100, 2)
    return Deal(c, cl, score, recommendation, reason, tax,
                round(c.price + (c.shipping or 0) + tax, 2), observations, previous, low_30d)
