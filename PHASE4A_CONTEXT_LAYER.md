# Phase 4a: Outcome Resolution, Regime Detection, Microstructure Context

Scoped exactly as agreed: outcome resolution, regime detection, one free
context provider (microstructure), the `AnalystOpinion` schema, and
decision-engine-v2 math. No paid data sources touched, per your call to
avoid spending anything at this stage.

## What changed in existing behavior — and what didn't

**The 3-of-5 technical gate is byte-for-byte unchanged.** A signal still
requires at least 3 of the 5 technical strategies to agree, exactly as
in Phase 3. Regime and context layer on top of that gate; neither can
create a signal or flip its direction on their own yet. That's a
deliberate, conservative choice — there's no track record yet to justify
giving a brand-new, unvalidated layer that much power. `AnalystOpinion`
is additive too — the 5 existing strategies still return `StrategyResult`
unchanged; nothing was forced to migrate.

**What actually changed the confidence number:**
- Regime multiplier (static, see `regime/detector.py`) applied to each
  strategy's weight before computing weighted confidence.
- Context adjustment (bounded to ±15%, see
  `CONTEXT_MAX_ADJUSTMENT` in `signals/aggregator.py`) applied after the
  gate already decided direction.

## New: the outcome resolver — this is the important one

`learning/outcome_resolver.py` closes the gap flagged a few messages
back: nothing was ever moving a `SignalRecord` from `pending` to
`win`/`loss`, which meant `ai/accuracy_reviewer.py` was structurally
starved — it only considers `status in ("win", "loss")`. Runs on a
schedule (15 minutes past every hour, offset from the scan job) and
manually from the dashboard ("Resolve pending signals now"). A signal
that hasn't hit stop-loss or take-profit within `TRADE_TIMEOUT_HOURS`
(48h, already in `config/settings.py`) gets marked `expired` with a
mark-to-market P&L rather than left pending forever.

**This is what actually unlocks the AI weight tuning you asked for
originally** — it had nothing to review until now.

## New: market regime detection

`regime/detector.py`. Deliberately simple: ADX ≥25 for
trending-vs-ranging, realized-volatility percentile for
high/low-volatility. Regimes are non-exclusive labels (a market can be
trending AND high-vol). The per-(strategy, regime) multipliers are a
**static dict, not database-backed or AI-tunable yet** — there's no
learning-loop mechanism in place to justify dynamically tuning them
until the nightly review job exists (Phase 4b). Making it DB-backed now
would just be an admin-editable table nothing ever actually adjusts.

## New: the microstructure context provider

`context/providers/microstructure.py`. Covers funding rate, open
interest (via a separate `ccxt.binanceusdm()` client — these are
perpetual-futures concepts, not spot), and spot order-book imbalance.
All free, no new API keys needed.

**Explicitly NOT covered**: liquidation clusters. Binance only exposes
those through a real-time websocket stream, not a REST endpoint with
history — there's no websocket infrastructure in this app, so this is
honestly scoped out rather than faked with something weaker. Worth
revisiting if a websocket listener ever gets built for other reasons.

**A rate-limit-conscious design choice, given the ban earlier this
build**: context data is only fetched for symbols that already cleared
the technical gate, not all 40 every scan. `core/scanner.py` now runs
`aggregate()` twice for a firing symbol — once with no context (cheap,
no extra API calls, decides *whether* a signal exists) and once with
context (only for the handful that already qualified). Same pattern
`quick_backtest` already used for the same reason.

## What's visible now

- Dashboard: new "Signal outcomes" card with a manual resolve button.
- `SignalRecord.metadata_json` now includes `regime`, `base_confidence`
  (pre-context), and `context_evidence` — visible via the API
  (`/api/signals`) even though there's no dedicated admin UI for
  browsing it yet (that's the observability work noted as a follow-up
  in the roadmap doc, not done here).
- `POST /api/outcomes/resolve` and the matching admin route.

## What's still ahead (per the roadmap doc)

- Phase 4b, remaining piece: nightly review job producing `LearnedInsight`
  records from grouped win-rate statistics -- deliberately held back until
  there's real resolved-signal history to analyze (see below). The two
  free context providers (Fear & Greed, crypto news) are done -- see
  `PHASE4B_FREE_PROVIDERS.md`.
- Phase 4c: `ai_briefing` synthesis step, and a decision point on a
  macro-calendar data source.
- Phase 4d: on-chain and social providers — gated on picking (and
  paying for) a source, per your call to avoid that for now.
