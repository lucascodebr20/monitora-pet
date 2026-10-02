from dataclasses import dataclass

from app.domain.enums import Activity, ReviewDecision, ZoneType


@dataclass(frozen=True)
class CreateCameraCommand:
    name: str
    ip: str
    username: str
    password: str
    rtsp_url: str | None
    onvif_port: int


@dataclass(frozen=True)
class CameraCredentialsCommand:
    username: str
    password: str
    rtsp_url: str | None


@dataclass(frozen=True)
class CreateZoneCommand:
    camera_id: str
    name: str
    type: ZoneType
    polygon: tuple[tuple[float, float], ...]
    minimum_presence_seconds: float
    absence_tolerance_seconds: float
    cooldown_seconds: float


@dataclass(frozen=True)
class ReviewEventCommand:
    decision: ReviewDecision
    corrected_activity: Activity | None
    cat_name: str | None
    notes: str | None
