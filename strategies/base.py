"""
Base interface for strategy plugins.

STATUS: scaffolding only, not wired into anything yet. The goal (per the
project brief) is: "Adding an eighth strategy should require almost no
changes elsewhere." That means every strategy -- including the existing
RandomForest model in strategies/ml_model/ -- should eventually implement
this same analyze() contract and register with a future aggregator in
signals/, rather than the aggregator knowing about any strategy's
internals.

A strategy MUST NOT send alerts, write to the database, or otherwise
cause side effects. It only analyzes and returns an opinion.
"""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from core.types import StrategyResult


class Strategy(ABC):
    """Every strategy plugin implements this interface."""

    #: Short, stable identifier used in logs, weights config, and alerts.
    name: str = "unnamed_strategy"

    @abstractmethod
    def analyze(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> StrategyResult:
        """
        Produce one independent opinion for a symbol/timeframe given OHLCV
        candle data. Must not mutate `candles` or perform any I/O beyond
        pure computation on the data it's given.
        """
        raise NotImplementedError
