import httpx
import pytest

from dealbot.config import Config, StoreConfig
from dealbot.sources.base import BlockedSource
from dealbot.sources.retailer import RetailerSource


def _source(cfg: Config | None = None) -> RetailerSource:
    cfg = cfg or Config(discord_token="test")
    store = StoreConfig("TestStore", "https://example.com/search?q={query}", ("example.com",))
    return RetailerSource(cfg, store, httpx.AsyncClient(), browser=None)


@pytest.mark.asyncio
async def test_blocked_source_propagates_instead_of_being_swallowed():
    # A regression: BlockedSource is a subclass of SourceError, so the
    # per-page except clause meant to survive one bad page was also
    # silently swallowing genuine 403/429 blocks, which should instead
    # reach the engine's backoff handling.
    source = _source()

    async def raises_blocked(url: str):
        raise BlockedSource("HTTP 403")

    source._collect_links = raises_blocked
    with pytest.raises(BlockedSource):
        await source.search("ram")


@pytest.mark.asyncio
async def test_ordinary_source_error_on_one_query_does_not_abort_the_others():
    source = _source()
    calls = []

    async def flaky(url: str):
        calls.append(url)
        if len(calls) == 2:
            raise TimeoutError("simulated slow page")
        return []

    source._collect_links = flaky
    result = await source.search("ram")
    assert result == []
    assert len(calls) >= 1  # didn't crash the whole scan on one bad query


@pytest.mark.asyncio
async def test_ram_queries_rotate_instead_of_all_firing_every_cycle():
    cfg = Config(discord_token="test")
    source = _source(cfg)
    seen_urls = []

    async def record_url(url: str):
        seen_urls.append(url)
        return []

    source._collect_links = record_url
    await source.search("ram")
    assert len(seen_urls) == 1  # not len(cfg.ram_queries), which is >1 by default
