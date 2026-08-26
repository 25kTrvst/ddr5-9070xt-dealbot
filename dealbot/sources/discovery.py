from __future__ import annotations

import asyncio
import base64
import email
import imaplib
import re
import time
from dataclasses import dataclass
from email.header import decode_header, make_header
from urllib.parse import urlparse

import feedparser
import httpx

from ..config import Config
from ..models import Kind


@dataclass(slots=True)
class Lead:
    source: str
    kind: Kind
    title: str
    url: str


def kind_from_text(text: str, cfg: Config) -> Kind | None:
    low = text.lower()
    if re.search(r"\b(?:rx|radeon)\s*9070\s*xt\b", low) and not re.search(r"\b9070\s*gre\b", low):
        return "gpu"
    if cfg.gpu2_enabled and re.search(r"\b(?:rx|radeon)\s*[- ]?7900\s*xtx\b", low):
        return "gpu"
    if "ddr5" in low and any(re.search(rf"\b{c}\s*gb\b", low) for c in cfg.ram_capacities_gb):
        return "ram"
    return None


class RedditDiscovery:
    name = "Reddit"
    def __init__(self, cfg: Config, client: httpx.AsyncClient):
        self.cfg, self.client, self._token, self._expires = cfg, client, "", 0.0

    @property
    def configured(self) -> bool:
        return bool(self.cfg.reddit_client_id and self.cfg.reddit_client_secret and self.cfg.reddit_user_agent)

    async def _oauth(self) -> str:
        if self._token and self._expires > time.monotonic() + 30: return self._token
        basic = base64.b64encode(f"{self.cfg.reddit_client_id}:{self.cfg.reddit_client_secret}".encode()).decode()
        r = await self.client.post("https://www.reddit.com/api/v1/access_token",
            headers={"Authorization": f"Basic {basic}", "User-Agent": self.cfg.reddit_user_agent}, data={"grant_type": "client_credentials"})
        r.raise_for_status()
        data = r.json(); self._token = data["access_token"]; self._expires = time.monotonic() + int(data.get("expires_in", 3600))
        return self._token

    async def discover(self) -> list[Lead]:
        if not self.configured: return []
        headers = {"Authorization": f"bearer {await self._oauth()}", "User-Agent": self.cfg.reddit_user_agent}
        out: list[Lead] = []
        for sub in self.cfg.reddit_subreddits:
            r = await self.client.get(f"https://oauth.reddit.com/r/{sub}/new", headers=headers, params={"limit": 50, "raw_json": 1})
            r.raise_for_status()
            for child in r.json().get("data", {}).get("children", []):
                p = child.get("data", {}); kind = kind_from_text(str(p.get("title", "")), self.cfg)
                url = str(p.get("url_overridden_by_dest", p.get("url", "")))
                if kind and url.startswith("http"): out.append(Lead(f"Reddit r/{sub}", kind, str(p.get("title", "")), url))
        return out


class SlickdealsDiscovery:
    name = "Slickdeals"
    def __init__(self, cfg: Config): self.cfg = cfg
    @property
    def configured(self) -> bool: return bool(self.cfg.slickdeals_feed_url)
    async def discover(self) -> list[Lead]:
        if not self.configured: return []
        feed = await asyncio.to_thread(feedparser.parse, self.cfg.slickdeals_feed_url)
        out: list[Lead] = []
        for e in feed.entries[:100]:
            kind = kind_from_text(str(e.get("title", "")), self.cfg)
            if kind and str(e.get("link", "")).startswith("http"):
                out.append(Lead(self.name, kind, str(e.get("title", "")), str(e.get("link", ""))))
        return out


class ZohoDiscovery:
    name = "Zoho Mail"
    URL_RE = re.compile(r"https?://[^\s<>\"']+")
    def __init__(self, cfg: Config): self.cfg = cfg
    @property
    def configured(self) -> bool: return self.cfg.zoho_imap_enabled and bool(self.cfg.zoho_email and self.cfg.zoho_app_password)
    def _read(self) -> list[Lead]:
        out: list[Lead] = []
        with imaplib.IMAP4_SSL(self.cfg.zoho_imap_host) as box:
            box.login(self.cfg.zoho_email, self.cfg.zoho_app_password); box.select(self.cfg.zoho_folder, readonly=True)
            _, data = box.search(None, "UNSEEN")
            for mid in data[0].split()[-50:]:
                _, raw = box.fetch(mid, "(RFC822)"); msg = email.message_from_bytes(raw[0][1])
                subject = str(make_header(decode_header(msg.get("Subject", ""))))
                body = ""
                for part in msg.walk():
                    if part.get_content_type() in {"text/plain", "text/html"}:
                        try: body += part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
                        except Exception: pass
                kind = kind_from_text(subject + " " + body, self.cfg)
                if kind:
                    for url in self.URL_RE.findall(body):
                        if urlparse(url).scheme in {"http", "https"}: out.append(Lead(self.name, kind, subject, url.rstrip(".,)")))
        return out
    async def discover(self) -> list[Lead]:
        return await asyncio.to_thread(self._read) if self.configured else []
