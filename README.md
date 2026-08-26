# DDR5 + RX 9070 XT DealBot V6

V6 is a clean, separate rebuild focused on speed **and** product identity. It never changes your V5.1 folder.

## What changed

- RAM discovery now runs one search per speed tier (`RAM_SPEEDS`, default `5000,5200,5600,6000,6400`) **and** per capacity (`RAM_CAPACITIES_GB`, default `16,32`) against eBay and every scraped retailer, instead of one fixed query. Each added capacity multiplies the number of searches, so only add capacities you actually want tracked. Customize the wording with `RAM_QUERY_TEMPLATE` (default `"{capacity}GB DDR5 desktop memory {speed}MHz"`). Note `RAM_MAX_PRICE` and friends are one price ceiling shared across every capacity you track — 16GB and 32GB kits are close enough in price that $200 covers both fine, but don't add a much pricier capacity (like 64GB) without also loosening the ceiling.
- The recognized RAM brand/sub-brand list (used to help confirm a listing is a real standalone kit) now covers far more manufacturers and product lines — Viper, Vengeance, Fury, Renegade, T-Force, HyperX, ROG Strix, Aorus, and more, not just the top handful.
- Restock alerts: an exact listing that goes out of stock and later comes back — even at the *same* price — now alerts. Previously the bot only alerted on a new listing or a $5+ price drop, so a same-price restock was silently missed. Going out of stock itself never alerts (nothing to buy), only the return. eBay/Best Buy watch checks record "out of stock" themselves when the API stops returning the item, since those APIs simply omit unavailable listings instead of flagging them.
- Every Discord alert now includes a small price-history chart (`PRICE_CHART_ENABLED`, `PRICE_CHART_HISTORY_DAYS` default 90) built from every store that has seen the exact model, once there are at least two price points to plot.
- A local status webpage at `http://localhost:8765` (`STATUS_WEB_ENABLED`, `STATUS_WEB_PORT`) mirrors `/status` and auto-refreshes every 5 seconds, so you can leave a browser tab open instead of running the Discord command each time.
- A second GPU model can be tracked alongside the RX 9070 XT via `GPU2_ENABLED=true`, `GPU2_LABEL`, `GPU2_QUERY`, and its own `GPU2_MAX_PRICE` ceiling — each card gets compared against its own price, not a shared one.
- A preloaded catalog (`dealbot/catalog.py`) ships real manufacturer part numbers for common RX 9070 XT board-partner cards and 32GB DDR5 kits at each speed tier. A match gives a deterministic cross-store `model_key` and raises identity confidence — see the "Catalog" note below for why UPCs ship blank.
- A genuine cross-store market baseline and 30-day low: every verified price observation is now compared against every other store/source that has seen the exact same model (via the catalog/MPN-derived `model_key`), not just the single listing being scored. Discord alerts show the N-source baseline and the true all-store 30-day low — N is distinct stores, not raw price checks (three checks on one Newegg listing reads as 1 source, not 3).
- Each scraped store now has its own parser (`dealbot/sources/parsers/`) with tailored link discovery and price selectors, instead of one generic scraper handling every site the same way.
- One Playwright Chromium process (`dealbot/browser.py`) is launched once and reused for every JS-rendering fallback fetch, instead of paying browser-startup cost per request; each fetch still gets an isolated browser context.
- Extremely cheap, uncorroborated prices are no longer hidden. They're posted as a clearly labeled `⚠️ UNCONFIRMED — VERIFY BEFORE BUYING` alert (red embed) instead of being silently quarantined, so you get the heads-up but know to double-check before buying.
- Every background scanner is supervised: if one crashes from a bug, it's logged, an alert is posted to `#dealbot-ops` (`OPS_CHANNEL_NAME`, falls back to the GPU channel or a DM), and the scanner restarts automatically. A scanner can no longer die silently.
- Official eBay and Best Buy API lanes run every 60 seconds when credentials are present.
- Reddit, Slickdeals RSS, and optional Zoho Mail act only as discovery leads. A retailer/API must verify the real product page before an alert.
- Every verified URL/SKU/UPC/model is saved to SQLite and targeted for recheck every 2 minutes. API watchlists rotate in small batches so a large list cannot exceed the provider's daily quota.
- Each broad retailer search runs independently on its own schedule (`STORES` in `dealbot/config.py`) — 3 minutes for Newegg (fastest; no observed blocking), 5 minutes for other stores that haven't shown blocking (Best Buy page, B&H, Central Computers), and 15 minutes for stores that have actually hit HTTP 403 (Micro Center, Adorama, Antonline), have no track record yet (Provantage, ShopBLT), or are known to be heavily bot-protected (Walmart). A 403/429 causes only that store to additionally wait a random 30–60 minutes on top of its own schedule.
- Stores run in parallel, with at most two active requests per store.
- Strict gates reject systems, adapters, upgrade services, bundles, sponsored prices, open-box/used items, SODIMMs, DDR5 below 5000 MT/s, and RX 9070 GRE.
- Extremely cheap first sightings are flagged `⚠️ UNCONFIRMED` and alerted right away rather than hidden, until the same listing is observed again or a second source corroborates the exact model and price.
- A first sighting can now alert immediately as `BUY` if the price and identity confidence are strong enough — it no longer waits for a second scan to confirm the same listing first. `WAIT / WATCH` results still stay silent and enter the watchlist; Discord alerts fire for a `BUY`, a real price drop, a restock, an unconfirmed-price warning, or confirmed resale margin.

