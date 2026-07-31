"""
Volume strategy: flags a volume spike (current volume well above its
20-period average) that's confirmed by both price direction and OBV
trend -- a volume spike alone means nothing without agreement on which
way it's pushing price.
"""

import talib
import pandas as pd
import numpy as np

from strategies.base import Strategy
from core.types import StrategyResult, SignalDirection

VOLUME_SPIKE_RATIO = 1.5
AVG_PERIOD = 20
OBV_LOOKBACK = 5


class VolumeStrategy(Strategy):
    name = "volume"

    def analyze(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> StrategyResult:
        close = candles["close"].values
        volume = candles["volume"].values

        if len(close) < AVG_PERIOD + OBV_LOOKBACK + 1:
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0,
                reasons=["not enough candles for volume average/OBV"],
            )

        avg_volume = np.mean(volume[-(AVG_PERIOD + 1):-1])  # excludes current bar
        obv = talib.OBV(close, volume)

        if avg_volume <= 0 or pd.isna(obv[-1]) or pd.isna(obv[-1 - OBV_LOOKBACK]):
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0, reasons=["indicators not ready"]
            )

        vol_ratio = volume[-1] / avg_volume
        price_change = close[-1] - close[-2]
        obv_trend = obv[-1] - obv[-1 - OBV_LOOKBACK]
        confidence = float(min(max(vol_ratio - 1.0, 0.0) / 2.0, 1.0))
        metadata = {"volume_ratio": round(float(vol_ratio), 2), "obv_trend": float(obv_trend)}

        if vol_ratio >= VOLUME_SPIKE_RATIO and price_change > 0 and obv_trend > 0:
            return StrategyResult(
                self.name, SignalDirection.BUY, confidence=confidence, score=confidence,
                reasons=[f"Volume {vol_ratio:.1f}x average, rising price and OBV"],
                metadata=metadata,
            )
        if vol_ratio >= VOLUME_SPIKE_RATIO and price_change < 0 and obv_trend < 0:
            return StrategyResult(
                self.name, SignalDirection.SELL, confidence=confidence, score=confidence,
                reasons=[f"Volume {vol_ratio:.1f}x average, falling price and OBV"],
                metadata=metadata,
            )
        return StrategyResult(
            self.name, SignalDirection.HOLD, 0.0, 0.0,
            reasons=["no confirmed volume-backed move"], metadata=metadata,
        )
