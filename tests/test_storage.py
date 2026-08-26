from pathlib import Path

import pytest

from dealbot.models import Candidate
from dealbot.storage import Storage


@pytest.mark.asyncio
async def test_market_baseline_aggregates_across_stores(tmp_path: Path):
    storage = Storage(tmp_path / "test.sqlite3")
    await storage.initialize()
    prices_by_source = {"Newegg": 150.0, "Best Buy": 140.0, "Adorama": 90.0}
    for index, (source, price) in enumerate(prices_by_source.items()):
        c = Candidate(source, str(index), "ram", "Corsair Vengeance 32GB DDR5 6000MHz", f"https://x/{index}", price)
        await storage.record(c, _fake_classification(), 120)

    baseline, low, count = await storage.market_baseline("ram", "CORSAIR:CMK32GX5M2B6000C30")
    assert count == 3 and low == 90.0 and baseline == 140.0


@pytest.mark.asyncio
async def test_restock_at_same_price_still_alerts(tmp_path: Path):
    storage = Storage(tmp_path / "test.sqlite3")
    await storage.initialize()
    cl = _fake_classification()

    c1 = Candidate("Newegg", "1", "ram", "Patriot Viper 32GB DDR5 6000MHz", "https://x/1", 120, stock="in stock")
    _, _, _, should_alert, restocked = await storage.record(c1, cl, 120)
    assert should_alert and not restocked
    await storage.mark_alerted(c1)

    c2 = Candidate("Newegg", "1", "ram", "Patriot Viper 32GB DDR5 6000MHz", "https://x/1", 120, stock="out of stock")
    _, _, _, should_alert, restocked = await storage.record(c2, cl, 120)
    assert not should_alert and not restocked  # going out of stock is never itself alert-worthy

    c3 = Candidate("Newegg", "1", "ram", "Patriot Viper 32GB DDR5 6000MHz", "https://x/1", 120, stock="in stock")
    _, _, _, should_alert, restocked = await storage.record(c3, cl, 120)
    assert should_alert and restocked  # same price as before, but a genuine restock


@pytest.mark.asyncio
async def test_price_history_returns_oldest_first_across_stores(tmp_path: Path):
    storage = Storage(tmp_path / "test.sqlite3")
    await storage.initialize()
    for index, price in enumerate([150.0, 140.0, 90.0]):
        c = Candidate("Newegg", str(index), "ram", "Corsair Vengeance 32GB DDR5 6000MHz", f"https://x/{index}", price)
        await storage.record(c, _fake_classification(), 120)

    history = await storage.price_history("ram", "CORSAIR:CMK32GX5M2B6000C30", 90)
    assert [price for _, price in history] == [150.0, 140.0, 90.0]


def _fake_classification():
    from dealbot.models import Classification
    return Classification(True, 97, ["test"], "CORSAIR:CMK32GX5M2B6000C30", 6000, 30, "2x16GB", 32)
