"""
Single shared-password auth for the admin panel, per your choice of
"simplest, fine for one-person use." Session is a signed cookie
(Starlette's SessionMiddleware, keyed by config.SECRET_KEY) -- no
password hashes to manage, no user table. If you outgrow this later
(multiple admins), swap this module for real per-user auth without
touching the rest of the admin/ routes -- they only depend on
`require_login`.
"""

from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from starlette import status

from config.settings import config


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("logged_in"))


def check_password(password: str) -> bool:
    if not config.ADMIN_PASSWORD:
        # Fail closed: an unset password should never mean "anyone can log in."
        return False
    return password == config.ADMIN_PASSWORD


def require_login(request: Request):
    """FastAPI dependency: raises a redirect-to-login if not authenticated."""
    if not is_logged_in(request):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
        )
    return True


def login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
