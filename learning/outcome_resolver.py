"""
Resolves pending signals to win/loss/expired.

This didn't exist before Phase 4 -- SignalRecord.status started at
"pending" and nothing ever moved it. That meant ai/accuracy_reviewer.py
was structurally unable to do anything: it only looks at signals with
status in ("win", "loss"), so with zero ever resolved, every strategy
permanently reported "not enough samples." This closes that gap.

Runs on a schedule (see admin/server.py) and can also be triggered
manually. Uses `data/fetcher.py: fetch_historical_data()`, capped to a
few days back -- a signal that hasn't resolved within
config.TRADE_TIMEOUT_HOURS (48h) is marked "expired" rather than left
pending forever.
"""

import logging
from datetime import datetime, timezone, timedelta

import ccxt

from config.settings import config
from data.fetcher import get_data_fetcher
from database.db import get_session
from database.models import SignalRecord
from core.types import SignalDirection

logger = logging.getLogger(__name__)

MIN_AGE_BEFORE_CHECKING = timedelta(hours=1)  # give at least one candle time to close
HISTORY_DAYS_BACK = 4  # comfortably covers TRADE_TIMEOUT_HOURS (48h) plus buffer


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _resolve_one(record: SignalRecord) -> tuple:
    """
    Returns (status, closed_at, pnl_pct) or (None, None, None) if it's
    genuinely still too early to tell (not enough time/data yet).
    """
    fetcher = get_data_fetcher()
    candles = fetcher.fetch_historical_data(record.symbol, record.timeframe, days_back=HISTORY_DAYS_BACK)
    if candles is None or candles.empty:
        return None, None, None

    created_at = _as_utc(record.created_at)
    future = candles[candles["timestamp"] > created_at]
    if future.empty:
        return None, None, None

    direction = SignalDirection(record.direction)
    entry = record.entry_price
    stop_loss = record.stop_loss
    take_profit = record.take_profit
    timeout_at = created_at + timedelta(hours=config.TRADE_TIMEOUT_HOURS)

    for _, row in future.iterrows():
        candle_time = row["timestamp"]
        if candle_time > timeout_at:
            break

        high, low = row["high"], row["low"]
        if direction == SignalDirection.BUY:
            hit_sl, hit_tp = low <= stop_loss, high >= take_profit
        else:
            hit_sl, hit_tp = high >= stop_loss, low <= take_profit

        if hit_sl:
            pnl_pct = (stop_loss - entry) / entry * 100 if direction == SignalDirection.BUY \
                else (entry - stop_loss) / entry * 100
            return "loss", candle_time, round(float(pnl_pct), 4)
        if hit_tp:
            pnl_pct = (take_profit - entry) / entry * 100 if direction == SignalDirection.BUY \
                else (entry - take_profit) / entry * 100
            return "win", candle_time, round(float(pnl_pct), 4)

    # Neither hit within the window. If the timeout has actually passed,
    # mark expired using the last available close as a mark-to-market.
    now = datetime.now(timezone.utc)
    if now > timeout_at:
        last_close = float(future.iloc[-1]["close"])
        pnl_pct = (last_close - entry) / entry * 100 if direction == SignalDirection.BUY \
            else (entry - last_close) / entry * 100
        return "expired", now, round(pnl_pct, 4)

    return None, None, None  # still legitimately pending


def resolve_pending_signals() -> dict:
    """Checks every pending signal old enough to have at least one closed
    candle, and resolves the ones that can be resolved. Returns a summary."""
    now = datetime.now(timezone.utc)
    resolved = []
    errors = []

    with get_session() as session:
        pending = session.query(SignalRecord).filter_by(status="pending").all()
        eligible = [r for r in pending if now - _as_utc(r.created_at) >= MIN_AGE_BEFORE_CHECKING]

        for record in eligible:
            try:
                status, closed_at, pnl_pct = _resolve_one(record)
            except (ccxt.DDoSProtection, ccxt.RateLimitExceeded) as e:
                # Binance is actively throttling/banning us -- stop the
                # whole resolution pass immediately rather than
                # continuing to the next signal. This is what previously
                # turned one ban into 40+ rapid reconnection attempts,
                # one per pending signal, with zero delay between them --
                # see get_data_fetcher()'s cooldown in data/fetcher.py,
                # which this also relies on to fail fast on the very next
                # scheduled run instead of retrying immediately.
                logger.error(f"Exchange rate-limited/banned mid-resolution at signal {record.id}, stopping: {e}")
                errors.append({"id": record.id, "symbol": record.symbol, "error": str(e)})
                break
            except Exception as e:
                logger.warning(f"Failed to resolve signal {record.id} ({record.symbol}): {e}")
                errors.append({"id": record.id, "symbol": record.symbol, "error": str(e)})
                continue

            if status is not None:
                record.status = status
                record.closed_at = closed_at
                record.pnl_pct = pnl_pct
                resolved.append({"id": record.id, "symbol": record.symbol, "status": status, "pnl_pct": pnl_pct})

    logger.info(f"Outcome resolution: {len(resolved)} resolved out of {len(pending)} pending")
    return {
        "checked": len(pending),
        "eligible": len(eligible),
        "resolved": len(resolved),
        "results": resolved,
        "errors": errors,
    }
