from __future__ import annotations

import math
import os
import secrets
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.rate_limit import FailedAttemptLimiter

SESSION_COOKIE = "vigiapet_session"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "testserver")
PUBLIC_API_PATHS = frozenset({"/api/session"})
UNAUTHENTICATED_DETAIL = "Sessão não autenticada. Abra o Monitora Pet pelo aplicativo."
LOCKED_DETAIL = "Muitas tentativas de autenticação. Aguarde {seconds} segundos."

LIMITER = FailedAttemptLimiter()


def _configured_token() -> str | None:
    value = os.getenv("VIGIAPET_API_TOKEN", "").strip()
    return value or None


def _configured_hosts() -> list[str]:
    extra = [host.strip() for host in os.getenv("VIGIAPET_ALLOWED_HOSTS", "").split(",")]
    return [*LOCAL_HOSTS, *(host for host in extra if host)]


API_TOKEN = _configured_token()
ALLOWED_HOSTS = _configured_hosts()


def auth_required() -> bool:
    return API_TOKEN is not None


def is_valid_token(candidate: str | None) -> bool:
    if API_TOKEN is None or not candidate:
        return False
    return secrets.compare_digest(candidate.encode("utf-8"), API_TOKEN.encode("utf-8"))


def token_from_request(request: Request) -> str | None:
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return request.cookies.get(SESSION_COOKIE)


def is_protected_path(path: str) -> bool:
    return path.startswith("/api/") and path.rstrip("/") not in PUBLIC_API_PATHS


def authorized(request: Request) -> bool:
    if API_TOKEN is None or not is_protected_path(request.url.path):
        return True
    return is_valid_token(token_from_request(request))


def client_origin(request: Request) -> str:
    return request.client.host if request.client and request.client.host else "local"


def locked_response(seconds: float) -> JSONResponse:
    wait = max(1, math.ceil(seconds))
    return JSONResponse(
        status_code=429,
        content={"detail": LOCKED_DETAIL.format(seconds=wait)},
        headers={"Retry-After": str(wait)},
    )


def install_access_control(app: FastAPI) -> None:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.middleware("http")
    async def session_guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path
        if path.startswith("/api/"):
            origin = client_origin(request)
            locked = LIMITER.seconds_locked(origin)
            if locked > 0:
                return locked_response(locked)
            if not authorized(request):
                LIMITER.record_failure(origin)
                return JSONResponse(status_code=401, content={"detail": UNAUTHENTICATED_DETAIL})
            if API_TOKEN is not None and is_protected_path(path):
                LIMITER.reset(origin)
        return await call_next(request)
