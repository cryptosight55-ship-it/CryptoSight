"""
Turns a signal's structured data into a short plain-language explanation.
Purely additive/cosmetic -- never influences the signal itself, only
explains one after the fact. If the AI call fails, callers should fall
back to showing the raw reasons list instead (see usage in
alerts/discord_alerts.py once wired in).
"""

import logging
from typing import List, Optional

from ai.openrouter_client import openrouter_client, OpenRouterError

logger = logging.getLogger(__name__)


def explain_signal(
    symbol: str,
    direction: str,
    confidence: float,
    reasons: List[str],
    timeframe: str,
) -> Optional[str]:
    """Returns a 1-3 sentence explanation, or None if the AI call fails."""
    prompt = (
        f"A trading signal system flagged {symbol} as a {direction} on the "
        f"{timeframe} timeframe with {confidence:.0%} confidence. "
        f"Contributing reasons: {', '.join(reasons) if reasons else 'none listed'}. "
        "Write a 1-3 sentence plain-language summary of why this signal fired, "
        "for a trader who wants a quick gut-check before looking at the chart "
        "themselves. Do not tell them to buy or sell -- describe the setup only."
    )
    try:
        return openrouter_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
        ).strip()
    except OpenRouterError as e:
        logger.warning(f"Signal explanation failed for {symbol}: {e}")
        return None
