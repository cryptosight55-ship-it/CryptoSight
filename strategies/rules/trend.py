"""
Trend strategy: EMA20 vs EMA50 relative position, confirmed by ADX so a
signal only fires when there's an actual trend to follow (ADX below ~20
usually means the market is choppy/ranging -- EMA crosses there are
mostly noise).
"""

import talib
import pandas as pd

from strategies.base import Strategy
from core.types import StrategyResult, SignalDirection

ADX_TREND_THRESHOLD = 20.0
EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50


class TrendStrategy(Strategy):
    name = "trend"

    def analyze(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> StrategyResult:
        close = candles["close"].values
        high = candles["high"].values
        low = candles["low"].values

        if len(close) < EMA_SLOW_PERIOD + 10:
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0,
                reasons=["not enough candles for EMA50/ADX"],
            )

        ema_fast = talib.EMA(close, timeperiod=EMA_FAST_PERIOD)
        ema_slow = talib.EMA(close, timeperiod=EMA_SLOW_PERIOD)
        adx = talib.ADX(high, low, close, timeperiod=14)

        f, s, a, last_close = ema_fast[-1], ema_slow[-1], adx[-1], close[-1]
        if pd.isna(f) or pd.isna(s) or pd.isna(a):
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0, reasons=["indicators not ready"]
            )

        strength = float(min(a / 50.0, 1.0))  # ADX 25=trending, 50+=very strong; normalize to 0-1
        metadata = {"ema_fast": round(float(f), 6), "ema_slow": round(float(s), 6), "adx": round(float(a), 2)}

        if f > s and last_close > f and a >= ADX_TREND_THRESHOLD:
            return StrategyResult(
                self.name, SignalDirection.BUY, confidence=strength, score=strength,
                reasons=[f"EMA{EMA_FAST_PERIOD} above EMA{EMA_SLOW_PERIOD}, ADX {a:.1f} confirms uptrend"],
                metadata=metadata,
            )
        if f < s and last_close < f and a >= ADX_TREND_THRESHOLD:
            return StrategyResult(
                self.name, SignalDirection.SELL, confidence=strength, score=strength,
                reasons=[f"EMA{EMA_FAST_PERIOD} below EMA{EMA_SLOW_PERIOD}, ADX {a:.1f} confirms downtrend"],
                metadata=metadata,
            )
        return StrategyResult(
            self.name, SignalDirection.HOLD, 0.0, 0.0,
            reasons=["no aligned trend or ADX too weak"], metadata=metadata,
        )
