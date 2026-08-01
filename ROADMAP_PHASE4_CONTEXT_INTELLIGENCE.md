# Phase 4+: Context Intelligence & Continuous Learning — Roadmap

This is a design document, not a diff. Nothing in here is implemented yet.
Per your instruction, this preserves the existing architecture
(technical strategies → aggregator → backtest → database → Discord → AI
explanation, all shipped in phases 1-3) and adds to it in layers, rather
than replacing it.

---

## 0. Principles carried over from the existing architecture

These held up well through phases 1-3 and should keep holding:

- **Independent providers with a shared interface**, not one monolithic
  service — exactly how `strategies/base.py`'s `Strategy` interface
  already works. The Context Intelligence Layer is the same pattern
  applied to a new category of input.
- **Deterministic, auditable math for the actual decision; AI for
  synthesis and explanation, not for the core weighting.** This is
  already how the codebase is split: `signals/aggregator.py` does plain
  arithmetic, `ai/signal_explainer.py` narrates the result afterward.
  Phase 4+ keeps that split even as more goes into the aggregator —
  the weighted-confidence formula stays reproducible and debuggable; an
  LLM call synthesizes the final human-readable rationale on top of it,
  it doesn't compute the confidence number itself.
- **Every automated adjustment gets bounded guardrails and an audit
  log**, same as `ai/accuracy_reviewer.py` already does for strategy
  weights (min sample size, max step size, clamped range, reasoning
  recorded). The learning pipeline below extends this pattern rather
  than inventing a new one.
- **Graceful degradation over hard dependency.** The ML strategy
  already demonstrates this — it returns HOLD instead of crashing when
  no model file exists. Every new context provider should do the same
  when its data source is unavailable, rate-limited, or unconfigured:
  return a neutral/low-confidence reading, never block the pipeline.

---

## 1. Context Intelligence Layer

### 1.1 Interface

Mirrors `strategies/base.py`'s `Strategy` / `StrategyResult` split:

```python
# context/base.py
class ContextProvider(ABC):
    name: str
    category: str  # "macro" | "geopolitical" | "crypto_news" |
                    # "sentiment" | "onchain" | "microstructure"

    @abstractmethod
    def fetch(self, symbol: Optional[str] = None) -> "ContextSignal":
        """symbol=None for global/macro providers; a symbol for
        per-asset providers (on-chain, microstructure, some news)."""

# context/types.py
@dataclass
class ContextSignal:
    provider_name: str
    category: str
    direction: SignalDirection      # BUY/SELL/HOLD-style bias, or NEUTRAL
    confidence: float               # 0-1, the provider's own confidence
    evidence: List[str]             # concrete facts, not vibes --
                                     # "CPI printed 3.2% vs 3.4% consensus"
    reasoning: str                  # one paragraph, provider's own words
    staleness_seconds: float        # how old is this reading
    raw: Dict[str, Any]             # source data for debugging/audit
```

### 1.2 Provider catalog and realistic cost/complexity

This is the part worth being honest about up front — "gather macro,
geopolitical, sentiment, on-chain, and microstructure data" spans wildly
different levels of effort and cost. Rough map (verify current
pricing/availability at build time, this shifts):

| Category | Example source | Cost | Notes |
|---|---|---|---|
| **Microstructure** | Funding rates, open interest, liquidations, order-book imbalance | **Free** — already-available Binance/Bybit endpoints via `ccxt` | Zero new integration risk. Build first. |
| **Sentiment (Fear & Greed)** | alternative.me API | Free | Simple, stable, single number + classification |
| **Crypto news** | CryptoPanic free tier, exchange/project RSS feeds | Free–cheap | Raw headlines; needs an AI extraction step to turn "headline" into structured `ContextSignal` |
| **On-chain (ETF flows)** | Farside Investors-style public data | Free, semi-official | Scraping/parsing risk, not an official API |
| **Sentiment (Google Trends)** | `pytrends` (unofficial) | Free but fragile | Google can break this without notice; treat as best-effort |
| **Macro calendar** (FOMC/CPI/PPI/GDP/employment with consensus-vs-actual) | FRED (raw data, free) vs. a commercial econ calendar API (surprise-vs-consensus) | Free for raw series, **paid** for calendar-with-consensus | This is a real decision point — see §10 |
| **On-chain (whale activity, exchange flows, stablecoin flows)** | Glassnode / CryptoQuant / Nansen | **Paid**, meaningfully so | Real decision point |
| **Social (X/Twitter)** | X API | **Paid**, and pricing/access has shifted multiple times | Real decision point; Reddit's free tier is more usable if this category matters most |
| **Geopolitical** | No good structured feed exists | Free news APIs + heavy AI summarization | Realistically the weakest-signal category to automate; starts as "AI reads headlines," not a real feed |

