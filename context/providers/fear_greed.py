"""
Fear & Greed Index context provider. Free, no API key, via
alternative.me's public endpoint. This is a market-wide reading, not
per-symbol -- the `symbol` argument to fetch() is accepted (to match the
ContextProvider interface) but ignored.

Interpretation is deliberately the classic CONTRARIAN read: extreme fear
(crowd is panicking) leans bullish, extreme greed (crowd is euphoric)
leans bearish. That's the conventional use of this index, not a novel
claim -- worth knowing if you ever want to flip it.

Cached in-process for CACHE_TTL_SECONDS since the index only updates
once a day; no reason to hit the API on every firing symbol in a scan.
"""

import logging
import time
from typing import Optional

import requests

from context.base import ContextProvider
from context.types import ContextSignal
from core.types import SignalDirection

logger = logging.getLogger(__name__)

API_URL = "https://api.alternative.me/fng/?limit=1"
CACHE_TTL_SECONDS = 3600  # 1 hour -- the index itself only updates daily
EXTREME_FEAR = 25
EXTREME_GREED = 75


class FearGreedProvider(ContextProvider):
    name = "fear_greed"
    category = "sentiment"

    def __init__(self):
        self._cached_signal: Optional[ContextSignal] = None
        self._cached_at: float = 0.0

    def fetch(self, symbol: Optional[str] = None) -> ContextSignal:
        now = time.time()
        if self._cached_signal is not None and (now - self._cached_at) < CACHE_TTL_SECONDS:
            return self._cached_signal

        signal = self._fetch_live()
        self._cached_signal = signal
        self._cached_at = now
        return signal

    def _fetch_live(self) -> ContextSignal:
        try:
            resp = requests.get(API_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()["data"][0]
            value = int(data["value"])
            classification = data.get("value_classification", "")
        except Exception as e:
            logger.warning(f"Fear & Greed Index unavailable: {e}")
            return ContextSignal(
                provider_name=self.name, category=self.category,
                direction=SignalDirection.HOLD, confidence=0.0,
                reasoning=f"Fear & Greed Index unavailable: {e}",
            )

        if value <= EXTREME_FEAR:
            direction = SignalDirection.BUY
            confidence = float(min((EXTREME_FEAR - value) / EXTREME_FEAR, 1.0)) * 0.5 + 0.3
            reasoning = f"Fear & Greed Index at {value} ({classification}) -- extreme fear, contrarian bullish lean"
        elif value >= EXTREME_GREED:
            direction = SignalDirection.SELL
            confidence = float(min((value - EXTREME_GREED) / (100 - EXTREME_GREED), 1.0)) * 0.5 + 0.3
            reasoning = f"Fear & Greed Index at {value} ({classification}) -- extreme greed, contrarian bearish lean"
        else:
            direction = SignalDirection.HOLD
            confidence = 0.0
            reasoning = f"Fear & Greed Index at {value} ({classification}) -- no extreme reading"

        return ContextSignal(
            provider_name=self.name, category=self.category,
            direction=direction, confidence=round(confidence, 4),
            evidence=[reasoning], reasoning=reasoning,
            raw={"value": value, "classification": classification},
        )
