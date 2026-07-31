"""
JSON API. Read-only for now (plus one action endpoint to trigger an AI
review pass) -- writing signals into the database from the actual
scanner/strategy pipeline is follow-up work, not done in this pass.
"""

import logging

from fastapi import APIRouter, HTTPException

from database.db import get_session
from database.models import SignalRecord, StrategyWeight
from ai.accuracy_reviewer import review_and_adjust_weights
from core.scanner import run_scan

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/signals")
def list_signals(limit: int = 50):
    with get_session() as session:
        rows = (
            session.query(SignalRecord)
            .order_by(SignalRecord.created_at.desc())
            .limit(min(limit, 200))
            .all()
        )
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "timeframe": r.timeframe,
                "direction": r.direction,
                "confidence": r.confidence,
                "entry_price": r.entry_price,
                "stop_loss": r.stop_loss,
                "take_profit": r.take_profit,
                "strategies_agreeing": r.strategies_agreeing,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


@router.get("/strategies/weights")
def list_weights():
    with get_session() as session:
        rows = session.query(StrategyWeight).all()
        return [
            {
                "strategy_name": w.strategy_name,
                "weight": w.weight,
                "enabled": w.enabled,
                "min_weight": w.min_weight,
                "max_weight": w.max_weight,
                "last_adjusted_by": w.last_adjusted_by,
            }
            for w in rows
        ]


@router.post("/strategies/review")
def trigger_review(dry_run: bool = False):
    try:
        return {"results": review_and_adjust_weights(dry_run=dry_run)}
    except Exception as e:
        logger.exception("AI review pass failed via API")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan/run")
def trigger_scan():
    """
    Manually run one scan pass (top 40 coins, 1h candles). Can take a
    while (network calls per symbol + backtesting for anything that
    fires) -- this is a synchronous call, so expect this request to be
    slow, not failed, if it's taking 30-60+ seconds.
    """
    try:
        return run_scan()
    except Exception as e:
        logger.exception("Manual scan trigger failed via API")
        raise HTTPException(status_code=500, detail=str(e))
