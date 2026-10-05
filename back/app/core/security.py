"""Controle de acesso local da API.

Dois mecanismos complementares:

* ``TrustedHostMiddleware`` (configurado em ``main.py`` com ``ALLOWED_HOSTS``) rejeita
  requisições cujo cabeçalho ``Host`` não seja local. Isso bloqueia DNS rebinding, em que
  uma página maliciosa aponta o próprio domínio para 127.0.0.1 e passa a conversar com a API.
* Token de sessão (``MONITORAPET_API_TOKEN``). Quando definido, toda rota ``/api/*`` exige o
  token via ``Authorization: Bearer`` ou via cookie HttpOnly criado por ``POST /api/session``.
  O cookie é necessário para que ``<img>`` e ``<video>`` consigam carregar vídeo e mídia.

Quem inicia o backend (Tauri, ``start.bat``) gera o token, exporta a variável de ambiente e o
entrega ao frontend pela query ``?token=`` ou por ``window.__MONITORAPET_TOKEN__``.
Sem a variável, a API fica aberta apenas para o host local, o que atende o fluxo de
desenvolvimento.
"""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Request

SESSION_COOKIE = "monitorapet_session"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "testserver")


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


def require_session(request: Request) -> None:
    if API_TOKEN is None:
        return
    if not is_valid_token(token_from_request(request)):
        raise HTTPException(status_code=401, detail="Sessão não autenticada. Abra o MonitoraPet pelo aplicativo.")
