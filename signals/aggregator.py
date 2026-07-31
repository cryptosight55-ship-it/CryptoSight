"""
The signal aggregator. This is the piece the original codebase never
had -- previously a single ML model's prediction WAS the signal. Now:
every strategy in ALL_STRATEGIES independently analyzes the same
candles, and a signal only fires when at least MIN_AGREEING of them
land on the same direction.

Adding a 6th strategy later means adding it to ALL_STRATEGIES and
seeding a StrategyWeight row for it -- nothing here needs to change,
per the "adding an 8th strategy should require almost no changes
elsewhere" goal from the original brief.
"""

import logging
from typing import List, Optional, Dict, Any

import pandas as pd
import talib

from core.types import StrategyResult, SignalDirection
from strategies.base import Strategy
from strategies.rules.trend import TrendStrategy
from strategies.rules.momentum import MomentumStrategy
from strategies.rules.volume import VolumeStrategy
from strategies.rules.volatility import VolatilityStrategy
from strategies.ml_model.predictor_strategy import MLModelStrategy
from database.db import get_session
from database.models import StrategyWeight

logger = logging.getLogger(__name__)

ALL_STRATEGIES: List[Strategy] = [
    TrendStrategy(),
    MomentumStrategy(),
    VolumeStrategy(),
    VolatilityStrategy(),
    MLModelStrategy(),
]
MIN_AGREEING = 3

# Fallback ATR multiples used for stop-loss/take-profit sizing when the
# volatility strategy didn't run or didn't return ATR (shouldn't normally
# happen, but analyze() calls are individually try/excepted below).
ATR_STOP_MULTIPLE = 1.5
ATR_TARGET_MULTIPLE = 3.0  # 1:2 risk/reward baked in


def get_strategy_weights() -> Dict[str, float]:
    with get_session() as session:
        rows = session.query(StrategyWeight).filter_by(enabled=True).all()
        return {r.strategy_name: r.weight for r in rows}


def _compute_atr(candles: pd.DataFrame) -> Optional[float]:
    if len(candles) < 20:
        return None
    atr = talib.ATR(candles["high"].values, candles["low"].values, candles["close"].values, timeperiod=14)
    value = atr[-1]
    return float(value) if not pd.isna(value) else None


def run_all_strategies(symbol: str, timeframe: str, candles: pd.DataFrame) -> List[StrategyResult]:
    """Run every strategy, skipping (not crashing on) any that errors."""
    results = []
    for strat in ALL_STRATEGIES:
        try:
            results.append(strat.analyze(symbol, timeframe, candles))
        except Exception as e:
            logger.warning(f"Strategy '{strat.name}' failed for {symbol} {timeframe}: {e}")
    return results


def aggregate(symbol: str, timeframe: str, candles: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Returns None if fewer than MIN_AGREEING strategies agree on a
    direction. Otherwise returns a dict describing the resulting signal:
    direction, confidence, entry/stop_loss/take_profit, strategies_agreeing,
    reasons, and the full list of individual StrategyResults (for logging).
    """
    results = run_all_strategies(symbol, timeframe, candles)
    weights = get_strategy_weights()

    buy_results = [r for r in results if r.signal == SignalDirection.BUY]
    sell_results = [r for r in results if r.signal == SignalDirection.SELL]

    if len(buy_results) >= MIN_AGREEING and len(buy_results) >= len(sell_results):
        direction = SignalDirection.BUY
        agreeing = buy_results
    elif len(sell_results) >= MIN_AGREEING and len(sell_results) > len(buy_results):
        direction = SignalDirection.SELL
        agreeing = sell_results
    else:
        return None

    total_possible_weight = sum(weights.get(s.name, 1.0) for s in ALL_STRATEGIES)
    weighted_sum = sum(r.confidence * weights.get(r.strategy_name, 1.0) for r in agreeing)
    confidence = float(min(weighted_sum / total_possible_weight, 1.0)) if total_possible_weight else 0.0

    last_close = float(candles["close"].values[-1])
    atr = _compute_atr(candles)
    if atr is None or atr <= 0:
        # Fall back to a conservative fixed percentage if ATR isn't available
        atr = last_close * 0.01

    if direction == SignalDirection.BUY:
        stop_loss = last_close - ATR_STOP_MULTIPLE * atr
        take_profit = last_close + ATR_TARGET_MULTIPLE * atr
    else:
        stop_loss = last_close + ATR_STOP_MULTIPLE * atr
        take_profit = last_close - ATR_TARGET_MULTIPLE * atr

    reasons = [reason for r in agreeing for reason in r.reasons]

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "direction": direction,
        "confidence": round(confidence, 4),
        "entry_price": last_close,
        "stop_loss": round(stop_loss, 8),
        "take_profit": round(take_profit, 8),
        "strategies_agreeing": [r.strategy_name for r in agreeing],
        "reasons": reasons,
        "atr": atr,
        "all_results": results,
    }
