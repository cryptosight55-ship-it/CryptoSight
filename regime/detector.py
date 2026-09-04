"""
Market regime detection.

Deliberately simple for a first pass, per the phase-4 roadmap: ADX for
trending-vs-ranging (ADX >= 25 is the standard trending threshold),
realized volatility percentile (vs. its own recent history) for
high-vol-vs-low-vol. A market can be trending AND high-vol at once --
regimes returned as a list of labels, not one mutually-exclusive category.

Regime multipliers below are a STATIC starting point, not DB-backed or
AI-tunable yet. That's intentional: there's no learning-loop mechanism
in place yet to justify dynamically tuning them (that's Phase 4b, once
the nightly review job exists). Making these DB-backed now would just
be an admin-editable table nothing ever actually adjusts. Revisit once
4b ships.
"""

import logging
from typing import Dict, Any, List

import pandas as pd
import talib

logger = logging.getLogger(__name__)

ADX_TRENDING_THRESHOLD = 25.0
VOL_LOOKBACK = 20
HIGH_VOL_PERCENTILE = 0.75
LOW_VOL_PERCENTILE = 0.25

TRENDING = "trending"
RANGING = "ranging"
HIGH_VOLATILITY = "high_volatility"
LOW_VOLATILITY = "low_volatility"

# (strategy_name, regime) -> multiplier applied on top of StrategyWeight.
# Conservative on purpose -- these nudge, they don't dominate the
# aggregation math. Missing combinations default to 1.0 (no adjustment).
DEFAULT_REGIME_MULTIPLIERS = {
    # Replaced Sept 2026, after a full month of resolved signals made
    # clear the original assumptions here had the direction BACKWARDS
    # for this system. The nightly review (learning/nightly_review.py)
    # showed every strategy performing roughly twice as well in
    # ranging/low-volatility conditions as in trending/high-volatility
    # ones -- the opposite of "trend strategies excel during strong
    # directional markets," which is what the old multipliers assumed.
    #
    # Source data (win rate, sample size), Aug 2026:
    #   trend:      trending 14% (n=28), high_vol 12% (n=17), ranging 28% (n=18), low_vol 23% (n=13)
    #   momentum:   trending 10% (n=29), high_vol  6% (n=17), ranging 27% (n=22), low_vol 29% (n=14)
    #   volatility: trending 13% (n=31), high_vol 11% (n=19), ranging 26% (n=19), low_vol 29% (n=14)
    #   volume:     only ranging had enough samples (20%, n=10) -- not
    #               enough evidence for the other regimes, left neutral.
    #
    # Values below are each regime's win rate divided by that strategy's
    # own average across regimes, clamped to [0.6, 1.3] to stay a nudge
    # rather than a dominant force -- samples are real but still modest
    # (13-31), and this is itself a hypothesis to keep validating as
    # more data accumulates, not a settled conclusion.
    ("trend", TRENDING): 0.7,
    ("trend", HIGH_VOLATILITY): 0.6,
    ("trend", RANGING): 1.3,
    ("trend", LOW_VOLATILITY): 1.2,
    ("momentum", TRENDING): 0.6,
    ("momentum", HIGH_VOLATILITY): 0.6,
    ("momentum", RANGING): 1.3,
    ("momentum", LOW_VOLATILITY): 1.3,
    ("volatility", TRENDING): 0.7,
    ("volatility", HIGH_VOLATILITY): 0.6,
    ("volatility", RANGING): 1.3,
    ("volatility", LOW_VOLATILITY): 1.3,
    # volume's old ("volume", HIGH_VOLATILITY): 1.1 boost is removed --
    # it was never supported by data, and high_volatility is now the
    # worst-performing regime across every strategy that DOES have data.
}


def detect_regime(candles: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns {"regimes": [...], "adx": float, "vol_percentile": float}.
    Returns an empty regimes list (not an error) if there isn't enough
    history yet -- callers should treat that as "no regime adjustment,"
    not as a failure.
    """
    close = candles["close"].values
    high = candles["high"].values
    low = candles["low"].values

    if len(close) < 60:
        return {"regimes": [], "adx": None, "vol_percentile": None}

    adx = talib.ADX(high, low, close, timeperiod=14)
    if pd.isna(adx[-1]):
        return {"regimes": [], "adx": None, "vol_percentile": None}

    returns = pd.Series(close).pct_change().dropna()
    rolling_vol = returns.rolling(VOL_LOOKBACK).std().dropna()
    if rolling_vol.empty:
        return {"regimes": [], "adx": round(float(adx[-1]), 2), "vol_percentile": None}

    current_vol = rolling_vol.iloc[-1]
    vol_percentile = float((rolling_vol <= current_vol).mean())

    regimes: List[str] = [TRENDING if adx[-1] >= ADX_TRENDING_THRESHOLD else RANGING]
    if vol_percentile >= HIGH_VOL_PERCENTILE:
        regimes.append(HIGH_VOLATILITY)
    elif vol_percentile <= LOW_VOL_PERCENTILE:
        regimes.append(LOW_VOLATILITY)

    return {
        "regimes": regimes,
        "adx": round(float(adx[-1]), 2),
        "vol_percentile": round(vol_percentile, 4),
    }


def get_regime_multiplier(strategy_name: str, regimes: List[str]) -> float:
    """Combined multiplier for a strategy across all active regime labels."""
    multiplier = 1.0
    for regime in regimes:
        multiplier *= DEFAULT_REGIME_MULTIPLIERS.get((strategy_name, regime), 1.0)
    return multiplier
