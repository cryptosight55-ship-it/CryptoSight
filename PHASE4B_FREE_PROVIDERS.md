# Phase 4b (partial): Two Free Context Providers

The nightly-review/`LearnedInsight` piece of Phase 4b is intentionally
held back — see `PHASE4A_CONTEXT_LAYER.md`'s note on why (no resolved
signal history to learn from yet). This is just the two new
`ContextSignal` sources, both free, both zero-config.

## Fear & Greed Index (`context/providers/fear_greed.py`)

Via `alternative.me`'s public API — no signup, no key. Market-wide
reading (not per-symbol; `symbol` is accepted but ignored to match the
provider interface). Cached for an hour in-process since the index only
updates daily.

**Interpretation is the classic contrarian read**: extreme fear (≤25)
leans bullish, extreme greed (≥75) leans bearish — the crowd being
panicked or euphoric is read as a signal against following the crowd,
not with it. Worth knowing if you ever want that flipped.

## Crypto news (`context/providers/crypto_news.py`)

Free RSS feeds (CoinDesk, CoinTelegraph) — deliberately **not**
CryptoPanic or similar, since those require creating an account for an
API token, and the point right now was zero new friction or cost.
Headlines are fetched once and cached for 15 minutes, then re-filtered
per symbol from that cached batch (so a scan with several firing
symbols only hits the RSS feeds once, not once per symbol).

**Be aware of the real limitation here, stated plainly**: this is
keyword matching, not NLP or AI sentiment analysis.
- Symbol relevance is a whole-word search for the ticker (e.g. "BTC")
  in the headline text. Tested against a synthetic headline using
  "Bitcoin" instead of "BTC" — it does NOT match. Coins whose news
  coverage favors the full name over the ticker will under-match.
- Bullish/bearish scoring is a short hardcoded word list (`surge`,
  `hack`, `approval`, `lawsuit`, etc.), not a trained model.

Both are real, working signals — just coarse ones. The natural upgrade
is one OpenRouter call per scan (batching all fetched headlines, not one
call per symbol, to keep AI cost down) that actually classifies
relevance and sentiment properly. Not built now, on purpose — it would
add a per-scan AI cost, and the goal for this phase was staying free.
Worth doing once you're ready to spend a little on the AI side.

## Both are already wired in

`context/aggregator.py`'s `PROVIDERS` list now has three entries
(microstructure, fear_greed, crypto_news) — `core/scanner.py` didn't
need any changes, it already calls `gather_context()` generically.
Bounded ±15% confidence adjustment (`CONTEXT_MAX_ADJUSTMENT` in
`signals/aggregator.py`) still applies to all of them combined, same
guardrail as before.
