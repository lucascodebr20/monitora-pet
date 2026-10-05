from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.security import SESSION_COOKIE, auth_required, is_valid_token, token_from_request


router = APIRouter(prefix="/api/session", tags=["session"])


class SessionRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


def _status(authenticated: bool) -> dict[str, Any]:
    return {"required": auth_required(), "authenticated": authenticated}


@router.get("")
def session_status(request: Request) -> dict[str, Any]:
    if not auth_required():
        return _status(True)
    return _status(is_valid_token(token_from_request(request)))


@router.post("")
def open_session(payload: SessionRequest, response: Response) -> dict[str, Any]:
    if not auth_required():
        return _status(True)
    if not is_valid_token(payload.token):
        raise HTTPException(status_code=401, detail="Token de sessão inválido.")
    response.set_cookie(SESSION_COOKIE, payload.token, httponly=True, samesite="strict", path="/")
    return _status(True)


@router.delete("", status_code=204)
def close_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
