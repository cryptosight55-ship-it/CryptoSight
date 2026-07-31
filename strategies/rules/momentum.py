"""
Momentum strategy: MACD line vs signal line for direction, RSI as a
sanity check so we don't buy into an already-overbought move or sell
into an already-oversold one.
"""

import talib
import pandas as pd

from strategies.base import Strategy
from core.types import StrategyResult, SignalDirection


class MomentumStrategy(Strategy):
    name = "momentum"

    def analyze(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> StrategyResult:
        close = candles["close"].values

        if len(close) < 40:
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0,
                reasons=["not enough candles for MACD/RSI"],
            )

        rsi = talib.RSI(close, timeperiod=14)
        macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)

        r, m, ms, mh = rsi[-1], macd[-1], macd_signal[-1], macd_hist[-1]
        if pd.isna(r) or pd.isna(m) or pd.isna(ms):
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0, reasons=["indicators not ready"]
            )

        # Normalize histogram magnitude relative to price so confidence is
        # comparable across coins of very different price scales.
        confidence = float(min(abs(mh) / (close[-1] * 0.005), 1.0)) if close[-1] else 0.0
        metadata = {"rsi": round(float(r), 2), "macd": round(float(m), 6), "macd_signal": round(float(ms), 6)}

        if m > ms and 40 <= r <= 75:
            return StrategyResult(
                self.name, SignalDirection.BUY, confidence=confidence, score=confidence,
                reasons=[f"MACD bullish cross, RSI {r:.1f} not overbought"],
                metadata=metadata,
            )
        if m < ms and 25 <= r <= 60:
            return StrategyResult(
                self.name, SignalDirection.SELL, confidence=confidence, score=confidence,
                reasons=[f"MACD bearish cross, RSI {r:.1f} not oversold"],
                metadata=metadata,
            )
        return StrategyResult(
            self.name, SignalDirection.HOLD, 0.0, 0.0,
            reasons=["MACD/RSI not aligned"], metadata=metadata,
        )
