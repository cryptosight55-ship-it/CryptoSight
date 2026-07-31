# Phase 1: Structural Refactor

This document records what changed in this pass. Scope was **layout only**
— no strategy logic, signal thresholds, ML behavior, or alert content was
changed. Two exceptions, both pure hygiene rather than business logic, are
called out explicitly below.

## New layout

```
config/       settings.py (was src/config.py)
core/         types.py (new scaffold — see "Scaffolding added")
data/         fetcher.py (was src/data_fetcher.py)
exchanges/    empty — see exchanges/README.md
indicators/   features.py (was src/feature_engineer.py)
strategies/   base.py (new scaffold), ml_model/predictor.py (was src/predictor.py)
signals/      generator.py (was src/signal_generator.py)
risk/         empty — see risk/README.md
backtesting/  backtest.py (was backtest.py, already empty — 0 lines — in the original repo)
alerts/       discord_alerts.py (was src/alert_manager.py)
database/     performance_tracker.py, trade_monitor.py (was src/*),
              trade_verifier.py, winrate.py (were repo-root scripts —
              see "Reclassified" below)
dashboard/    app.py (was app.py, Streamlit)
api/          empty — see api/README.md
tests/        empty — see tests/README.md (there were no tests before)
utils/        helpers.py (was src/utils.py)
cli/          main.py (was src/main.py)
training/     auto_train_v2.py + notebooks/ (01-04*.ipynb) — the model
              training pipeline, kept separate from the serving app
legacy/       trade_scanner.py, scanner_service.py, quick_fix.py,
              fix_folders.py, tie_analyzer.py, analyze_performance.py
logs/         *.log files that were sitting at repo root
main.py       new thin wrapper — `python main.py` still works
```

## Reclassified during the move

`trade_verifier.py` and `winrate.py` were at the repo root, but they're
real dependencies of `database/trade_monitor.py` and
`database/performance_tracker.py` (not orphaned scripts), so they moved
into `database/` alongside the modules that use them.

`trade_monitor.py`'s relative imports (`from .trade_verifier import ...`,
`from .winrate import ...`) were already assuming those files lived
next to it — which was never true before this move. Co-locating them in
`database/` is what makes those imports valid for the first time.

## Import paths fixed

Every `from src.xxx import yyy` was rewritten to the new package paths
(e.g. `from config.settings import config`). This was mechanical — same
names, same objects, new locations. All internal imports were statically
verified to resolve (see below); syntax-checked with `py_compile`.
Third-party packages (`ccxt`, `talib`, `schedule`, etc.) aren't installed
in this sandbox, so full runtime import wasn't possible here — recommend
running `python -c "import cli.main"` etc. in your actual environment
with dependencies installed as a final check.

## The two non-cosmetic fixes made during the move

Both are config/security hygiene, not strategy behavior:

1. **`config/settings.py`**: the dead duplicate `ensure_directories` /
   `setup_logging` block that lived at module level (outside the `Config`
   class, with a stray `@classmethod` decorator that made it inert) was
   merged into the one real `Config` class. It never executed before, so
   this changes nothing at runtime.
2. **`config/settings.py`**: the Discord webhook URL was hardcoded and
   committed to git history. It now reads from `os.getenv("DISCORD_WEBHOOK")`
   — `.env.example` already had the right placeholder, the code just
   wasn't reading it. **Action needed on your side: treat the old webhook
   as leaked and regenerate it in Discord.**

Everything else — the "EMERGENCY FIX" OR-logic in `signals/generator.py`,
the `long_bias_multiplier = 1.8` in `strategies/ml_model/predictor.py`,
the missing `models/latest_model.pkl`, the unused/duplicate `ccxt.binance()`
client in `database/trade_verifier.py` — was left exactly as it was. Those
are logic changes and belong to the next phase.

## Scaffolding added (not wired into anything yet)

- `core/types.py`: `StrategyResult` dataclass + `SignalDirection` enum —
  the standardized return shape the brief's "Strategy System" section
  asks for.
- `strategies/base.py`: `Strategy` ABC with the `analyze(symbol, timeframe,
  candles)` contract.

Nothing calls these yet. `signals/generator.py` still runs its original,
untouched logic. These exist so the next phase (building independent
strategy plugins and a real aggregator) has an agreed contract instead of
each strategy inventing its own shape.

## Deliberately left alone

- `legacy/*`: six scripts that were already broken or orphaned in the
  original repo (broken imports, or simply never called from any
  entrypoint — confirmed by grepping the whole codebase for references to
  each). Moved out of the way so they don't get mistaken for live code,
  but not fixed or deleted. `legacy/analyze_performance.py` still has
  `from src...` imports — left as-is since it's not part of the running
  system.
- `training/*`: the notebook-based training pipeline. Not touched beyond
  the move — it's a separate concern from the serving app and out of
  scope for this pass.
- `backtesting/backtest.py`: was a 0-byte file in the original repo.
  Still is. Real backtesting engine is future work per the roadmap.

## Verification done

- `py_compile` on every migrated file: clean.
- Static AST check confirming every internal `from <our-package> import`
  resolves to an actual file in the new tree: clean, 0 errors.
- Full runtime import wasn't possible in this sandbox (no network to
  install `ccxt`/`talib`/`schedule`); do that check in your environment
  before deploying.

## Suggested next phase

Per your earlier answer: the RandomForest model becomes one strategy
among several rather than the sole gatekeeper. Concretely that means:
wrap `strategies/ml_model/predictor.py` behind the `Strategy` interface
in `strategies/base.py`, build 2-3 independent rule-based strategies
(trend, momentum, volume are the most natural first three given what
`indicators/features.py` already computes), and build the real aggregator
in `signals/` that collects `StrategyResult`s and only fires when enough
of them agree — replacing the current single-model "emergency" OR-logic.
That also directly fixes the missing-model-file problem, since the system
would degrade gracefully instead of hard-depending on one `.pkl`.
