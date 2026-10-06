from pydantic import BaseModel, Field

from app.domain.enums import ZoneType
from app.services.zone import CreateZoneCommand


class PointRequest(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class ZoneCreateRequest(BaseModel):
    camera_id: str
    name: str = Field(min_length=1, max_length=80)
    type: ZoneType
    polygon: list[PointRequest] = Field(min_length=3)
    minimum_presence_seconds: float = Field(default=3, ge=0.5, le=300)
    absence_tolerance_seconds: float = Field(default=1, ge=0, le=30)
    cooldown_seconds: float = Field(default=10, ge=0, le=3600)

    def to_command(self) -> CreateZoneCommand:
        return CreateZoneCommand(
            camera_id=self.camera_id,
            name=self.name,
            type=self.type,
            polygon=tuple((point.x, point.y) for point in self.polygon),
            minimum_presence_seconds=self.minimum_presence_seconds,
            absence_tolerance_seconds=self.absence_tolerance_seconds,
            cooldown_seconds=self.cooldown_seconds,
        )
