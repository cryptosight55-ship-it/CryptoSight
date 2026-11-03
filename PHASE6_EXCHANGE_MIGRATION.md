# Sept 2026: Migration from Binance to Bybit

After a Binance IP ban that persisted across multiple days despite
every rate-limit safeguard in this codebase working correctly (cooldown
fired, retries stopped, no hammering) -- either an extremely long
escalated penalty, or Render's shared free-tier IP catching punishment
for other tenants' traffic. Running in parallel with a 48-hour
`EXCHANGE_PAUSED=true` clean-silence test (see config/settings.py),
this migration removes the dependency on that specific exchange/IP
relationship entirely, regardless of what the pause test shows.

## Why Bybit

`ccxt`'s unified symbol convention for linear perpetuals
(`BASE/QUOTE:QUOTE`) is the same one already assumed by
`context/providers/microstructure.py` for Binance USD-M futures --
minimal code change needed there as a result. Comparable volume/liquidity
across the altcoins this app scans, solid `ccxt` support, and no history
of the blanket US-IP blocking that caused the original Frankfurt-region
fix months ago.

## What actually changed

- **`config/settings.py`**: `EXCHANGE = 'bybit'`.
- **`context/providers/microstructure.py`**: futures client switched
  from `ccxt.binanceusdm()` to `ccxt.bybit({'options': {'defaultType':
  'linear'}})` -- Bybit uses one unified exchange class with a type
  switch, rather than Binance's separate spot/usdm/coinm classes.
- **`database/models.py`**: `SignalRecord.exchange` default updated.
- **A real, separate bug found and fixed along the way**:
  `config.EXCHANGE` had never actually been used anywhere --
  `data/fetcher.py`'s `DataFetcher()` always used its own hardcoded
  default regardless of what this config said. Fixed by having
  `get_data_fetcher()` pass `config.EXCHANGE` explicitly. Also fixed:
  `SignalRecord.exchange` was never set explicitly at signal creation
  (relied entirely on the model's default, which was `"binance"` even
  while the app was already running on whatever exchange
  `DataFetcher`'s hardcoded default pointed to) -- `core/scanner.py`
  now sets it from `config.EXCHANGE` directly, so it can't go stale
  again if the exchange changes in the future.
- **User-facing/log strings** that hardcoded "Binance" (the manual-scan
  cooldown error message, the exchange-init failure cooldown message)
  updated to say "the exchange" generically, so they stay accurate
  regardless of which exchange is configured going forward.

## What's UNVERIFIED -- flagged honestly, not tested live

This was built without live network access to actually confirm Bybit's
`ccxt` responses match what the code expects:

- `fetch_funding_rate()` and `fetch_open_interest()` on
  `ccxt.bybit()` with `defaultType: 'linear'` -- assumed to return the
  same unified field names (`fundingRate`, `openInterestAmount` /
  `openInterestValue`) ccxt normalizes across exchanges. Should work
  per ccxt's unified API design, but wasn't confirmed against a real
  response.
- Whether every symbol this app scans (top 40 by volume) has a
  matching Bybit spot AND linear-perpetual listing. Not every coin
  listed on Binance is listed on Bybit or vice versa -- the top-40 list
  itself will likely look somewhat different now, since it's now
  Bybit's own volume ranking, not Binance's.

None of this should be able to crash anything -- the microstructure
provider already catches its own exceptions and returns a neutral
reading on failure (per its original design), and `get_top_coins()`
only ever returns symbols that actually exist on the configured
exchange. But some quirk in exact field names or response shape
wouldn't be caught until this actually runs. Check the first few scans'
logs after deploying for anything unexpected from
`context/providers/microstructure.py` specifically.

## Before deploying: check `EXCHANGE_PAUSED`

If the 48-hour pause test is still running, `EXCHANGE_PAUSED=true` in
Render's environment will block Bybit too -- the kill switch is
exchange-agnostic, it stops any exchange connection attempt regardless
of which one is configured. Remove that env var (or set it to `false`)
once you're ready to actually test the Bybit migration, not before.

## What did NOT change

`data/fetcher.py`'s actual fetching logic (`get_top_coins`,
`fetch_live_data`, `fetch_historical_data`, the rate-limit cooldown, the
DDoSProtection handling) was already exchange-agnostic -- it uses
`self.exchange` generically via `getattr(ccxt, exchange_name)`, no
Binance-specific assumptions in the logic itself. That's *why* this
migration was a config change plus one provider update, not a rewrite.

---

## Nov 2026 addendum: first rebuild in months broke on dependency drift

Deploying this migration was the first full Docker rebuild in a long
time, and `requirements.txt` is unpinned (`>=` only), so pip pulled
current versions of everything. Three things needed fixing before the
app would even start:

1. **`database/db.py` -- crash on import:** `ModuleNotFoundError: No
   module named 'psycopg'`. SQLAlchemy 2.1 changed the default driver for
   plain `postgresql://` URLs from psycopg2 to psycopg (v3), which isn't
   installed. Fixed by normalizing both `postgres://` and
   `postgresql://` to `postgresql+psycopg2://` explicitly.
2. **`admin/server.py` -- precautionary:** the deprecated
   `@app.on_event("startup"/"shutdown")` hooks were converted to a
   `lifespan` context manager (same behavior). Not confirmed to be
   broken yet -- the app crashed before reaching them -- but they're
   deprecated and newer Starlette/FastAPI releases may drop them.
3. **`admin/routes.py`, `api/routes.py` -- precautionary:** three legacy
   `session.query(Model).get(id)` calls replaced with
   `session.get(Model, id)`.

Items 2 and 3 couldn't be run in the build sandbox (no network, so
FastAPI/SQLAlchemy 2.1 aren't installable there) -- they're
syntax-checked only. Anything else that drifted will surface in the
Render logs after the next deploy.

**Suggested follow-up once the app is up and stable:** pin
`requirements.txt` to the exact working versions (`pip freeze` from the
running container) so a rebuild can't silently change behavior again.
