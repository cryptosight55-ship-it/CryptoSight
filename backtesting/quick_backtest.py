"""
Quick historical sanity-check for a signal that just fired live.

Deliberately NOT run for every symbol on every scan -- only for the
handful that actually produce a live signal, and only over a bounded
number of sample points (see MAX_SAMPLES) so a scan can't stall waiting
on this. This is a fast sanity check, not a rigorous backtest engine --
it reuses the exact same aggregate() function the live signal used, on
shrinking historical windows, so "would this exact setup have worked
recently" is answered with the same logic that's about to fire live.
"""

import logging
from typing import Optional, Dict, Any

import pandas as pd

from core.types import SignalDirection
from signals.aggregator import aggregate

logger = logging.getLogger(__name__)

MIN_LOOKBACK = 60          # candles needed before a strategy can produce a real opinion
LOOKFORWARD_BARS = 24      # how many future candles to check for TP/SL being hit
MAX_SAMPLES = 40           # hard cap on how many historical points we test, for speed
WINDOW_SIZE = 250          # bars fed to aggregate() at each historical point


def _resolve_outcome(direction, entry: float, stop_loss: float, take_profit: float,
                      future_candles: pd.DataFrame) -> str:
    for _, row in future_candles.iterrows():
        high, low = row["high"], row["low"]
        if direction == SignalDirection.BUY:
            hit_sl, hit_tp = low <= stop_loss, high >= take_profit
        else:
            hit_sl, hit_tp = high >= stop_loss, low <= take_profit
        if hit_sl:
            # If both were touched on the same candle, assume the stop was
            # hit first -- conservative, since we can't know intra-candle order.
            return "loss"
        if hit_tp:
            return "win"
    return "no_result"


def quick_backtest(symbol: str, timeframe: str, candles: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Returns {"sample_size", "wins", "losses", "no_result", "win_rate"}, or
    None if there wasn't enough history to test anything.
    """
    n = len(candles)
    usable_range = n - MIN_LOOKBACK - LOOKFORWARD_BARS
    if usable_range <= 0:
        return None

    step = max(3, usable_range // MAX_SAMPLES)

    wins = losses = no_result = 0
    for i in range(MIN_LOOKBACK, n - LOOKFORWARD_BARS, step):
        window = candles.iloc[max(0, i - WINDOW_SIZE):i + 1].reset_index(drop=True)
        try:
            result = aggregate(symbol, timeframe, window)
        except Exception as e:
            logger.debug(f"Backtest point failed for {symbol} at bar {i}: {e}")
            continue
        if result is None:
            continue

        future = candles.iloc[i + 1: i + 1 + LOOKFORWARD_BARS]
        outcome = _resolve_outcome(
            result["direction"], result["entry_price"], result["stop_loss"],
            result["take_profit"], future,
        )
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        else:
            no_result += 1

    sample_size = wins + losses
    return {
        "sample_size": sample_size,
        "wins": wins,
        "losses": losses,
        "no_result": no_result,
        "win_rate": round(wins / sample_size, 4) if sample_size else None,
    }
