# Sept 2026: First Data-Driven Recalibration

After a full month of live scanning (per the "run for a month, gather
volume" plan), the learning pipeline built in Phase 4 produced its first
genuinely actionable verdict. This is the first time any core signal
logic changed based on real evidence rather than initial assumptions.

## What the data showed

Nightly review (`learning/nightly_review.py`), ~60 resolved signals,
13 groups with enough samples (8-31 each):

| Regime | trend | momentum | volatility |
|---|---|---|---|
| trending | 14% (n=28) | 10% (n=29) | 13% (n=31) |
| high_volatility | 12% (n=17) | 6% (n=17) | 11% (n=19) |
| ranging | 28% (n=18) | 27% (n=22) | 26% (n=19) |
| low_volatility | 23% (n=13) | 29% (n=14) | 29% (n=14) |

Two findings, both acted on:

1. **Every regime was below the 33% win rate needed to break even** at
   the original 1:2 risk/reward (1.5x ATR stop, 3x ATR target) — some
   badly (6-14% in trending/high-volatility conditions).
2. **A consistent ~2x gap between regimes**: every strategy performed
   roughly twice as well in ranging/low-volatility conditions as in
   trending/high-volatility ones — the opposite of what
   `regime/detector.py`'s original multipliers assumed
   ("trend strategies excel during strong directional markets" was the
   literal assumption baked in back in Phase 4a; the data says the
   opposite for this system).

## What changed

- **`regime/detector.py`**: `DEFAULT_REGIME_MULTIPLIERS` replaced with
  values derived from each regime's win rate relative to that
  strategy's own average, clamped to [0.6, 1.3] to stay a nudge rather
  than a dominant force. Full source numbers and the exact formula are
  in the file's comments.
- **`signals/aggregator.py`**: `ATR_TARGET_MULTIPLE` reduced from 3.0
  to 2.0 (R:R from 2:1 to ~1.33:1). This is explicitly a **hypothesis,
  not a proven fix** — the breakeven bar this creates (43%) is actually
  *higher* than before (33%), on the bet that a meaningfully closer
  target raises the real win rate by more than the bar itself rises.
  There's no historical data at this exact ratio yet, only at the old
  one. Needs another stretch of resolved signals to validate.

## Why weight-tuning alone couldn't fix this

Worth recording since it's a real structural finding: `momentum` and
`volatility` had already been cut to the configured floor (0.1) by
`ai/accuracy_reviewer.py`, `trend` was at 0.106. The bounded
weight-adjustment mechanism had done everything it structurally can — a
strategy at any weight above zero still counts toward the "3 of 5 must
agree" gate, so down-weighting can shrink a strategy's influence on the
confidence *number* but can never stop it from helping a signal *fire*
in the first place. Fixing the actual underperformance needed changing
the shared signal logic itself (regime weighting, risk/reward), not
just continuing to turn down a dial that had already hit its limit.

## What to watch next

Once enough signals resolve under the new `ATR_TARGET_MULTIPLE=2.0`,
check the nightly review again:
- If win rates rise enough to clear ~43%, the hypothesis holds — keep it.
- If win rates stay roughly the same as before (still ~10-29%), the
  problem probably isn't target distance at all, and the higher
  breakeven bar just made things worse — worth reverting and looking at
  a different lever (e.g. the strategies' actual directional logic,
  not just the payoff structure around it).
