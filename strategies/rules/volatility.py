"""
Volatility strategy: price closing outside its Bollinger Bands (20, 2std)
signals a breakout. Also computes ATR(14) and puts it in metadata --
the aggregator uses it to size stop-loss/take-profit distances for
whatever direction ends up winning, regardless of which strategies agreed.
"""

import talib
import pandas as pd

from strategies.base import Strategy
from core.types import StrategyResult, SignalDirection

BB_PERIOD = 20
BB_STDDEV = 2
ATR_PERIOD = 14


class VolatilityStrategy(Strategy):
    name = "volatility"

    def analyze(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> StrategyResult:
        close = candles["close"].values
        high = candles["high"].values
        low = candles["low"].values

        if len(close) < BB_PERIOD + 5:
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0,
                reasons=["not enough candles for Bollinger Bands/ATR"],
            )

        upper, middle, lower = talib.BBANDS(
            close, timeperiod=BB_PERIOD, nbdevup=BB_STDDEV, nbdevdn=BB_STDDEV
        )
        atr = talib.ATR(high, low, close, timeperiod=ATR_PERIOD)

        u, l, a, last_close = upper[-1], lower[-1], atr[-1], close[-1]
        if pd.isna(u) or pd.isna(l) or pd.isna(a) or a <= 0:
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0, reasons=["indicators not ready"]
            )

        metadata = {"atr": round(float(a), 6), "bb_upper": round(float(u), 6), "bb_lower": round(float(l), 6)}

        if last_close > u:
            distance = (last_close - u) / a
            confidence = float(min(distance, 1.0))
            return StrategyResult(
                self.name, SignalDirection.BUY, confidence=confidence, score=confidence,
                reasons=["Price broke above upper Bollinger Band"], metadata=metadata,
            )
        if last_close < l:
            distance = (l - last_close) / a
            confidence = float(min(distance, 1.0))
            return StrategyResult(
                self.name, SignalDirection.SELL, confidence=confidence, score=confidence,
                reasons=["Price broke below lower Bollinger Band"], metadata=metadata,
            )
        return StrategyResult(
            self.name, SignalDirection.HOLD, 0.0, 0.0,
            reasons=["price within Bollinger Bands, no breakout"], metadata=metadata,
        )
