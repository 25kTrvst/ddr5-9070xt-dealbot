from __future__ import annotations

import httpx

from .config import TradingConfig

UP_COLOR = 0x2ECC71
DOWN_COLOR = 0xE74C3C


async def send_alert(cfg: TradingConfig, title: str, description: str, color: int, url: str | None = None) -> None:
    print(f"[ALERT] {title} — {description}")
    if not cfg.discord_webhook_url:
        return
    embed: dict = {"title": title[:256], "description": description[:4096], "color": color}
    if url:
        embed["url"] = url
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(cfg.discord_webhook_url, json={"embeds": [embed]})
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[ALERT] Discord webhook failed: {exc}")
