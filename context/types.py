"""
Shared types for the Context Intelligence Layer. Mirrors
strategies/base.py's Strategy/StrategyResult split deliberately -- same
pattern, applied to a new category of input (macro, news, sentiment,
on-chain, microstructure) instead of technical indicators.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.types import SignalDirection


@dataclass
class ContextSignal:
    provider_name: str
    category: str  # "macro" | "geopolitical" | "crypto_news" | "sentiment" | "onchain" | "microstructure"
    direction: SignalDirection  # HOLD doubles as "neutral" for context providers
    confidence: float  # 0.0-1.0, the provider's own confidence in this reading
    evidence: List[str] = field(default_factory=list)
    reasoning: str = ""
    staleness_seconds: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict)
