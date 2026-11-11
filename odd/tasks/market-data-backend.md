# Feature: market_data backend (MOD-02)

Objective: implement the MOD-02 market_data module (catalog, search, quotes, candles, depth, calendar, schedules, watchlists, alerts, notifications, dashboard, streaming) on top of migration 0003.
Branch: `modulo_login`. Delivery: work units committed on the feature branch. Test runner: `uv run pytest` (Hypothesis profile `max_examples=100`, `db` tests skipped without `TEST_DATABASE_URL`).

## Specs

- **S1** Symbol path validation: trim; 1-20 characters in `^[A-Za-z0-9./-]+$`; return uppercase. A rejected value is 422 `VALIDATION_ERROR`; an unknown symbol is 404 `SYMBOL_NOT_FOUND`. A symbol containing `/` must reach the validator, not a routing 404.
- **S2** Search: `q` trimmed 1-50; `page` >= 1 default 1; `page_size` 50; optional `exchange`; optional `classification` in `tradable` | `view_only`; results ordered by exact symbol match, then symbol prefix, then name contains, symbol ascending within each group; `total` is the unpaged count; `classification = tradable` exactly when the instrument's tradable flag is true.
- **S3** `GET /markets` returns the seeded exchange codes with display names (`AMEX`, `ARCA`, `BATS`, `NYSE`, `NASDAQ`, `NYSEARCA`, `OTC`).
- **S4** Catalog reload runs when the cache is empty or older than `CATALOG_MAX_AGE_HOURS`. On failure with a non-empty cache, search is answered from cache and the reload timestamp is unchanged. With an empty cache the failure is 502 `ALPACA_UNAVAILABLE` (5xx/transport) or 503 `ALPACA_RATE_LIMITED` (429).
- **S5** Asset detail is read from `GET /v1/assets/{symbol}`. Alpaca 404 returns 404 `SYMBOL_NOT_FOUND` and writes nothing. A storage failure returns 500 and leaves the cached row unchanged.
- **S6** Quote: catalog check first (404 `SYMBOL_NOT_FOUND` with no Alpaca call). A live snapshot is stored and annotated with `served_from_cache = false`. On `AlpacaUnavailable`/`AlpacaRateLimited`, a stored snapshot is returned with `as_of` = stored update timestamp, `is_stale = true`, `served_from_cache = true` and no write; without a stored snapshot the matching 502/503 is raised. The stored snapshot is unchanged on failure.
- **S7** Candles: `timeframe` in `1Min`, `5Min`, `15Min`, `1Hour`, `1Day`; `start`/`end` ISO 8601, a date-only `end` means the end of that day (UTC), `start <= end`; `page_size` 1-10000 default 1000; `page_token` passes through; bars filtered to the range inclusive, ascending timestamp, capped at page size.
- **S8** Freshness: `currency = "USD"` exactly for `us_equity` (else null); `source = "alpaca"`; `data_age_seconds = max(0, floor(now - as_of))` or null; `is_delayed` only for `delayed_sip`; `is_stale` when served from cache, age null, or age above `PRICE_STALENESS_THRESHOLD_SECONDS`; `served_from_cache` equals the flag. Candle metadata is the `currency`, `source`, `feed`, `is_delayed` subset.
- **S9** Depth: `get_latest_quote` (`GET /v2/stocks/{symbol}/quotes/latest?feed=`); no `quote` object gives empty `levels`, otherwise exactly one level from `bp`, `bs`, `ap`, `as` with missing/null keys null; `full_depth_available = false`; `as_of` from `t`. Invalid symbol 422 and unknown symbol 404 happen before any Alpaca call; 502/503 writes nothing.
- **S10** Calendar status resolution, highest precedence first: (1) Schedule_Override for that market and date; (2) Alpaca trading day opens with the market default times when both are set, otherwise Alpaca times; (3) otherwise closed (`holiday` Monday-Friday, `weekend` Saturday/Sunday). One entry per date in ascending order, at most 366 days; `GET /markets/{market_code}/status` equals that date's entry. `tz` defaults to `America/New_York`; timestamps are ISO 8601 with the offset in effect at that instant.
- **S11** `GET /markets/clock` returns `{is_open, next_open, next_close, timestamp, time_zone}` from Alpaca's clock, converted to `tz`.
- **S12** Schedule admin: `PUT`/`DELETE /admin/markets/{market_code}/default-schedule`, `GET`/`POST /admin/markets/{market_code}/schedule-overrides`, `PUT`/`DELETE /admin/markets/{market_code}/schedule-overrides/{override_id}` with `admin:markets`. A non-closed override requires both times and `close_time > open_time`; a default schedule requires both times and `close_time > open_time`; only one override per market and date (409 `OVERRIDE_EXISTS`); unknown market or override is 404 `NOT_FOUND`.
- **S13** Watchlists require `watchlist:manage` and premium (403 `PREMIUM_REQUIRED`). Limits: 20 watchlists per user, 50 symbols per watchlist. Duplicate symbol is 409 `SYMBOL_ALREADY_IN_WATCHLIST`; another user's watchlist is 404 `NOT_FOUND`; removing a symbol returns 200 with the updated Watchlist.
- **S14** Price alerts require `watchlist:manage` and premium. Comparators `above` / `below` / `crosses`; threshold `0 < threshold <= 999999999.99`; activate/deactivate/delete only own alerts (404 otherwise). The engine triggers at most once per alert, only while `active`, skips unavailable prices and keeps the previous evaluated price on a skip.
- **S15** Notifications: one stored in-app notification and one delivery per channel in `{in_app} ∪ {external channels enabled for that event type}`; `sent` for in_app and successful senders, `failed` for failing senders, every selected channel attempted. `GET /notifications` needs only a valid token, `page_size` 1-100 default 20.
- **S16** Dashboard: match instruments by interest (Market code or sector); fallback to `DASHBOARD_DEFAULT_SYMBOLS`; at most 10 in ascending symbol order; a missing quote keeps the instrument with null price/timestamp and `quote_unavailable = true`; a clock failure returns `market_status: null` with `market_status_unavailable: true`; `beginner` is true exactly for level `beginner`.
- **S17** Streaming registry: subscription of 1-30 catalog symbols; an invalid subscription leaves the client's accepted set unchanged; the upstream subscription equals the union of all accepted sets. `WS /ws/v1/market-feed` authenticates with the access cookie, requires `market:read`, closes with 1008 when disabled or unauthorized.
- **S18** Every new route declares its documented error statuses with `error_responses`; auth uses `require_permission` from `identity.adapters.inbound.http.deps`.
- **S19** `uv run ruff check .`, `uv run mypy src` (strict) and `uv run pytest` pass.

