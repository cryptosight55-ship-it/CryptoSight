"""
Base interface for context providers. A provider MUST NOT raise on a
missing/rate-limited/unconfigured data source -- it should return a
neutral, low-confidence ContextSignal instead, same as the ML strategy
returns HOLD when there's no model file. The pipeline should degrade
gracefully, never block on one provider being unavailable.
"""

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from context.types import ContextSignal


class ContextProvider(ABC):
    name: str = "unnamed_provider"
    category: str = "uncategorized"

    @abstractmethod
    def fetch(self, symbol: Optional[str] = None) -> ContextSignal:
        """
        symbol=None for global/macro providers (not implemented yet in
        Phase 4a). A real symbol for per-asset providers like
        microstructure. Must never raise -- catch your own exceptions
        and return a neutral ContextSignal with reasoning explaining why.
        """
        raise NotImplementedError
