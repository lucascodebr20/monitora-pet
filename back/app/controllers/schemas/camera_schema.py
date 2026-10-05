from __future__ import annotations

import ipaddress

from pydantic import BaseModel, Field, field_validator, model_validator

from app.infra.camera.stream import split_url_credentials
from app.services.commands import CameraCredentialsCommand, CreateCameraCommand


def _move_url_credentials_to_fields(model: _WithRtspCredentials) -> None:
    """Se a URL veio como ``rtsp://usuario:senha@host/...``, a senha sai da URL e vai para
    os campos próprios, que nunca são persistidos. Campos já preenchidos têm prioridade."""
    if not model.rtsp_url or not model.rtsp_url.strip():
        model.rtsp_url = None
        return
    clean_url, username, password = split_url_credentials(model.rtsp_url)
    model.rtsp_url = clean_url
    if username and not model.username:
        model.username = username
    if password and not model.password:
        model.password = password


class _WithRtspCredentials(BaseModel):
    username: str = Field(default="", max_length=128)
    password: str = Field(default="", max_length=256)
    rtsp_url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def strip_credentials_from_url(self) -> _WithRtspCredentials:
        _move_url_credentials_to_fields(self)
        return self


class CameraCreateRequest(_WithRtspCredentials):
    name: str = Field(min_length=1, max_length=80)
    ip: str
    onvif_port: int = Field(default=8899, ge=1, le=65535)

    @field_validator("ip")
    @classmethod
    def valid_ip(cls, value: str) -> str:
        return str(ipaddress.ip_address(value.strip()))

    def to_command(self) -> CreateCameraCommand:
        return CreateCameraCommand(**self.model_dump())


class CameraCredentialsRequest(_WithRtspCredentials):
    def to_command(self) -> CameraCredentialsCommand:
        return CameraCredentialsCommand(**self.model_dump())
