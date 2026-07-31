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

from config.settings import config
from database.db import init_db, get_session
from database.models import StrategyWeight
from admin.routes import router as admin_router
from api.routes import router as api_router

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


def _seed_default_strategy_weights():
    """
    Ensure the existing ML model has a weight row so the admin panel and
    AI reviewer have something to show/act on immediately. Additional
    strategies (per the phase-2 plan) register themselves here the same
    way once they exist -- this function is the one place that needs to
    grow, nothing else.
    """
    with get_session() as session:
        existing = {w.strategy_name for w in session.query(StrategyWeight).all()}
        if "ml_model" not in existing:
            session.add(StrategyWeight(strategy_name="ml_model", weight=1.0))


@app.on_event("startup")
def on_startup():
    config.setup_logging()
    config.ensure_directories()
    init_db()
    _seed_default_strategy_weights()
    logger.info("CryptoSight admin app started")


@app.get("/")
def root():
    return {"service": "CryptoSight", "admin": "/admin", "api": "/api/health"}
