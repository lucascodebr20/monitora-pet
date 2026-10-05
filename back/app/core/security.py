"""Controle de acesso local da API.

Dois mecanismos complementares, instalados por ``install_access_control``:

* ``TrustedHostMiddleware`` rejeita requisições cujo cabeçalho ``Host`` não seja local. Isso
  bloqueia DNS rebinding, em que uma página maliciosa aponta o próprio domínio para 127.0.0.1
  e passa a conversar com a API.
* Guarda de sessão por caminho (``MONITORAPET_API_TOKEN``). Quando definido, qualquer
  requisição a ``/api/*`` (inclusive docs, OpenAPI e rotas criadas no futuro) exige o token via
  ``Authorization: Bearer`` ou via cookie HttpOnly criado por ``POST /api/session``. O cookie é
  necessário para que ``<img>`` e ``<video>`` consigam carregar vídeo e mídia.

Quem inicia o backend (Tauri, ``start.bat``, lançador desktop) gera o token, exporta a variável
de ambiente e o entrega ao frontend pela query ``?token=`` ou por ``window.__MONITORAPET_TOKEN__``.
Sem a variável, a API fica aberta apenas para o host local, o que atende o desenvolvimento.
"""

from __future__ import annotations

import os
import secrets
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

SESSION_COOKIE = "monitorapet_session"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "testserver")
PUBLIC_API_PATHS = frozenset({"/api/session"})
UNAUTHENTICATED_DETAIL = "Sessão não autenticada. Abra o MonitoraPet pelo aplicativo."


def _configured_token() -> str | None:
    value = os.getenv("MONITORAPET_API_TOKEN", "").strip()
    return value or None


def _configured_hosts() -> list[str]:
    extra = [host.strip() for host in os.getenv("MONITORAPET_ALLOWED_HOSTS", "").split(",")]
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
    """True quando a requisição pode seguir: sem token configurado, caminho público,
    ou token válido por cabeçalho/cookie."""
    if API_TOKEN is None or not is_protected_path(request.url.path):
        return True
    return is_valid_token(token_from_request(request))


def install_access_control(app: FastAPI) -> None:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.middleware("http")
    async def session_guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not authorized(request):
            return JSONResponse(status_code=401, content={"detail": UNAUTHENTICATED_DETAIL})
        return await call_next(request)