## Tasks

- T1 (S1, S19) domain entities + ports + symbol validation; route: inline; status: done.
- T2 (S2, S3, S4, S5) catalog merge, search ranking, Alpaca broker client + fake, persistence tables and instrument repository, catalog/search/exchanges/asset-detail use cases; route: inline; status: done.
- T3 (S2, S18) instrument and markets routers/schemas wired in `market_data/composition.py`; route: inline; status: done.
- T4 (S6, S7, S8) freshness, quote and bars domain rules plus property tests; route: inline; status: done.
- T5 (S6, S7) Alpaca data client + fake, snapshot repository, quote and candle use cases and endpoints; route: inline; status: done.
- T6 (S9) depth mapping, use case and endpoint; route: inline; status: done.
- T7 (S10, S11, S12) schedule/calendar/timezone domain, market repository, calendar/clock/status/schedule-admin use cases and endpoints; route: inline; status: done.
- T8 (S13, S14, S15) watchlist/alert/notification/clock-watch domain, repositories, use cases, endpoints, notifier and senders; route: inline; status: done.
- T9 (S14, S15) alert engine and clock watcher jobs; route: inline; status: done.
- T10 (S16) dashboard assembly, service and endpoint; route: inline; status: done.
- T11 (S17) streaming registry, hub and WebSocket endpoint; route: inline; status: done.
- T12 (S19) validation, task checkboxes and work-unit commits; route: inline; status: done.

## Log

- L1 (user, verbatim): "Arranca, intenta completar lo más posible, corrige errores, etc"
- L2: Implemented in dependency order 12.2 -> 12.3 -> 13.x -> 14.x -> 15.x -> 17.x -> 18.x, validating with ruff, mypy and pytest after each block.
- L3: Domain properties 16-29 and 37-39 implemented as Hypothesis tests in `tests/market_data/property/`. API/unit tests in `tests/market_data/` use in-memory adapters from `tests/support/market_fakes.py`; no test reaches Alpaca or Postgres.
- L4: Verification evidence: `uv run ruff check .` clean, `uv run mypy src` clean (146 files), `uv run pytest tests/market_data` = 83 passed, full suite = 164 passed and 18 skipped without `TEST_DATABASE_URL`.
- L5: Pending by design: DB-backed Property 17 (13.7), exhaustive API tests (13.8, 14.13, 15.7, 17.9), cross-module flow (20.3), and the module checkpoints. The streaming upstream was implemented against the Alpaca WebSocket protocol but only its registry is unit-tested.
- L6: Supabase verification: pooler connection at port 5432 with `ssl=require` works; `alembic_version` is `0004_assignment_cancellation`; all 11 market tables and the seeds exist. Fixed two runtime bugs found only against real data: the 14,408-asset catalog upsert exceeded asyncpg's 32,767 parameter limit (now batched at 500 rows with a single `text[]` unlist parameter) and nullable SQL filters needed explicit casts under asyncpg. After the fix, markets, search, quote, candles, depth, calendar and clock returned real sandbox data (commit `edf8db0`).
