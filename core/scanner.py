"""
The hourly scan job. This is what actually generates signals now --
previously this same role was played by cli/main.py calling straight
into the single ML model. This calls signals/aggregator.py instead,
which requires 3-of-5 strategies to agree.

Scans on 1h candles (500 back, ~20 days of history) across the top 40
USDT pairs by 24h volume on Binance. Runs via APScheduler in
admin/server.py, on the hour, every hour -- and can also be triggered
manually from the admin panel or POST /api/scan/run.
"""

import logging
from datetime import datetime, timezone

import ccxt

from data.fetcher import get_data_fetcher
from signals.aggregator import aggregate
from backtesting.quick_backtest import quick_backtest
from context.aggregator import gather_context
from database.db import get_session
from database.models import SignalRecord
from alerts.discord_alerts import alert_manager
from ai.openrouter_client import openrouter_client
from ai.signal_explainer import explain_signal
from core.types import SignalDirection

logger = logging.getLogger(__name__)

TOP_N_COINS = 40
SCAN_TIMEFRAME = "1h"
CANDLE_LOOKBACK = 500
ALERT_DURATION_HOURS = 24  # matches backtesting.quick_backtest.LOOKFORWARD_BARS on 1h candles


def _build_discord_payload(signal: dict) -> dict:
    entry = signal["entry_price"]
    take_profit = signal["take_profit"]
    tp_distance = take_profit - entry
    return {
        "symbol": signal["symbol"],
        "direction": "LONG" if signal["direction"] == SignalDirection.BUY else "SHORT",
        "probability": signal["confidence"],
        "timeframe": signal["timeframe"],
        "entry": entry,
        "stoploss": signal["stop_loss"],
        "tp1": take_profit,
        "tp2": entry + 1.5 * tp_distance,
        "tp3": entry + 2.0 * tp_distance,
        "duration_hours": ALERT_DURATION_HOURS,
    }


def _process_symbol(symbol: str) -> dict:
    fetcher = get_data_fetcher()
    candles = fetcher.fetch_live_data(symbol, timeframe=SCAN_TIMEFRAME, limit=CANDLE_LOOKBACK)
    if candles is None or len(candles) < 60:
        return {"symbol": symbol, "action": "skipped_insufficient_data"}

    # First pass: no context. This decides whether a signal exists at
    # all (the 3-of-5 technical gate + regime weighting) without any
    # extra API calls. Context data (funding rate, order book, etc.) is
    # only fetched for symbols that already cleared this gate -- same
    # reasoning as quick_backtest being scoped to firing symbols only:
    # bound the request volume, learned the hard way from an earlier
    # Binance rate-limit ban in this project.
    preliminary = aggregate(symbol, SCAN_TIMEFRAME, candles)
    if preliminary is None:
        return {"symbol": symbol, "action": "no_signal"}

    context_signals = gather_context(symbol)
    signal = aggregate(symbol, SCAN_TIMEFRAME, candles, context_signals=context_signals)
    if signal is None:
        # Shouldn't happen -- context never changes the gate decision,
        # only the confidence score -- but fall back defensively rather
        # than lose a signal that already cleared the gate once.
        logger.warning(f"Signal for {symbol} disappeared on second aggregate() pass, using first pass")
        signal = preliminary

    backtest_result = quick_backtest(symbol, SCAN_TIMEFRAME, candles)

    ai_explanation = None
    if openrouter_client.is_configured():
        ai_explanation = explain_signal(
            symbol=symbol,
            direction=signal["direction"].value,
            confidence=signal["confidence"],
            reasons=signal["reasons"],
            timeframe=SCAN_TIMEFRAME,
        )

    metadata = {
        "atr": signal["atr"],
        "backtest": backtest_result,
        "regime": signal.get("regime"),
        "base_confidence": signal.get("base_confidence"),
        "context_evidence": signal.get("context_evidence", []),
        "strategy_details": [
            {
                "strategy": r.strategy_name,
                "signal": r.signal.value,
                "confidence": float(r.confidence),
                "reasons": r.reasons,
            }
            for r in signal["all_results"]
        ],
    }

    with get_session() as session:
        record = SignalRecord(
            symbol=signal["symbol"],
            timeframe=signal["timeframe"],
            direction=signal["direction"].value,
            confidence=signal["confidence"],
            entry_price=signal["entry_price"],
            stop_loss=signal["stop_loss"],
            take_profit=signal["take_profit"],
            strategies_agreeing=signal["strategies_agreeing"],
            reasons=signal["reasons"],
            metadata_json=metadata,
            ai_explanation=ai_explanation,
        )
        session.add(record)

    try:
        alert_manager.send_discord_alert(_build_discord_payload(signal))
    except Exception as e:
        logger.warning(f"Discord alert failed for {symbol}: {e}")

    return {
        "symbol": symbol,
        "action": "signal_fired",
        "direction": signal["direction"].value,
        "confidence": signal["confidence"],
        "strategies_agreeing": signal["strategies_agreeing"],
        "backtest_win_rate": backtest_result["win_rate"] if backtest_result else None,
    }


def run_scan() -> dict:
    """Runs one full scan pass. Returns a summary dict for logging/API/admin display."""
    started_at = datetime.now(timezone.utc)

    try:
        fetcher = get_data_fetcher()
        symbols = fetcher.get_top_coins(limit=TOP_N_COINS)
    except Exception as e:
        logger.error(f"Failed to initialize exchange / get top coins for scan: {e}")
        return {"error": str(e), "started_at": started_at.isoformat()}

    results = []
    for symbol in symbols:
        try:
            results.append(_process_symbol(symbol))
        except (ccxt.DDoSProtection, ccxt.RateLimitExceeded) as e:
            # Binance is actively throttling/banning us -- stop immediately
            # rather than burning through the remaining symbols into the
            # same wall, which only makes any ban last longer.
            logger.error(f"Exchange rate-limited/banned mid-scan at {symbol}, stopping scan: {e}")
            results.append({"symbol": symbol, "action": "error", "error": str(e)})
            break
        except Exception as e:
            logger.exception(f"Scan failed for {symbol}")
            results.append({"symbol": symbol, "action": "error", "error": str(e)})

    signals_fired = [r for r in results if r.get("action") == "signal_fired"]
    logger.info(
        f"Scan complete: {len(results)}/{len(symbols)} symbols processed, "
        f"{len(signals_fired)} signals fired"
    )

    return {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "symbols_scanned": len(results),
        "signals_fired": len(signals_fired),
        "results": results,
    }
