"""
Microstructure context provider.

Covers 3 of the 4 microstructure signals from the phase-4 roadmap:
funding rate, open interest, and order-book imbalance -- all free,
via exchange endpoints already reachable from this app.

NOT covered here: liquidation clusters. Binance only exposes recent
liquidations through a real-time websocket stream (`!forceOrder@arr`),
not a REST endpoint with history -- there's no websocket infrastructure
in this app yet, so this is honestly out of scope for this pass rather
than faked with something weaker. Revisit if/when a websocket listener
gets built.

Funding rate and open interest are perpetual-futures concepts and
don't exist on the spot market -- this provider talks to a separate
`ccxt.binanceusdm()` client for those two, and reuses the regular spot
client (via data/fetcher.py) for the order book. Not every spot symbol
has a matching futures listing; that's handled as a normal "provider
returned less evidence than usual," not an error.
"""

import logging
from typing import Optional

import ccxt

from context.base import ContextProvider
from context.types import ContextSignal
from core.types import SignalDirection
from data.fetcher import get_data_fetcher

logger = logging.getLogger(__name__)

FUNDING_RATE_ELEVATED = 0.0005    # ~0.05% per 8h funding interval -- crowded-longs territory
FUNDING_RATE_DEPRESSED = -0.0005  # crowded-shorts territory
IMBALANCE_THRESHOLD = 0.10        # 10% bid/ask volume skew before it counts as evidence
ORDER_BOOK_DEPTH = 50

# Funding rate is a *contrarian* signal by convention here: extremely
# positive funding means longs are paying shorts heavily, i.e. the crowd
# is already very long -- read as a lean against the crowd, not with it.
FUNDING_SCORE_WEIGHT = 0.3
IMBALANCE_SCORE_WEIGHT = 0.4


def _to_futures_symbol(spot_symbol: str) -> str:
    """'BTC/USDT' -> 'BTC/USDT:USDT' (ccxt's unified symbol for Binance USD-M perpetuals)."""
    base_quote = spot_symbol.split(":")[0]  # already-futures symbols pass through unchanged
    if ":" in spot_symbol:
        return spot_symbol
    quote = base_quote.split("/")[-1]
    return f"{base_quote}:{quote}"


class MicrostructureProvider(ContextProvider):
    name = "microstructure"
    category = "microstructure"

    def __init__(self):
        self._futures_exchange = None

    def _get_futures_exchange(self):
        if self._futures_exchange is None:
            self._futures_exchange = ccxt.binanceusdm({"enableRateLimit": True})
        return self._futures_exchange

    def fetch(self, symbol: Optional[str] = None) -> ContextSignal:
        if symbol is None:
            return ContextSignal(
                provider_name=self.name, category=self.category,
                direction=SignalDirection.HOLD, confidence=0.0,
                reasoning="microstructure provider requires a symbol",
            )

        evidence = []
        raw = {}
        score = 0.0

        # --- funding rate + open interest (futures) ---
        try:
            futures_ex = self._get_futures_exchange()
            futures_symbol = _to_futures_symbol(symbol)

            funding = futures_ex.fetch_funding_rate(futures_symbol)
            funding_rate = funding.get("fundingRate")
            raw["funding_rate"] = funding_rate

            if funding_rate is not None:
                if funding_rate > FUNDING_RATE_ELEVATED:
                    score -= FUNDING_SCORE_WEIGHT
                    evidence.append(
                        f"Funding rate {funding_rate:.4%} -- crowded longs, contrarian bearish lean"
                    )
                elif funding_rate < FUNDING_RATE_DEPRESSED:
                    score += FUNDING_SCORE_WEIGHT
                    evidence.append(
                        f"Funding rate {funding_rate:.4%} -- crowded shorts, contrarian bullish lean"
                    )

            try:
                oi = futures_ex.fetch_open_interest(futures_symbol)
                raw["open_interest"] = oi.get("openInterestAmount") or oi.get("openInterestValue")
            except Exception as e:
                logger.debug(f"Open interest unavailable for {symbol}: {e}")

        except Exception as e:
            logger.debug(f"No futures data for {symbol} (may not have a futures listing): {e}")

        # --- order book imbalance (spot) ---
        try:
            spot_exchange = get_data_fetcher().exchange
            book = spot_exchange.fetch_order_book(symbol, limit=ORDER_BOOK_DEPTH)
            bid_volume = sum(b[1] for b in book.get("bids", []))
            ask_volume = sum(a[1] for a in book.get("asks", []))
            total = bid_volume + ask_volume
            if total > 0:
                imbalance = (bid_volume - ask_volume) / total
                raw["order_book_imbalance"] = round(imbalance, 4)
                if abs(imbalance) >= IMBALANCE_THRESHOLD:
                    score += IMBALANCE_SCORE_WEIGHT * (1 if imbalance > 0 else -1)
                    evidence.append(
                        f"Order book {imbalance:+.1%} skewed toward {'bids' if imbalance > 0 else 'asks'}"
                    )
        except Exception as e:
            logger.debug(f"Order book unavailable for {symbol}: {e}")

        confidence = float(min(abs(score), 1.0))
        if score > 0.15:
            direction = SignalDirection.BUY
        elif score < -0.15:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        reasoning = "; ".join(evidence) if evidence else "No strong funding-rate or order-book signal"

        return ContextSignal(
            provider_name=self.name, category=self.category,
            direction=direction, confidence=confidence,
            evidence=evidence, reasoning=reasoning, raw=raw,
        )
