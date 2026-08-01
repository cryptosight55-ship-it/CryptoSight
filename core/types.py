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


@dataclass
class AnalystOpinion:
    """
    Richer output shape for the phase-4 Context Intelligence Layer and
    (eventually) the multi-agent system -- a superset of StrategyResult.
    Not a replacement: the 5 existing rule/ML strategies still produce
    StrategyResult, and nothing forces them onto this. This exists so
    context providers and any future analyst have a place to put
    evidence/risk/entry-style detail that StrategyResult was never
    designed to carry, without a breaking change to what's already
    shipped and working.
    """

    source_name: str
    source_type: str  # "technical" | "context" | "chief_agent"
    direction: SignalDirection
    confidence: float
    evidence: List[str] = field(default_factory=list)
    reasoning: str = ""
    risks: List[str] = field(default_factory=list)
    invalidation_conditions: List[str] = field(default_factory=list)
    preferred_entry_style: Optional[str] = None
    expected_holding_time: Optional[str] = None