## Fixes from an independent review

A second opinion (via ChatGPT) on this codebase turned up real issues, since fixed:

- **eBay quota risk**: searching every RAM speed/capacity combo every single 60-second cycle (10 combos by default) meant up to ~15,840 Browse API calls/day, well past eBay's default 5,000/day limit. Both eBay and every scraped retailer now *rotate* through their configured combos one at a time per cycle instead of firing all of them every cycle — full coverage still happens over successive cycles, just spread out (eBay is now ~2,880 calls/day at defaults).
- **Store backoff was silently disabled**: a fix for "one slow page shouldn't kill the whole scan" accidentally also caught `BlockedSource` (403/429), since it's a subtype of the general per-page error — meaning an actual block never reached the engine's 30–60 minute cooldown. Blocks now propagate correctly again (verified with a regression test).
- **False restock risk**: a single not-found result (a momentary API hiccup, an empty response) could get recorded as "out of stock," and the next successful check would then look like a restock that never really happened. Now requires two consecutive not-found results before committing to "out of stock."
- **"N sources" was actually "N price checks"**: the market baseline's source count was counting raw observation rows, so three checks on one Newegg listing could display as "3 sources." Now counts distinct stores.
- **Total scraped-request volume**: the same rotation fix above also cuts scraped-store request volume roughly 10x versus firing every speed/capacity combo every cycle, which was pushing total daily requests well past what the per-store speed tiers were designed to keep safe.
- **Antonline's link matching was too loose** (effectively matched almost any link on the page) and **Provantage's search URL may be RAM-category-locked** (its `SEC=~CRAMM` parameter looks like a category code), which would silently return nothing for GPU searches on that store. Antonline's matching is tightened (still unverified — send a real example link if it stays empty); Provantage needs a GPU-specific search URL to fix properly — see below.
- **Version drift**: the scraper's User-Agent string and the package version were still hardcoded to `6.0.0` regardless of the actual release. Now centralized in `dealbot/__init__.py`.

## Setup

Use `install_and_start.bat` once. It installs Playwright and Chromium automatically. Use `start_bot.bat` afterward. Windows Firewall does not need inbound/public access for this outbound-only bot; if prompted for the headless browser, Cancel is fine.

Copy `.env.example` to `.env` if migration did not find your V5 settings. Keep `.env` private.

### Optional discovery

- **Reddit:** approved Data API Client ID, Client Secret, and a specific User Agent. Configure multiple communities with `REDDIT_SUBREDDITS`.
- **Slickdeals:** create an RSS/search alert feed and paste its URL into `SLICKDEALS_FEED_URL`; a second feed (e.g. a GPU search) can go in `SLICKDEALS_FEED_URL_2` — both are polled and merged, since each item's own title decides whether it's a RAM or GPU lead. V6 does not scrape Slickdeals pages.
- **Zoho:** enable IMAP in Zoho, create an app password, and set `ZOHO_IMAP_ENABLED=true`. V6 reads unread deal emails for links but does not store email bodies.
- **Micro Center:** set `MICROCENTER_STORE_ID` for location-specific pages. A ZIP field is included for future store endpoints.

### Operational alerts

Create a `#dealbot-ops` channel (or set `OPS_CHANNEL_NAME` to an existing one) so scanner-crash notifications have somewhere to go. If that channel doesn't exist, crash alerts fall back to the GPU channel, then to a DM to `PING_USER_ID`.

## Catalog

`dealbot/catalog.py` ships real manufacturer part numbers (MPNs) for common RX 9070 XT cards and 32GB DDR5 kits. UPCs are intentionally left blank: they vary by region and revision, and a wrong one would falsely "confirm" the wrong product — worse than not matching at all. Add a UPC only once you've personally verified it against a retailer or manufacturer page for your region. Add new SKUs to `GPU_CATALOG`/`RAM_CATALOG` as new board-partner models or kits ship.

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
