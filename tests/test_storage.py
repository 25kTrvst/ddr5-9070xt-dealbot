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


def _fake_classification():
    from dealbot.models import Classification
    return Classification(True, 97, ["test"], "CORSAIR:CMK32GX5M2B6000C30", 6000, 30, "2x16GB", 32)
