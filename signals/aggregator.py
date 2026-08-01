"""
The signal aggregator -- decision engine v2 (Phase 4a).

The core gate is UNCHANGED from Phase 3: at least MIN_AGREEING of the 5
technical strategies must agree on a direction, or no signal fires.
That's still what decides *whether* a signal exists -- Phase 4a doesn't
touch that, on purpose. What's new:

1. Regime-conditioned weights: each strategy's weight is multiplied by
   regime/detector.py's static per-(strategy, regime) multiplier before
   computing weighted confidence.
2. Context adjustment: if context signals are supplied (from
   context/aggregator.py), they can nudge the confidence score up or
   down by at most CONTEXT_MAX_ADJUSTMENT -- bounded, additive, and
   applied AFTER the technical gate already decided direction. Context
   signals can currently never create a signal or flip its direction on
   their own; there's no track record yet to justify giving an
   unvalidated new layer that much power. Revisit once Phase 4b's
   learning pipeline has real data on whether context actually helps.

Adding a 6th strategy still just means adding it to ALL_STRATEGIES and
seeding a StrategyWeight row for it -- nothing here changes for that.
"""

import logging
from typing import List, Optional, Dict, Any

import pandas as pd
import talib

from core.types import StrategyResult, SignalDirection
from context.types import ContextSignal
from strategies.base import Strategy
from strategies.rules.trend import TrendStrategy
from strategies.rules.momentum import MomentumStrategy
from strategies.rules.volume import VolumeStrategy
from strategies.rules.volatility import VolatilityStrategy
from strategies.ml_model.predictor_strategy import MLModelStrategy
from database.db import get_session
from database.models import StrategyWeight
from regime.detector import detect_regime, get_regime_multiplier

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

# Bounded, same philosophy as ai/accuracy_reviewer.py's weight-step cap:
# a new, unvalidated layer shouldn't be able to swing confidence wildly.
CONTEXT_MAX_ADJUSTMENT = 0.15


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


def _apply_context_adjustment(
    base_confidence: float, direction: SignalDirection, context_signals: List[ContextSignal]
) -> tuple:
    """Returns (adjusted_confidence, context_evidence_used)."""
    if not context_signals:
        return base_confidence, []

    adjustment = 0.0
    evidence_used = []
    for c in context_signals:
        if c.direction == SignalDirection.HOLD:
            continue
        if c.direction == direction:
            adjustment += c.confidence * CONTEXT_MAX_ADJUSTMENT
        else:
            adjustment -= c.confidence * CONTEXT_MAX_ADJUSTMENT
        evidence_used.extend(c.evidence)

    adjustment = max(-CONTEXT_MAX_ADJUSTMENT, min(CONTEXT_MAX_ADJUSTMENT, adjustment))
    adjusted = float(min(max(base_confidence + adjustment, 0.0), 1.0))
    return adjusted, evidence_used


def aggregate(
    symbol: str,
    timeframe: str,
    candles: pd.DataFrame,
    context_signals: Optional[List[ContextSignal]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Returns None if fewer than MIN_AGREEING strategies agree on a
    direction. Otherwise returns a dict describing the resulting signal.

    context_signals is optional and defaults to None -- callers that
    don't pass it (e.g. backtesting/quick_backtest.py, which has no
    historical context data to feed in) get identical behavior to
    Phase 3's aggregator, just with regime weighting added.
    """
    results = run_all_strategies(symbol, timeframe, candles)
    weights = get_strategy_weights()
    regime_info = detect_regime(candles)
    regimes = regime_info.get("regimes") or []

    def effective_weight(strategy_name: str) -> float:
        return weights.get(strategy_name, 1.0) * get_regime_multiplier(strategy_name, regimes)

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

    total_possible_weight = sum(effective_weight(s.name) for s in ALL_STRATEGIES if s.is_active())
    weighted_sum = sum(r.confidence * effective_weight(r.strategy_name) for r in agreeing)
    base_confidence = float(min(weighted_sum / total_possible_weight, 1.0)) if total_possible_weight else 0.0

    confidence, context_evidence = _apply_context_adjustment(base_confidence, direction, context_signals or [])

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
        "base_confidence": round(base_confidence, 4),
        "entry_price": last_close,
        "stop_loss": round(stop_loss, 8),
        "take_profit": round(take_profit, 8),
        "strategies_agreeing": [r.strategy_name for r in agreeing],
        "reasons": reasons,
        "context_evidence": context_evidence,
        "regime": regime_info,
        "atr": atr,
        "all_results": results,
    }
