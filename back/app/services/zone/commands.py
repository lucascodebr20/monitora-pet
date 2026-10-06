from dataclasses import dataclass

from app.domain.enums import ZoneType


@dataclass(frozen=True)
class CreateZoneCommand:
    camera_id: str
    name: str
    type: ZoneType
    polygon: tuple[tuple[float, float], ...]
    minimum_presence_seconds: float
    absence_tolerance_seconds: float
    cooldown_seconds: float
