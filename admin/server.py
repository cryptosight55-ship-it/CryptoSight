"""
Application entrypoint for Render.

Run locally with:
    uvicorn admin.server:app --reload

Render's start command (see render.yaml / Procfile):
    uvicorn admin.server:app --host 0.0.0.0 --port $PORT
"""

import logging

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import config
from database.db import init_db, get_session
from database.models import StrategyWeight
from admin.routes import router as admin_router
from api.routes import router as api_router
from signals.aggregator import ALL_STRATEGIES
from core.scanner import run_scan
from learning.outcome_resolver import resolve_pending_signals

logger = logging.getLogger(__name__)

app = FastAPI(title="CryptoSight")

if not config.SECRET_KEY:
    # A missing SECRET_KEY would mean sessions can't be signed at all --
    # fail loudly at startup rather than silently running an insecure
    # random key that changes on every restart (logging everyone out).
    raise RuntimeError(
        "SECRET_KEY is not set. Generate one (e.g. `openssl rand -hex 32`) "
        "and set it in your environment before starting the app."
    )

app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)
app.mount("/static", StaticFiles(directory="admin/static"), name="static")

app.include_router(admin_router)
app.include_router(api_router)

scheduler = BackgroundScheduler()


def _seed_default_strategy_weights():
    """
    Ensure every strategy in signals/aggregator.py's ALL_STRATEGIES has a
    weight row, so the admin panel and AI reviewer always reflect exactly
    what's actually running. Adding a 6th strategy later means adding it
    to ALL_STRATEGIES -- it'll get seeded here automatically on next boot,
    no other change needed.
    """
    with get_session() as session:
        existing = {w.strategy_name for w in session.query(StrategyWeight).all()}
        for strat in ALL_STRATEGIES:
            if strat.name not in existing:
                session.add(StrategyWeight(strategy_name=strat.name, weight=1.0))


def _scheduled_scan():
    logger.info("Running scheduled hourly scan")
    try:
        result = run_scan(bypass_cooldown=True)
        logger.info(f"Scheduled scan result: {result.get('signals_fired')} signals fired")
    except Exception:
        logger.exception("Scheduled scan failed")


def _scheduled_resolve_outcomes():
    logger.info("Running scheduled outcome resolution")
    try:
        result = resolve_pending_signals()
        logger.info(f"Scheduled outcome resolution: {result.get('resolved')} resolved")
    except Exception:
        logger.exception("Scheduled outcome resolution failed")


@app.on_event("startup")
def on_startup():
    config.setup_logging()
    config.ensure_directories()
    init_db()
    _seed_default_strategy_weights()

    # Runs on the hour, every hour (e.g. 13:00, 14:00, ...). A single
    # in-process scheduler is fine at this scale; if scans start taking
    # long enough to risk overlapping with the admin panel's own
    # requests, move this to a separate Render Cron Job / Background
    # Worker hitting the same database instead.
    scheduler.add_job(_scheduled_scan, CronTrigger(minute=0), id="hourly_scan", replace_existing=True)
    # Offset by 15 minutes so it doesn't compete with the scan job on
    # the same tick. Runs more often than signals actually need
    # resolving (most won't be eligible yet -- MIN_AGE_BEFORE_CHECKING
    # in learning/outcome_resolver.py), which is fine, it's a cheap no-op
    # for anything not old enough yet.
    scheduler.add_job(_scheduled_resolve_outcomes, CronTrigger(minute=15), id="resolve_outcomes", replace_existing=True)
    scheduler.start()

    logger.info("CryptoSight admin app started")


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown(wait=False)


@app.get("/")
def root():
    return {"service": "CryptoSight", "admin": "/admin", "api": "/api/health"}
