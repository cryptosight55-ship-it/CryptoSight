"""
Crypto news context provider. Uses free RSS feeds (no signup, no API
key -- deliberately avoided CryptoPanic and similar here since they
require creating an account for an auth token, and the goal right now
is zero new friction/cost while still testing).

HONEST LIMITATION: this is a coarse keyword-based pass, not NLP or an
AI-based sentiment classifier. Headline matching is a whole-word search
for the symbol's ticker (e.g. "BTC" for BTC/USDT) -- it will miss
headlines that only use a coin's full name for less-common tickers, and
the bullish/bearish lexicon is a short hardcoded word list, not a
trained sentiment model. A natural upgrade later: one OpenRouter call
per scan (not per-symbol -- keep API cost down) that classifies the
batch of fetched headlines properly. Not done here to keep this pass
free of any new AI-call cost per scan; revisit once there's appetite for
that.

Headlines are fetched once and cached for CACHE_TTL_SECONDS, then
re-filtered per symbol from the cached batch -- so a scan with several
firing symbols only hits the RSS feeds once.
"""

import logging
import re
import time
from typing import Optional, List, Dict
from xml.etree import ElementTree

import requests

from context.base import ContextProvider
from context.types import ContextSignal
from core.types import SignalDirection

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]
CACHE_TTL_SECONDS = 900  # 15 minutes
MAX_HEADLINES_PER_FEED = 30

BULLISH_WORDS = [
    "surge", "rally", "approval", "approved", "adoption", "partnership",
    "upgrade", "breakout", "record high", "all-time high", "inflow", "bullish",
]
BEARISH_WORDS = [
    "hack", "exploit", "lawsuit", "ban", "banned", "crash", "sell-off", "selloff",
    "delist", "investigation", "outflow", "bearish", "collapse", "fraud",
]


class CryptoNewsProvider(ContextProvider):
    name = "crypto_news"
    category = "crypto_news"

    def __init__(self):
        self._cached_headlines: Optional[List[str]] = None
        self._cached_at: float = 0.0

    def _get_headlines(self) -> List[str]:
        now = time.time()
        if self._cached_headlines is not None and (now - self._cached_at) < CACHE_TTL_SECONDS:
            return self._cached_headlines

        headlines = []
        for url in RSS_FEEDS:
            try:
                resp = requests.get(url, timeout=10, headers={"User-Agent": "CryptoSight/1.0"})
                resp.raise_for_status()
                headlines.extend(self._parse_titles(resp.text)[:MAX_HEADLINES_PER_FEED])
            except Exception as e:
                logger.debug(f"RSS feed unavailable ({url}): {e}")

        self._cached_headlines = headlines
        self._cached_at = now
        return headlines

    @staticmethod
    def _parse_titles(xml_text: str) -> List[str]:
        try:
            root = ElementTree.fromstring(xml_text)
            return [item.findtext("title", default="").strip() for item in root.iter("item")]
        except ElementTree.ParseError as e:
            logger.debug(f"RSS parse failed: {e}")
            return []

    def fetch(self, symbol: Optional[str] = None) -> ContextSignal:
        headlines = self._get_headlines()
        if not headlines:
            return ContextSignal(
                provider_name=self.name, category=self.category,
                direction=SignalDirection.HOLD, confidence=0.0,
                reasoning="No news headlines available",
            )

        relevant = headlines
        if symbol:
            ticker = symbol.split("/")[0].upper()
            pattern = re.compile(rf"\b{re.escape(ticker)}\b", re.IGNORECASE)
            matched = [h for h in headlines if pattern.search(h)]
            if matched:
                relevant = matched
            # else: fall back to the full unfiltered headline set as
            # weak general-market-mood evidence, per the docstring's
            # noted limitation on ticker-only matching.

        bullish_hits = []
        bearish_hits = []
        for h in relevant:
            h_lower = h.lower()
            if any(w in h_lower for w in BULLISH_WORDS):
                bullish_hits.append(h)
            if any(w in h_lower for w in BEARISH_WORDS):
                bearish_hits.append(h)

        score = len(bullish_hits) - len(bearish_hits)
        confidence = float(min(abs(score) / 3.0, 1.0))  # 3+ net hits = full confidence

        if score > 0:
            direction = SignalDirection.BUY
            evidence = bullish_hits[:3]
            reasoning = f"{len(bullish_hits)} bullish-leaning headline(s) found, {len(bearish_hits)} bearish"
        elif score < 0:
            direction = SignalDirection.SELL
            evidence = bearish_hits[:3]
            reasoning = f"{len(bearish_hits)} bearish-leaning headline(s) found, {len(bullish_hits)} bullish"
        else:
            direction = SignalDirection.HOLD
            confidence = 0.0
            evidence = []
            reasoning = "No net bullish/bearish headline signal"

        return ContextSignal(
            provider_name=self.name, category=self.category,
            direction=direction, confidence=round(confidence, 4),
            evidence=evidence, reasoning=reasoning,
            raw={"headlines_checked": len(relevant), "bullish": len(bullish_hits), "bearish": len(bearish_hits)},
        )
