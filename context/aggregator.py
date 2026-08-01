"""
Runs every registered context provider for a symbol and returns their
ContextSignals. Deliberately thin -- as more providers land in later
phases (4b: Fear & Greed, crypto news; 4c/4d: macro, on-chain, social),
they get added to PROVIDERS and nothing else here needs to change.
"""

import logging
from typing import List, Optional

from context.base import ContextProvider
from context.types import ContextSignal
from context.providers.microstructure import MicrostructureProvider

logger = logging.getLogger(__name__)

PROVIDERS: List[ContextProvider] = [
    MicrostructureProvider(),
]


def gather_context(symbol: Optional[str] = None) -> List[ContextSignal]:
    signals = []
    for provider in PROVIDERS:
        try:
            signals.append(provider.fetch(symbol))
        except Exception as e:
            # Providers are supposed to catch their own exceptions and
            # return a neutral ContextSignal -- this is a last-resort
            # backstop so one broken provider can't take down a scan.
            logger.warning(f"Context provider '{provider.name}' raised unexpectedly: {e}")
    return signals
