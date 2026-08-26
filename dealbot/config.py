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


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    value = int(os.getenv(name, str(default)))
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def env_float(name: str, default: float, minimum: float | None = None) -> float:
    value = float(os.getenv(name, str(default)))
    if minimum is not None:
        value = max(minimum, value)
    return value


def env_int_list(name: str, default: list[int]) -> list[int]:
    raw = os.getenv(name)
    if not raw:
        return default
    out: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if piece:
            try:
                out.append(int(piece))
            except ValueError:
                continue
    return out or default


@dataclass(slots=True)
class StoreConfig:
    name: str
    search_url: str
    domains: tuple[str, ...]
    interval_seconds: int = 600


@dataclass(slots=True)
class Config:
    discord_token: str = field(default_factory=lambda: os.getenv("DISCORD_TOKEN", "").strip())
    ping_user_id: int = field(default_factory=lambda: env_int("PING_USER_ID", 0, 0))
    ram_channel_name: str = field(default_factory=lambda: os.getenv("RAM_CHANNEL_NAME", "ddr5").strip().lower())
    gpu_channel_name: str = field(default_factory=lambda: os.getenv("GPU_CHANNEL_NAME", "gpu").strip().lower())
    ops_channel_name: str = field(default_factory=lambda: os.getenv("OPS_CHANNEL_NAME", "dealbot-ops").strip().lower())

    ram_query: str = field(default_factory=lambda: os.getenv("RAM_QUERY", "32GB DDR5 desktop memory 6000MHz"))
    gpu_query: str = field(default_factory=lambda: os.getenv("GPU_QUERY", "RX 9070 XT graphics card"))
    gpu_queries: tuple[str, ...] = field(default_factory=tuple)
    ram_speeds: tuple[int, ...] = field(default_factory=lambda: tuple(env_int_list("RAM_SPEEDS", [5000, 5200, 5600, 6000, 6400])))
    ram_capacities_gb: tuple[int, ...] = field(default_factory=lambda: tuple(env_int_list("RAM_CAPACITIES_GB", [16, 32])))
    ram_query_template: str = field(default_factory=lambda: os.getenv("RAM_QUERY_TEMPLATE", "{capacity}GB DDR5 desktop memory {speed}MHz"))
    ram_queries: tuple[str, ...] = field(default_factory=tuple)
    ram_max_price: float = field(default_factory=lambda: env_float("RAM_MAX_PRICE", 200, 1))
    ram_hot_price: float = field(default_factory=lambda: env_float("RAM_HOT_PRICE", 150, 1))
    ram_insane_price: float = field(default_factory=lambda: env_float("RAM_INSANE_PRICE", 120, 1))
    gpu_max_price: float = field(default_factory=lambda: env_float("GPU_MAX_PRICE", 600, 1))
    gpu_great_price: float = field(default_factory=lambda: env_float("GPU_GREAT_PRICE", 550, 1))
    gpu_hot_price: float = field(default_factory=lambda: env_float("GPU_HOT_PRICE", 500, 1))

    # A second GPU model to track alongside the RX 9070 XT, with its own price
    # ceiling (different cards are worth very different amounts, so they can't
    # share one ceiling the way RAM speeds/capacities do).
    gpu2_enabled: bool = field(default_factory=lambda: env_bool("GPU2_ENABLED", False))
    gpu2_label: str = field(default_factory=lambda: os.getenv("GPU2_LABEL", "RX 7900 XTX").strip())
    gpu2_query: str = field(default_factory=lambda: os.getenv("GPU2_QUERY", "RX 7900 XTX graphics card").strip())
    gpu2_max_price: float = field(default_factory=lambda: env_float("GPU2_MAX_PRICE", 700, 1))

    ram_min_speed: int = field(default_factory=lambda: env_int("RAM_MIN_SPEED_MT_S", 5000, 5000, 10000))
    desktop_only: bool = field(default_factory=lambda: env_bool("RAM_DESKTOP_ONLY", True))
    tax_rate_percent: float = field(default_factory=lambda: env_float("TAX_RATE_PERCENT", 6.625, 0))

    ebay_client_id: str = field(default_factory=lambda: os.getenv("EBAY_CLIENT_ID", "").strip())
    ebay_client_secret: str = field(default_factory=lambda: os.getenv("EBAY_CLIENT_SECRET", "").strip())
    ebay_marketplace_id: str = field(default_factory=lambda: os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US").strip())
    ebay_ram_category_id: str = field(default_factory=lambda: os.getenv("EBAY_RAM_CATEGORY_ID", "170083").strip())
    ebay_gpu_category_id: str = field(default_factory=lambda: os.getenv("EBAY_GPU_CATEGORY_ID", "27386").strip())
    ebay_min_feedback_score: int = field(default_factory=lambda: env_int("EBAY_MIN_FEEDBACK_SCORE", 100, 0))
    ebay_min_feedback_percent: float = field(default_factory=lambda: env_float("EBAY_MIN_FEEDBACK_PERCENT", 97.0, 0))
    ebay_interval_seconds: int = field(default_factory=lambda: env_int("EBAY_INTERVAL_SECONDS", 60, 45, 600))
    ebay_max_results: int = field(default_factory=lambda: env_int("EBAY_MAX_RESULTS", 50, 10, 200))

    bestbuy_api_key: str = field(default_factory=lambda: os.getenv("BESTBUY_API_KEY", "").strip())
    bestbuy_interval_seconds: int = field(default_factory=lambda: env_int("BESTBUY_INTERVAL_SECONDS", 60, 60, 1800))

    reddit_client_id: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_ID", "").strip())
    reddit_client_secret: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET", "").strip())
    reddit_user_agent: str = field(default_factory=lambda: os.getenv("REDDIT_USER_AGENT", "").strip())
    reddit_subreddits: tuple[str, ...] = field(default_factory=lambda: tuple(
        x.strip() for x in os.getenv("REDDIT_SUBREDDITS", "buildapcsales,buildapcsalesuk,pcpartsales").split(",") if x.strip()
    ))
    reddit_interval_seconds: int = field(default_factory=lambda: env_int("REDDIT_INTERVAL_SECONDS", 90, 60, 1800))

    slickdeals_feed_url: str = field(default_factory=lambda: os.getenv("SLICKDEALS_FEED_URL", "").strip())
    slickdeals_feed_url_2: str = field(default_factory=lambda: os.getenv("SLICKDEALS_FEED_URL_2", "").strip())
    slickdeals_feed_urls: tuple[str, ...] = field(default_factory=tuple)
    slickdeals_interval_seconds: int = field(default_factory=lambda: env_int("SLICKDEALS_INTERVAL_SECONDS", 90, 60, 1800))
    zoho_imap_enabled: bool = field(default_factory=lambda: env_bool("ZOHO_IMAP_ENABLED", False))
    zoho_imap_host: str = field(default_factory=lambda: os.getenv("ZOHO_IMAP_HOST", "imap.zoho.com").strip())
    zoho_email: str = field(default_factory=lambda: os.getenv("ZOHO_EMAIL", "").strip())
    zoho_app_password: str = field(default_factory=lambda: os.getenv("ZOHO_APP_PASSWORD", "").strip())
    zoho_folder: str = field(default_factory=lambda: os.getenv("ZOHO_FOLDER", "INBOX").strip())
    email_interval_seconds: int = field(default_factory=lambda: env_int("EMAIL_INTERVAL_SECONDS", 120, 60, 1800))

    watchlist_interval_seconds: int = field(default_factory=lambda: env_int("WATCHLIST_INTERVAL_SECONDS", 120, 60, 600))
    api_watch_batch_size: int = field(default_factory=lambda: env_int("API_WATCH_BATCH_SIZE", 2, 1, 10))
    store_concurrency: int = field(default_factory=lambda: env_int("STORE_CONCURRENCY", 2, 1, 2))
    blocked_backoff_min_seconds: int = field(default_factory=lambda: env_int("BLOCKED_BACKOFF_MIN_SECONDS", 1800, 300, 7200))
    blocked_backoff_max_seconds: int = field(default_factory=lambda: env_int("BLOCKED_BACKOFF_MAX_SECONDS", 3600, 600, 14400))
    unusual_price_ratio: float = field(default_factory=lambda: env_float("UNUSUAL_PRICE_RATIO", 0.70, 0.25))
    corroboration_tolerance_percent: float = field(default_factory=lambda: env_float("CORROBORATION_TOLERANCE_PERCENT", 8.0, 1))
    microcenter_store_id: str = field(default_factory=lambda: os.getenv("MICROCENTER_STORE_ID", "").strip())
    microcenter_zip: str = field(default_factory=lambda: os.getenv("MICROCENTER_ZIP", "").strip())

    http_timeout_seconds: int = field(default_factory=lambda: env_int("HTTP_TIMEOUT_SECONDS", 15, 5, 60))
    browser_fallback: bool = field(default_factory=lambda: env_bool("BROWSER_FALLBACK_ENABLED", True))
    browser_timeout_seconds: int = field(default_factory=lambda: env_int("BROWSER_TIMEOUT_SECONDS", 25, 10, 60))
    max_detail_pages_per_store: int = field(default_factory=lambda: env_int("MAX_DETAILS_PER_STORE", 10, 2, 20))
    max_alerts_per_kind_scan: int = field(default_factory=lambda: env_int("MAX_ALERTS_PER_KIND_SCAN", 3, 1, 10))
    price_drop_min: float = field(default_factory=lambda: env_float("PRICE_DROP_MIN", 5, 0))
    minimum_identity_confidence: int = field(default_factory=lambda: env_int("MIN_IDENTITY_CONFIDENCE", 88, 75, 100))
    database_path: Path = field(default_factory=lambda: ROOT / os.getenv("DATABASE_FILE", "dealbot_v6.sqlite3"))

    status_web_enabled: bool = field(default_factory=lambda: env_bool("STATUS_WEB_ENABLED", True))
    status_web_port: int = field(default_factory=lambda: env_int("STATUS_WEB_PORT", 8765, 1024, 65535))
    price_chart_enabled: bool = field(default_factory=lambda: env_bool("PRICE_CHART_ENABLED", True))
    price_chart_history_days: int = field(default_factory=lambda: env_int("PRICE_CHART_HISTORY_DAYS", 90, 7, 365))

    resale_fee_percent: float = field(default_factory=lambda: env_float("RESALE_FEE_PERCENT", 13.6, 0))
    resale_fixed_fee: float = field(default_factory=lambda: env_float("RESALE_FIXED_FEE", 0.40, 0))
    resale_outbound_shipping: float = field(default_factory=lambda: env_float("RESALE_OUTBOUND_SHIPPING", 10, 0))
    resale_return_reserve_percent: float = field(default_factory=lambda: env_float("RESALE_RETURN_RESERVE_PERCENT", 3, 0))
    resale_min_profit: float = field(default_factory=lambda: env_float("RESALE_MIN_PROFIT", 40, 0))
    sold_comps_file: Path = field(default_factory=lambda: ROOT / os.getenv("SOLD_COMPS_FILE", "sold_comps.csv"))
    resale_refs: dict[int, float] = field(default_factory=lambda: {
        5000: env_float("RAM_RESALE_REFERENCE_5000", 175, 1),
        5600: env_float("RAM_RESALE_REFERENCE_5600", 190, 1),
        6000: env_float("RAM_RESALE_REFERENCE_6000", 210, 1),
        6400: env_float("RAM_RESALE_REFERENCE_6400", 225, 1),
    })

    def __post_init__(self) -> None:
        speeds = tuple(s for s in sorted(set(self.ram_speeds)) if s >= self.ram_min_speed) or (self.ram_min_speed,)
        self.ram_speeds = speeds
        capacities = tuple(sorted(set(self.ram_capacities_gb))) or (32,)
        self.ram_capacities_gb = capacities
        self.ram_queries = tuple(
            self.ram_query_template.format(capacity=c, speed=s) for c in capacities for s in speeds
        )
        self.gpu_queries = (self.gpu_query, self.gpu2_query) if self.gpu2_enabled else (self.gpu_query,)
        self.slickdeals_feed_urls = tuple(u for u in (self.slickdeals_feed_url, self.slickdeals_feed_url_2) if u)

    @property
    def gpu_precheck_ceiling(self) -> float:
        """The most permissive GPU ceiling across every tracked model, used
        only to decide whether a price looks cheap enough to double-check
        before we know which specific model a listing is."""
        return max(self.gpu_max_price, self.gpu2_max_price) if self.gpu2_enabled else self.gpu_max_price

    def gpu_price_ceiling(self, identity_label: str) -> float:
        if self.gpu2_enabled and identity_label == self.gpu2_label:
            return self.gpu2_max_price
        return self.gpu_max_price

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.discord_token:
            issues.append("DISCORD_TOKEN is missing")
        if bool(self.ebay_client_id) != bool(self.ebay_client_secret):
            issues.append("eBay requires both EBAY_CLIENT_ID and EBAY_CLIENT_SECRET")
        if any([self.reddit_client_id, self.reddit_client_secret, self.reddit_user_agent]) and not all(
            [self.reddit_client_id, self.reddit_client_secret, self.reddit_user_agent]
        ):
            issues.append("Reddit requires Client ID, Client Secret, and User Agent")
        if self.zoho_imap_enabled and not all([self.zoho_email, self.zoho_app_password]):
            issues.append("Zoho monitoring requires ZOHO_EMAIL and a ZOHO_APP_PASSWORD")
        return issues


FAST_INTERVAL_SECONDS = 300   # stores with no observed blocking so far
SLOW_INTERVAL_SECONDS = 900   # stores that have actually hit HTTP 403 in practice

STORES: tuple[StoreConfig, ...] = (
    StoreConfig(
        "Newegg",
        "https://www.newegg.com/p/pl?d={query}",
        ("newegg.com", "www.newegg.com"),
        FAST_INTERVAL_SECONDS,
    ),
    StoreConfig(
        "Best Buy page",
        "https://www.bestbuy.com/site/searchpage.jsp?st={query}",
        ("bestbuy.com", "www.bestbuy.com"),
        FAST_INTERVAL_SECONDS,
    ),
    StoreConfig(
        "B&H",
        "https://www.bhphotovideo.com/c/search?q={query}&sts=ma",
        ("bhphotovideo.com", "www.bhphotovideo.com"),
        FAST_INTERVAL_SECONDS,
    ),
    StoreConfig(
        "Micro Center",
        "https://www.microcenter.com/search/search_results.aspx?Ntt={query}",
        ("microcenter.com", "www.microcenter.com"),
        SLOW_INTERVAL_SECONDS,
    ),
    StoreConfig(
        "Adorama",
        "https://www.adorama.com/l/?searchinfo={query}",
        ("adorama.com", "www.adorama.com"),
        SLOW_INTERVAL_SECONDS,
    ),
    StoreConfig(
        "Central Computers",
        "https://www.centralcomputer.com/catalogsearch/result/?q={query}",
        ("centralcomputer.com", "www.centralcomputer.com"),
        FAST_INTERVAL_SECONDS,
    ),
    StoreConfig(
        "Antonline",
        "https://www.antonline.com/Search?q={query}",
        ("antonline.com", "www.antonline.com", "node-4.antonline.com"),
        SLOW_INTERVAL_SECONDS,
    ),
    StoreConfig(
        "Provantage",
        "https://www.provantage.com/service/searchsvcs?SEC=%7ECRAMM&QUERY={query}&SUBMIT.x=0&SUBMIT.y=0",
        ("provantage.com", "www.provantage.com"),
        SLOW_INTERVAL_SECONDS,  # no track record yet; starts cautious
    ),
    StoreConfig(
        "ShopBLT",
        "https://www.shopblt.com/search/order_id=258602080&s_max=25&t_all=1&s_all={query}&search=Search",
        ("shopblt.com", "www.shopblt.com"),
        SLOW_INTERVAL_SECONDS,  # no track record yet; starts cautious
    ),
)
