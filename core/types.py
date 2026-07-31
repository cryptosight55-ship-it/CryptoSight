"""
Shared types for the strategy/signal layer.

STATUS: scaffolding only. Nothing in the codebase constructs or consumes
these yet -- signals/generator.py (the relocated src/signal_generator.py)
still runs its original single-model logic untouched. These types exist
so the next phase (building out /strategies as independent plugins and
wiring them into an aggregator) has an agreed-upon contract to build
against, per the "Strategy System" section of the project brief.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategyResult:
    """Standardized output every strategy plugin should return from analyze()."""

    strategy_name: str
    signal: SignalDirection
    confidence: float  # 0.0 - 1.0
    score: float  # strategy's own internal score, arbitrary scale, for debugging/tuning
    reasons: List[str] = field(default_factory=list)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
