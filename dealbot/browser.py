from __future__ import annotations

import asyncio
import re

from playwright.async_api import Browser, Playwright, Error as PlaywrightError, async_playwright

from .sources.base import BlockedSource, SourceError

CHALLENGE_RE = re.compile(r"access denied|verify you are human|captcha", re.I)


class BrowserManager:
    """Launches exactly one Chromium process for the whole bot and reuses it
    for every Playwright fallback fetch, instead of paying browser-startup
    cost on every blocked/JS-rendered page. Each fetch still gets its own
    isolated browser context so cookies/storage never bleed between stores."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._browser is not None:
                return
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)

    async def stop(self) -> None:
        async with self._lock:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None

    async def fetch(self, url: str, timeout_seconds: int) -> str:
        if self._browser is None:
            await self.start()
        assert self._browser is not None
        context = await self._browser.new_context()
        try:
            page = await context.new_page()
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
                html = await page.content()
            except PlaywrightError as exc:
                # A slow/unreachable page (timeout, navigation failure, etc.) should
                # only fail this one fetch, not blow up the whole store's scan.
                raise SourceError(f"browser fetch failed: {exc}") from exc
            if (response and response.status in {403, 429}) or CHALLENGE_RE.search(html):
                raise BlockedSource("browser was challenged; respecting a 30–60 minute cooldown")
            return html
        finally:
            await context.close()
