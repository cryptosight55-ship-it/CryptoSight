"""
Nightly review job: the piece deliberately deferred back in the phase-4
roadmap ("Phase 4b, held back until there's real resolved-signal
history"). There's real history now, so this is that piece.

WHAT THIS DOES: groups resolved signals (win/loss, not pending/expired)
by (strategy, regime) -- regime comes from the `regime` list stored on
each signal's metadata_json at signal time (see signals/aggregator.py) --
and computes win rate + average P&L per group. Where a group has enough
samples, writes a LearnedInsight row describing what was found.

WHY STATISTICAL GROUPING, NOT ML OR AN LLM CALL: with the signal volume
this system realistically produces (tens to low hundreds a week), a
trained model would overfit long before grouped win-rates would
mislead you -- this was the explicit design call in the roadmap doc.
Plain-language descriptions are templated in Python, not AI-generated,
for the same reason: no need to spend an API call generating text that
a template can express exactly as accurately.

GUARDRAIL AGAINST FRAGMENTING THE DATA TOO THIN: this groups by ONE
dimension (regime) on top of strategy, not regime-combinations or
regime x context. A signal exhibiting multiple regime labels (e.g.
trending AND high_volatility) contributes to each relevant regime's
bucket separately, rather than creating a combined
"trending+high_volatility" bucket that would need even more samples to
mean anything. Add more dimensions later only once single-dimension
groups are consistently getting enough samples to be worth slicing
further -- see the roadmap doc.

This NEVER touches StrategyWeight directly. It's an observation log,
browsable in the admin panel, meant to inform a human (or a future,
more sophisticated adjustment mechanism) -- not another automatic
weight-adjustment path alongside ai/accuracy_reviewer.py.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Any

from database.db import get_session
from database.models import SignalRecord, LearnedInsight

logger = logging.getLogger(__name__)

MIN_SAMPLES_PER_GROUP = 8  # deliberately lower than AI_MIN_SAMPLES_FOR_ADJUSTMENT (20) --
                            # this is an observation log, not a weight-adjustment trigger,
                            # and regime-slicing already costs sample size. Still high
                            # enough that a handful of signals can't drive a conclusion.


def _collect_resolved_signals(session) -> List[SignalRecord]:
    return session.query(SignalRecord).filter(SignalRecord.status.in_(["win", "loss"])).all()


def _group_by_strategy_and_regime(signals: List[SignalRecord]) -> Dict[Tuple[str, str], List[SignalRecord]]:
    groups: Dict[Tuple[str, str], List[SignalRecord]] = defaultdict(list)
    for s in signals:
        strategies = s.strategies_agreeing or []
        regimes = ((s.metadata_json or {}).get("regime") or {}).get("regimes") or []
        for strategy_name in strategies:
            for regime in regimes:
                groups[(strategy_name, regime)].append(s)
    return groups


def _describe(strategy_name: str, regime: str, group: List[SignalRecord]) -> Dict[str, Any]:
    n = len(group)
    wins = sum(1 for s in group if s.status == "win")
    win_rate = wins / n
    pnls = [s.pnl_pct for s in group if s.pnl_pct is not None]
    avg_pnl = sum(pnls) / len(pnls) if pnls else None

    pnl_text = f"{avg_pnl:+.2f}% average P&L" if avg_pnl is not None else "P&L not available"
    description = (
        f"'{strategy_name}' during '{regime}' regime: {win_rate:.0%} win rate "
        f"over {n} resolved signals, {pnl_text}."
    )

    return {
        "strategy_name": strategy_name,
        "regime": regime,
        "sample_size": n,
        "win_rate": round(win_rate, 4),
        "avg_pnl_pct": round(avg_pnl, 4) if avg_pnl is not None else None,
        "description": description,
        "supporting_stats": {"wins": wins, "losses": n - wins},
    }


def run_nightly_review() -> Dict[str, Any]:
    written = []
    skipped = []

    with get_session() as session:
        signals = _collect_resolved_signals(session)
        groups = _group_by_strategy_and_regime(signals)

        for (strategy_name, regime), group in groups.items():
            if len(group) < MIN_SAMPLES_PER_GROUP:
                skipped.append({"strategy": strategy_name, "regime": regime, "sample_size": len(group)})
                continue

            info = _describe(strategy_name, regime, group)
            session.add(LearnedInsight(
                strategy_name=info["strategy_name"],
                regime=info["regime"],
                sample_size=info["sample_size"],
                win_rate=info["win_rate"],
                avg_pnl_pct=info["avg_pnl_pct"],
                description=info["description"],
                supporting_stats=info["supporting_stats"],
            ))
            written.append(info)

    logger.info(f"Nightly review: {len(written)} insight(s) written, {len(skipped)} group(s) still too small")
    return {"written": written, "skipped": skipped, "total_resolved_signals": len(signals)}