**Recommendation**: build the free, already-connected category
(microstructure) and the free/stable categories (Fear & Greed, crypto
news) first. Treat macro-calendar-with-consensus, on-chain, and social
as later phases gated on an explicit decision to pay for a data source
— don't build against them speculatively.

### 1.3 Aggregation

A `ContextAggregator` runs once per scan (not per-symbol for
global/macro providers — FOMC context doesn't change symbol to symbol)
and produces a **market context snapshot**: the set of all
`ContextSignal`s from that scan cycle, saved alongside whatever signals
fire, so the learning pipeline can later ask "what was the context when
this trade won or lost."

---

## 2. Structured analyst output (replacing simple votes)

`core/types.py`'s `StrategyResult` grows into a richer `AnalystOpinion`
— backward compatible, existing strategies just leave the new fields at
sensible defaults:

```python
@dataclass
class AnalystOpinion:
    source_name: str
    source_type: str  # "technical" | "context" | "chief_agent"
    direction: SignalDirection
    confidence: float
    evidence: List[str]
    reasoning: str
    risks: List[str] = field(default_factory=list)
    invalidation_conditions: List[str] = field(default_factory=list)
    preferred_entry_style: Optional[str] = None   # "market" | "limit on pullback" | ...
    expected_holding_time: Optional[str] = None   # "hours" | "1-3 days" | ...
```

The 5 existing strategies and the new context providers both produce
`AnalystOpinion`s. That's what makes the multi-agent evolution in §6
mostly a naming/orchestration change later, not a rebuild.

---

## 3. Market regime detection

A first pass doesn't need to be clever: ADX (already computed by
`strategies/rules/trend.py`) for trending-vs-ranging, and realized
volatility percentile (rolling std of returns vs. its own recent
history) for high-vol-vs-low-vol. Four buckets:
`TRENDING`, `RANGING`, `HIGH_VOLATILITY`, `LOW_VOLATILITY` (not
mutually exclusive — a market can be trending AND high-vol).

