from __future__ import annotations

import ipaddress

from pydantic import BaseModel, Field, field_validator

from app.services.commands import CameraCredentialsCommand, CreateCameraCommand


class CameraCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    ip: str
    username: str = Field(default="", max_length=128)
    password: str = Field(default="", max_length=256)
    rtsp_url: str | None = Field(default=None, max_length=2048)
    onvif_port: int = Field(default=8899, ge=1, le=65535)

    @field_validator("ip")
    @classmethod
    def valid_ip(cls, value: str) -> str:
        return str(ipaddress.ip_address(value.strip()))

    def to_command(self) -> CreateCameraCommand:
        return CreateCameraCommand(**self.model_dump())


class CameraCredentialsRequest(BaseModel):
    username: str = Field(default="", max_length=128)
    password: str = Field(default="", max_length=256)
    rtsp_url: str | None = Field(default=None, max_length=2048)

    def to_command(self) -> CameraCredentialsCommand:
        return CameraCredentialsCommand(**self.model_dump())
