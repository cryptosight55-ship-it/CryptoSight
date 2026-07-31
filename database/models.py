"""
ORM models.

These replace the CSV files the original code used
(`data/trade_signals.csv`, `data/winrate_log.csv`) with real tables. The
existing CSV-based logic in `database/performance_tracker.py`,
`database/trade_monitor.py`, and `database/winrate.py` is UNCHANGED by
this file -- migrating those to use these tables instead of CSVs is
follow-up work, not done here, so nothing breaks today.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, JSON
)

from database.db import Base


class SignalRecord(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False, index=True)
    exchange = Column(String(32), default="binance")
    timeframe = Column(String(8), nullable=False)
    direction = Column(String(8), nullable=False)  # BUY / SELL / HOLD
    confidence = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    strategies_agreeing = Column(JSON, default=list)  # list[str] of strategy names
    reasons = Column(JSON, default=list)  # list[str]
    metadata_json = Column(JSON, default=dict)

    status = Column(String(16), default="pending")  # pending / win / loss / expired
    closed_at = Column(DateTime, nullable=True)
    pnl_pct = Column(Float, nullable=True)

    ai_explanation = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class StrategyWeight(Base):
    __tablename__ = "strategy_weights"

    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(64), unique=True, nullable=False)
    weight = Column(Float, default=1.0, nullable=False)
    enabled = Column(Boolean, default=True)
    min_weight = Column(Float, default=0.1)
    max_weight = Column(Float, default=5.0)
    last_adjusted_by = Column(String(16), default="manual")  # 'manual' or 'ai'
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))


class WeightAdjustmentLog(Base):
    """
    Audit trail for every AI-proposed weight change. Nothing about this
    system silently changes a weight -- every adjustment, whoever made
    it, is recorded here with the reasoning behind it.
    """
    __tablename__ = "weight_adjustment_log"

    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(64), nullable=False, index=True)
    old_weight = Column(Float, nullable=False)
    new_weight = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    win_rate = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)  # the AI's stated reasoning, verbatim
    source = Column(String(16), default="ai")  # 'ai' or 'manual'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