This feeds a **regime multiplier** on top of the existing
`StrategyWeight`, either as a new column (`StrategyWeight` per regime)
or a small `RegimeStrategyWeight` table keyed by (strategy, regime).
Start simple: a single multiplier per (strategy, regime) pair, manually
seeded with sensible defaults ("volatility strategy weight ×1.3 in
high-vol regimes"), later tuned by the same AI-review mechanism that
already tunes base weights.

---

## 4. Decision engine v2

`signals/aggregator.py` evolves from "count votes, need 3-of-5" to
combining:

- technical `AnalystOpinion`s (weighted by `StrategyWeight × regime
  multiplier`, as today)
- context `AnalystOpinion`s (weighted by each provider's own confidence
  × a per-category weight, tunable the same way strategy weights are)
- a historical-performance prior (how has this exact strategy performed
  recently, per §5)

into one weighted confidence score. The **aggregation math stays
deterministic** (§0). What's new is the final signal gains real content
instead of just a number: `rationale`, `risks`,
`invalidation_conditions`, `preferred_entry_style`,
`expected_holding_time`, and an `ai_briefing` — a short LLM-generated
paragraph synthesizing all the structured evidence into something a
person can read in five seconds. This is `ai/signal_explainer.py`'s job
today, scaled up to take the whole opinion set as input instead of just
the technical reasons list.

---

## 5. The learning pipeline

This phase **depends on a gap I flagged earlier and haven't built yet**:
nothing currently resolves a `SignalRecord` from `pending` to
`win`/`loss`. That becomes foundational here, not optional — the whole
learning pipeline has nothing to learn from without it. Recommend
building it as the very first piece of phase 4, independent of anything
context-related.

Once outcomes resolve:

1. **Store the context snapshot with every signal** (§1.3) — extend
   `SignalRecord.metadata_json` (already a flexible JSON column) with
   the regime and the full set of `ContextSignal`s active at signal
   time, rather than a schema migration for this part.
2. **Nightly review job** (new — extends the existing pattern in
   `ai/accuracy_reviewer.py`, doesn't replace it): groups resolved
   signals by strategy × regime × notable context conditions, computes
   win rate per group, and — **only where a group has enough samples to
   mean anything** (same `AI_MIN_SAMPLES_FOR_ADJUSTMENT`-style guardrail
   already in place) — writes a `LearnedInsight` record: plain-language
   observation, the supporting stats, and a confidence level. This is
   deliberately **statistical grouping first, not ML** — with the
   signal volume this system will realistically produce early on (tens
   to low hundreds of signals a week), a model would overfit long
   before grouped win-rates would mislead you. Revisit ML once there's
   genuinely enough resolved history to justify it.
3. **Feed insights back into weights** — the same bounded-adjustment,
   audited mechanism `ai/accuracy_reviewer.py` already uses, extended to
   also consider regime-conditioned and context-conditioned performance,
   not just raw per-strategy win rate.

Guardrail worth stating explicitly: **don't let the number of
(strategy × regime × context-bucket) combinations explode.** Start with
regime alone, add one context dimension at a time, and only once each
new dimension is producing groups with real sample sizes. A learning
system that fragments its own data into slices too thin to be
statistically meaningful is worse than one that doesn't segment at all.

---

## 6. Path to a multi-agent system

Once §§1-5 exist, "Macro Analyst," "News Analyst," "Technical Analyst,"
"On-Chain Analyst," "Risk Analyst" are mostly **names for groups of
providers that already produce `AnalystOpinion`s** — Technical Analyst
= the existing 5 strategies, Macro/News/On-Chain Analyst = context
providers grouped by category, Risk Analyst = a new provider type that
looks at position sizing / correlation / regime risk rather than
direction.

The **Chief Decision Agent** is decision-engine-v2 (§4), formalized:
takes every `AnalystOpinion`, applies the deterministic weighted-math,
and (optionally, as a separate step) makes one LLM call to write the
final briefing. This is genuinely more of an **organizational
refactor** than new capability, once the underlying pieces exist —
which is exactly why it's last on this roadmap, not first.

---

## 7. New/extended schema (sketch)

- `SignalRecord`: add `regime`, `rationale`, `risks` (JSON),
  `invalidation_conditions` (JSON), `entry_style`, `holding_time_estimate`
  — additive columns, no breaking change to existing rows.
- `ContextReading` (new table): one row per `ContextSignal` captured per
  scan, linked to the signals that were live at that time — this is what
  the nightly review job queries against.
- `LearnedInsight` (new table): `description`, `supporting_stats` (JSON),
  `confidence`, `sample_size`, `created_at` — a human-readable, auditable
  record of what the nightly review concluded, browsable in the admin
  panel the same way `WeightAdjustmentLog` already is.
- `RegimeStrategyWeight` (new table, or columns on `StrategyWeight`):
  per-(strategy, regime) multiplier.

## 8. New folders

```
context/
  base.py          # ContextProvider interface, ContextSignal type
  aggregator.py     # runs all providers, builds a snapshot
  providers/
    microstructure.py   # phase 4a -- free, via existing exchange access
    fear_greed.py        # phase 4b -- free
    crypto_news.py        # phase 4b -- free/cheap + AI extraction
    macro_calendar.py      # phase 4c -- decision point, see §10
    onchain.py               # phase 4d -- decision point
    social.py                 # phase 4d -- decision point
regime/
  detector.py       # market regime classification
learning/
  outcome_resolver.py   # resolves pending SignalRecords to win/loss
  nightly_review.py       # the grouped-statistics review job
agents/                     # phase 5+, mostly organizational
  chief_decision_agent.py
```

---

## 9. Observability

Every new layer should be visible in the admin panel the same way
strategy weights and the adjustment log already are — a context
snapshot viewer, a `LearnedInsight` browser, and regime history on the
dashboard. Not building this alongside the pipeline (rather than after)
avoids ending up with a system that's "smart" but opaque, which would
undercut the whole point of a decision-support tool.

---

## 10. Recommended build order

- **Phase 4a** (no new external dependencies, no new cost):
  outcome-resolution job, market regime detector, the microstructure
  context provider (funding/OI/liquidations/order-book — all free via
  the exchange access already in place), and evolving `StrategyResult`
  → `AnalystOpinion` (backward compatible). Decision engine v2's math
  goes in here too, but still fully deterministic — no LLM in the loop
  yet.
- **Phase 4b**: Fear & Greed provider, crypto news provider, and the
  nightly review job producing `LearnedInsight`s (statistical grouping
  only).
- **Phase 4c**: the `ai_briefing` synthesis step (one LLM call over the
  full opinion set), plus a decision on the macro-calendar data source.
- **Phase 4d**: on-chain and social providers, each gated on picking
  (and paying for) a data source.
- **Phase 5+**: formalize the multi-agent naming/orchestration once 4a-4d
  exist.

## 11. Decisions needed before 4a starts

The technical design above doesn't need your input to start — it's the
free, already-connected pieces. But a few things are worth deciding now
rather than defaulting silently:
