"""
Admin panel routes. Server-rendered Jinja2 templates, HTMX for the
in-page refreshes (signals table, weights table, review results) so
there's no separate frontend build step -- fits Render's simplest
deploy path.

NOTE: TemplateResponse calls use the current Starlette signature
(`templates.TemplateResponse(request, "name.html", {...})`), not the
older `TemplateResponse("name.html", {"request": request, ...})` style.
The older style triggered a `TypeError: unhashable type: 'dict'` on
recent Starlette versions -- keep using the request-first form here.
"""

import logging

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from config.settings import config
from database.db import get_session
from database.models import SignalRecord, StrategyWeight, WeightAdjustmentLog
from admin.auth import check_password, require_login, is_logged_in
from ai.accuracy_reviewer import review_and_adjust_weights
from core.scanner import run_scan
from learning.outcome_resolver import resolve_pending_signals

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="admin/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_logged_in(request):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, password: str = Form(...)):
    if check_password(password):
        request.session["logged_in"] = True
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request, "login.html", {"error": "Incorrect password."}
    )


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, _=Depends(require_login)):
    with get_session() as session:
        recent_signals = (
            session.query(SignalRecord).order_by(SignalRecord.created_at.desc()).limit(20).all()
        )
        weights = session.query(StrategyWeight).all()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"signals": recent_signals, "weights": weights},
    )


@router.get("/signals/{signal_id}", response_class=HTMLResponse)
def signal_detail(request: Request, signal_id: int, _=Depends(require_login)):
    with get_session() as session:
        record = session.query(SignalRecord).get(signal_id)
    if record is None:
        return HTMLResponse("Signal not found", status_code=404)
    return templates.TemplateResponse(request, "signal_detail.html", {"s": record})


@router.get("/signals", response_class=HTMLResponse)
def signals_partial(request: Request, _=Depends(require_login)):
    with get_session() as session:
        recent_signals = (
            session.query(SignalRecord).order_by(SignalRecord.created_at.desc()).limit(50).all()
        )
    return templates.TemplateResponse(
        request, "partials/signals_table.html", {"signals": recent_signals}
    )


@router.get("/weights", response_class=HTMLResponse)
def weights_partial(request: Request, _=Depends(require_login)):
    with get_session() as session:
        weights = session.query(StrategyWeight).all()
    return templates.TemplateResponse(
        request, "partials/weights_table.html", {"weights": weights}
    )


@router.post("/weights/review", response_class=HTMLResponse)
def run_ai_review(request: Request, _=Depends(require_login)):
    try:
        results = review_and_adjust_weights()
        error = None
    except Exception as e:
        logger.exception("AI weight review pass failed")
        results = []
        error = str(e)
    return templates.TemplateResponse(
        request, "partials/review_results.html", {"results": results, "error": error}
    )


@router.post("/scan/run", response_class=HTMLResponse)
def trigger_scan(request: Request, _=Depends(require_login)):
    try:
        summary = run_scan()
        error = summary.get("error")
    except Exception as e:
        logger.exception("Manual scan trigger failed")
        summary = {}
        error = str(e)
    return templates.TemplateResponse(
        request, "partials/scan_results.html", {"summary": summary, "error": error}
    )


@router.post("/outcomes/resolve", response_class=HTMLResponse)
def trigger_resolve_outcomes(request: Request, _=Depends(require_login)):
    try:
        summary = resolve_pending_signals()
        error = None
    except Exception as e:
        logger.exception("Manual outcome resolution failed")
        summary = {}
        error = str(e)
    return templates.TemplateResponse(
        request, "partials/resolve_results.html", {"summary": summary, "error": error}
    )


@router.post("/weights/{weight_id}", response_class=HTMLResponse)
def update_weight_manually(
    request: Request, weight_id: int, weight: float = Form(...), _=Depends(require_login)
):
    with get_session() as session:
        sw = session.query(StrategyWeight).get(weight_id)
        if sw:
            old = sw.weight
            sw.weight = max(sw.min_weight, min(sw.max_weight, weight))
            sw.last_adjusted_by = "manual"
            session.add(WeightAdjustmentLog(
                strategy_name=sw.strategy_name,
                old_weight=old,
                new_weight=sw.weight,
                sample_size=0,
                win_rate=None,
                reasoning="Manually set from admin panel.",
                source="manual",
            ))
        weights = session.query(StrategyWeight).all()
    return templates.TemplateResponse(
        request, "partials/weights_table.html", {"weights": weights}
    )


@router.get("/logs", response_class=HTMLResponse)
def adjustment_log(request: Request, _=Depends(require_login)):
    with get_session() as session:
        logs = (
            session.query(WeightAdjustmentLog)
            .order_by(WeightAdjustmentLog.created_at.desc())
            .limit(100)
            .all()
        )
    return templates.TemplateResponse(
        request, "logs.html", {"logs": logs}
    )
