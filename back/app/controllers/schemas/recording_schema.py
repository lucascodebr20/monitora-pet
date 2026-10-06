from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class RecordingImportRequest(BaseModel):
    camera_id: str = Field(min_length=1)
    path: str = Field(min_length=1, max_length=4096)
    started_at: datetime | None = None

    @field_validator("started_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)


class RecordingTimeRequest(BaseModel):
    started_at: datetime

    @field_validator("started_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _aware(value) or value


class WatchedFolderRequest(BaseModel):
    camera_id: str = Field(min_length=1)
    path: str = Field(min_length=1, max_length=4096)
