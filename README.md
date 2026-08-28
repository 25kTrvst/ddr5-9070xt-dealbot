# DDR5 + RX 9070 XT DealBot V6

V6 is a clean, separate rebuild focused on speed **and** product identity. It never changes your V5.1 folder.

## What changed

- Official eBay and Best Buy API lanes run every 60 seconds when credentials are present.
- Reddit, Slickdeals RSS, and optional Zoho Mail act only as discovery leads. A retailer/API must verify the real product page before an alert.
- Every verified URL/SKU/UPC/model is saved to SQLite and targeted for recheck every 2 minutes. API watchlists rotate in small batches so a large list cannot exceed the provider's daily quota.
- Each broad retailer search runs independently every 10 minutes. A 403/429 causes only that store to wait a random 30–60 minutes.
- Stores run in parallel, with at most two active requests per store.
- Strict gates reject systems, adapters, upgrade services, bundles, sponsored prices, open-box/used items, SODIMMs, DDR5 below 5000 MT/s, and RX 9070 GRE.
- Extremely cheap first sightings are quarantined until the same listing is observed again or a second source corroborates the exact model and price.
- First observations cannot be called “insane.” `WAIT / WATCH` results stay silent and enter the watchlist; Discord alerts are reserved for a later verified `BUY`, a real price drop, or confirmed resale margin.

## Setup

Use `install_and_start.bat` once. It installs Playwright and Chromium automatically. Use `start_bot.bat` afterward. Windows Firewall does not need inbound/public access for this outbound-only bot; if prompted for the headless browser, Cancel is fine.

Copy `.env.example` to `.env` if migration did not find your V5 settings. Keep `.env` private.

### Optional discovery

- **Reddit:** approved Data API Client ID, Client Secret, and a specific User Agent. Configure multiple communities with `REDDIT_SUBREDDITS`.
- **Slickdeals:** create an RSS/search alert feed and paste its URL into `SLICKDEALS_FEED_URL`. V6 does not scrape Slickdeals pages.
- **Zoho:** enable IMAP in Zoho, create an app password, and set `ZOHO_IMAP_ENABLED=true`. V6 reads unread deal emails for links but does not store email bodies.
- **Micro Center:** set `MICROCENTER_STORE_ID` for location-specific pages. A ZIP field is included for future store endpoints.

## Resale math and sold prices

V6 never pretends current eBay asking prices are sold prices. General access to eBay's historical Marketplace Insights/sold-data APIs is restricted. If you have authorized sold records, copy `sold_comps.example.csv` to `sold_comps.csv` and add at least three sales for the exact `model_key` shown in Discord. Net profit subtracts purchase tax, inbound shipping, marketplace fees, fixed fee, outbound shipping, and a return-risk reserve. Without three exact-model sold records, the bot does not claim a resale profit.

## Commands

- `/status` — schedules, connections, source errors and cooldowns.
- `/scanram`, `/scangpu` — one optional manual scan. Automatic scanning already runs.
- `/ignore URL` — permanently suppress one exact listing URL.
- `/watch` — explains the automatic SKU watchlist.

## Accuracy and blocking

No software can guarantee that retailers will not block automated requests. V6 uses official APIs where available, slow store-search intervals, low per-store concurrency, jitter, and long backoff. Playwright is a rendering fallback—not a CAPTCHA or anti-bot bypass. A challenged store is paused while all other lanes continue.

Run tests with `python -m pytest -q`. The included regression suite covers both false eBay DDR5 alerts that appeared in V5.1.

## Trading alert bot (`tradingbot/`)

A separate, alerts-only watcher for crypto, memecoins, and stocks — it never places
orders, it only tells you when something moves. It lives next to the dealbot and does
not touch any dealbot files. Run it with:

```
python trading_app.py
```

It reads public, keyless market data:

- **Crypto** via [ccxt](https://github.com/ccxt/ccxt) (100+ exchanges unified; defaults to Kraken's public ticker API).
- **Stocks** via `yfinance` (Yahoo Finance).
- **Memecoins / DEX tokens** via the [Dexscreener](https://docs.dexscreener.com/api/reference) public API.

Configure it with the same root `.env` file, all optional (sensible defaults apply):

```
TRADING_DISCORD_WEBHOOK_URL=          # Discord webhook URL; if unset, alerts just print to the console
CRYPTO_EXCHANGE=kraken                # any ccxt exchange id
CRYPTO_SYMBOLS=BTC/USD,ETH/USD,SOL/USD
CRYPTO_MOVE_PERCENT=3
CRYPTO_INTERVAL_SECONDS=60
STOCK_SYMBOLS=AAPL,TSLA,NVDA
STOCK_MOVE_PERCENT=3
STOCK_INTERVAL_SECONDS=300
MEMECOIN_ADDRESSES=                   # comma-separated chain:tokenAddress, e.g. solana:So11111111111111111111111111111111111111112
MEMECOIN_MOVE_PERCENT=8
MEMECOIN_INTERVAL_SECONDS=60
```

Each watcher polls its symbols on its own interval and fires an alert when a symbol
moves by at least its configured percent since the last check. To create a Discord
webhook URL: Server Settings → Integrations → Webhooks → New Webhook → Copy URL.

This is a starting point, not financial advice — verify any signal yourself before
trading on it.
