"""
AI-assisted strategy weight tuning.

WHAT THIS DOES: periodically looks at each strategy's recent closed
signals (win rate, sample size), asks the configured OpenRouter model to
recommend a weight adjustment with reasoning, and applies it -- within
hard guardrails that the AI cannot override:

  1. A strategy only gets adjusted once it has at least
     `AI_MIN_SAMPLES_FOR_ADJUSTMENT` closed signals. Small samples are
     noise, not signal -- don't let the AI chase noise.
  2. A single run can move a weight by at most
     `AI_MAX_WEIGHT_STEP_PCT` (default 20%) in either direction, so a bad
     AI call can't swing a weight to zero or to the max in one shot.
  3. The result is always clamped to
     [AI_MIN_STRATEGY_WEIGHT, AI_MAX_STRATEGY_WEIGHT] regardless of what
     the AI proposes.
  4. Every adjustment -- the before/after weight, the sample it was
     based on, and the AI's stated reasoning -- is written to
     WeightAdjustmentLog. Nothing is applied silently.

This never touches signal generation directly. It only updates
`StrategyWeight.weight`, which the (future) signal aggregator reads when
combining strategy opinions. Today, before that aggregator exists, this
module is safe to run -- it will just maintain weight rows without
anything downstream consuming them yet.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func

from config.settings import config
from database.db import get_session
from database.models import SignalRecord, StrategyWeight, WeightAdjustmentLog
from ai.openrouter_client import openrouter_client, OpenRouterError

logger = logging.getLogger(__name__)


def _strategy_performance(session, strategy_name: str) -> Optional[dict]:
    """Pull win rate and sample size for one strategy from closed signals."""
    closed = (
        session.query(SignalRecord)
        .filter(SignalRecord.status.in_(["win", "loss"]))
        .filter(SignalRecord.strategies_agreeing.isnot(None))
        .all()
    )
    relevant = [s for s in closed if strategy_name in (s.strategies_agreeing or [])]
    sample_size = len(relevant)
    if sample_size == 0:
        return {"sample_size": 0, "win_rate": None, "avg_pnl_pct": None}

    wins = sum(1 for s in relevant if s.status == "win")
    pnls = [s.pnl_pct for s in relevant if s.pnl_pct is not None]
    return {
        "sample_size": sample_size,
        "win_rate": round(wins / sample_size, 4),
        "avg_pnl_pct": round(sum(pnls) / len(pnls), 4) if pnls else None,
    }


def _ask_ai_for_adjustment(strategy_name: str, current_weight: float, perf: dict) -> dict:
    """
    Ask the AI for a proposed new weight + reasoning. Returns a dict with
    keys 'new_weight' (float) and 'reasoning' (str). Raises OpenRouterError
    on failure -- caller decides how to handle that (we skip the strategy).
    """
    system_prompt = (
        "You are a conservative risk analyst reviewing the performance of one "
        "trading signal strategy inside a larger multi-strategy system. You are "
        "adjusting an influence WEIGHT (not a trade, not a position, not money) "
        "that controls how much this strategy's vote counts relative to others. "
        "Be conservative: small performance differences should produce small "
        "weight changes. Respond ONLY with a JSON object: "
        '{"new_weight": <number>, "reasoning": "<one or two sentences>"}.'
    )
    user_prompt = (
        f"Strategy: {strategy_name}\n"
        f"Current weight: {current_weight}\n"
        f"Closed-signal sample size: {perf['sample_size']}\n"
        f"Win rate: {perf['win_rate']}\n"
        f"Average P&L per signal: {perf['avg_pnl_pct']}\n\n"
        "Propose a new weight. If performance looks roughly in line with a "
        "50% win rate and neutral P&L, keep the weight close to where it is."
    )

    result = openrouter_client.chat_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    if "new_weight" not in result:
        raise OpenRouterError(f"AI response missing 'new_weight': {result}")
    return result


def review_and_adjust_weights(dry_run: bool = False) -> list:
    """
    Run one review pass over every strategy in StrategyWeight.
    Returns a list of dicts describing what happened for each strategy
    (adjusted, skipped-low-sample, skipped-error), for logging/display in
    the admin panel.
    """
    results = []
    with get_session() as session:
        strategies = session.query(StrategyWeight).filter_by(enabled=True).all()

        for sw in strategies:
            perf = _strategy_performance(session, sw.strategy_name)

            if perf["sample_size"] < config.AI_MIN_SAMPLES_FOR_ADJUSTMENT:
                results.append({
                    "strategy": sw.strategy_name,
                    "action": "skipped_low_sample",
                    "sample_size": perf["sample_size"],
                    "required": config.AI_MIN_SAMPLES_FOR_ADJUSTMENT,
                })
                continue

            try:
                ai_result = _ask_ai_for_adjustment(sw.strategy_name, sw.weight, perf)
            except OpenRouterError as e:
                logger.warning(f"AI weight review failed for {sw.strategy_name}: {e}")
                results.append({
                    "strategy": sw.strategy_name,
                    "action": "skipped_error",
                    "error": str(e),
                })
                continue

            proposed = float(ai_result["new_weight"])
            reasoning = str(ai_result.get("reasoning", ""))

            # --- guardrails, applied regardless of what the AI proposed ---
            max_step = sw.weight * config.AI_MAX_WEIGHT_STEP_PCT
            bounded = max(sw.weight - max_step, min(sw.weight + max_step, proposed))
            bounded = max(sw.min_weight or config.AI_MIN_STRATEGY_WEIGHT,
                           min(sw.max_weight or config.AI_MAX_STRATEGY_WEIGHT, bounded))
            new_weight = round(bounded, 4)

            log_entry = WeightAdjustmentLog(
                strategy_name=sw.strategy_name,
                old_weight=sw.weight,
                new_weight=new_weight,
                sample_size=perf["sample_size"],
                win_rate=perf["win_rate"],
                reasoning=reasoning,
                source="ai",
            )
            session.add(log_entry)

            if not dry_run:
                sw.weight = new_weight
                sw.last_adjusted_by = "ai"
                sw.updated_at = datetime.now(timezone.utc)

            results.append({
                "strategy": sw.strategy_name,
                "action": "adjusted" if not dry_run else "would_adjust",
                "old_weight": log_entry.old_weight,
                "new_weight": new_weight,
                "ai_proposed": proposed,
                "reasoning": reasoning,
                "sample_size": perf["sample_size"],
                "win_rate": perf["win_rate"],
            })

    return results
