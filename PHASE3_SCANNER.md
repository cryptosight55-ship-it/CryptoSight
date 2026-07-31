# Phase 3: The Actual Multi-Strategy Scanner

This is the first pass that touches real signal-generation logic. Everything
before this (phases 1-2) was structure and infrastructure around an empty
pipeline. This phase makes the pipeline real.

## What runs now, every hour on the hour

1. **`core/scanner.py: run_scan()`** — fetches the top 40 USDT pairs by 24h
   volume on Binance (`data/fetcher.py: get_top_coins()`, already existed,
   reused as-is), and for each one:
2. **`signals/aggregator.py: aggregate()`** — runs all 5 strategies in
   `ALL_STRATEGIES` against 500 recent 1h candles, requires **at least 3 to
   agree on the same direction**, weights their confidence by each
   strategy's `StrategyWeight.weight` (the same weights the AI reviewer
   tunes), and computes entry/stop-loss/take-profit from ATR (1.5x ATR
   stop, 3x ATR target — a 1:2 risk/reward baked in).
3. If a signal fires: **`backtesting/quick_backtest.py`** replays the same
   `aggregate()` logic over up to ~40 sampled points across the available
   history, checking whether stop-loss or take-profit would have been hit
   first each time, and attaches a historical win-rate to the signal.
4. The signal is saved to `SignalRecord`, sent to Discord, and (if
   `OPENROUTER_API_KEY` is set) given a plain-language AI explanation.

You can also trigger a scan on demand from the dashboard ("Run scan now")
or `POST /api/scan/run` — useful for testing without waiting for the top
of the hour.

## The 5 strategies

- **`strategies/rules/trend.py`** — EMA20 vs EMA50, confirmed by ADX ≥ 20
  (so it doesn't fire on a choppy/ranging market).
- **`strategies/rules/momentum.py`** — MACD cross direction, confirmed by
  RSI not being at an extreme.
- **`strategies/rules/volume.py`** — volume ≥1.5x its 20-period average,
  confirmed by price direction and OBV trend agreeing.
- **`strategies/rules/volatility.py`** — Bollinger Band breakout; also
  computes ATR, which the aggregator uses for stop/target sizing
  regardless of which strategies actually agreed.
- **`strategies/ml_model/predictor_strategy.py`** — wraps the *original*
  RandomForest model (`indicators/features.py` + the predictor, both
  byte-for-byte unchanged) behind the `Strategy` interface. **Because
  there's still no `models/latest_model.pkl` in this repo**, this one
  will return HOLD every scan until you deploy an actual model file —
  gracefully, not by crashing. Until then, signals only need 3-of-4 from
  the rule-based strategies to fire, since the 5th can never vote.

## Known costs and limits — read before you assume something's broken

- **A manual "Run scan now" can take 30-90+ seconds.** 40 symbols, each
  needing a network round-trip to Binance plus (for anything that fires)
  up to ~40 backtest iterations. It's synchronous today — the button will
  just sit on its spinner, that's expected, not a hang. If this becomes
  annoying, the fix is running scans as a background task instead of
  inline in the request — flag it if you want that next.
- **The in-process hourly scheduler** (`APScheduler` inside `admin/server.py`)
  is the simplest option and fine at this scale, but it means a slow or
  stuck scan runs in the same process serving the admin panel. If that
  ever becomes a problem, move `run_scan()` to a separate Render Cron Job
  or Background Worker hitting the same Postgres/Neon database — nothing
  about `run_scan()` itself needs to change for that move.
- **The backtest is a sanity check, not a rigorous backtest engine.** It
  reuses live logic on shrinking historical windows and samples at most
  ~40 points — good enough to catch "this exact setup has been losing
  constantly," not a substitute for a real historical validation pipeline
  (that's still on the roadmap under `/backtesting`).
- **A JSON-serialization bug was caught and fixed before this shipped**:
  TA-Lib returns `numpy.float64`, not plain Python floats, and those
  aren't JSON-serializable. Every strategy now casts its own
  confidence/score to native `float`, and `core/scanner.py` casts again
  defensively when building the metadata that gets saved — so a future
  strategy that forgets this can't crash a signal save.
- **Minor, not urgent**: `quick_backtest()` calls `aggregate()` up to ~40
  times per firing symbol, and each call re-queries `StrategyWeight` from
  the database. Works fine, just does more DB round-trips than strictly
  necessary — worth caching the weights for the duration of one backtest
  pass if scans start feeling slow.

## What's still open

- No real ML model file deployed (see above) — the 5th strategy is
  currently a permanent HOLD.
- `risk/` is still empty — position sizing, max exposure, and the rest of
  the brief's risk-management list aren't built. ATR-based stops are the
  only risk logic in place right now, folded into the aggregator itself
  rather than a separate module.
- `backtesting/` has the quick per-signal sanity check but not a
  standalone historical backtest report/UI.
