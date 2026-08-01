"""
Wraps the existing ML model (feature_engineer + predictor, both
untouched) behind the Strategy interface. This is what "the model
becomes one strategy among several" (your earlier decision) actually
looks like in code.

IMPORTANT: as of this writing there is no models/latest_model.pkl or
fallback model file in the repo (flagged back in the original codebase
audit). model_predictor.load_model() will fail, and this strategy will
return HOLD with "model not available" every time -- gracefully, not by
crashing the scan. Once you deploy a real model file, this starts
contributing real votes with zero changes needed here.

Also note the model is a binary "breakout" classifier, not a genuine
BUY/SELL classifier -- prediction==1 is treated as BUY, prediction==0 as
HOLD (not SELL). Forcing prediction==0 into a SELL vote would be
inventing a signal the model was never trained to make.
"""

import logging

import pandas as pd

from strategies.base import Strategy
from core.types import StrategyResult, SignalDirection
from indicators.features import feature_engineer
from strategies.ml_model.predictor import model_predictor

logger = logging.getLogger(__name__)


class MLModelStrategy(Strategy):
    name = "ml_model"

    # Class-level, not per-instance: only attempt (and log) the model
    # load once per process, not on every analyze() call. Without this,
    # quick_backtest re-running aggregate() up to 40 times per firing
    # symbol turned one missing-model condition into dozens of identical
    # "No model files found!" log lines per scan. Render restarts the
    # process on every deploy anyway, so "once per process" naturally
    # re-checks whenever a real model file eventually gets deployed.
    _load_attempted = False
    _load_succeeded = False

    def _ensure_model_loaded(self) -> bool:
        if not MLModelStrategy._load_attempted:
            MLModelStrategy._load_attempted = True
            MLModelStrategy._load_succeeded = model_predictor.load_model()
            if not MLModelStrategy._load_succeeded:
                logger.warning(
                    "ML model file not available -- this strategy will return HOLD "
                    "for the rest of this process's lifetime (won't re-log this every call)."
                )
        return MLModelStrategy._load_succeeded

    def is_active(self) -> bool:
        """
        Reflects whether a real model file actually loaded. While False,
        signals/aggregator.py excludes this strategy's weight from the
        confidence-ceiling denominator entirely -- otherwise its
        configured weight (however it's set) permanently deflates every
        signal's confidence for a strategy that can never vote. Becomes
        True automatically the moment a real model file is deployed and
        loads successfully, with no other code changes needed.
        """
        return MLModelStrategy._load_succeeded

    def analyze(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> StrategyResult:
        if not model_predictor.is_loaded() and not self._ensure_model_loaded():
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0,
                reasons=["ML model file not available"],
            )

        try:
            features_df = feature_engineer.extract_features(candles, timeframe=timeframe)
        except Exception as e:
            logger.warning(f"Feature extraction failed for {symbol}: {e}")
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0, reasons=["feature extraction failed"]
            )

        if features_df is None or features_df.empty:
            return StrategyResult(
                self.name, SignalDirection.HOLD, 0.0, 0.0, reasons=["feature extraction returned no rows"]
            )

        prediction, probability = model_predictor.predict_breakout(features_df.tail(1))

        if prediction == 1:
            return StrategyResult(
                self.name, SignalDirection.BUY, confidence=probability, score=probability,
                reasons=[f"ML model breakout probability {probability:.0%}"],
                metadata={"probability": probability},
            )
        return StrategyResult(
            self.name, SignalDirection.HOLD, confidence=0.0, score=0.0,
            reasons=[f"ML model breakout probability only {probability:.0%}"],
            metadata={"probability": probability},
        )
