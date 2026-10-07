from pydantic import BaseModel, Field

from app.domain.enums import Activity, ReviewDecision, ZoneType
from app.services.event import ReviewEventCommand


class ReviewCreateRequest(BaseModel):
    decision: ReviewDecision
    corrected_activity: Activity | None = None
    pet_id: str | None = None
    zone_type: ZoneType | None = None
    notes: str | None = Field(default=None, max_length=500)
    pet_ids: list[str] = Field(default_factory=list, max_length=12)

    def to_command(self) -> ReviewEventCommand:
        values = self.model_dump()
        return ReviewEventCommand(**{**values, "pet_ids": tuple(values["pet_ids"])})


class HighlightUpdateRequest(BaseModel):
    highlighted: bool
