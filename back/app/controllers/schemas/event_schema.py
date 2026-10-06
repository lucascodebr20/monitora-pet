from pydantic import BaseModel, Field

from app.domain.enums import Activity, ReviewDecision, ZoneType
from app.services.event import ReviewEventCommand


class ReviewCreateRequest(BaseModel):
    decision: ReviewDecision
    corrected_activity: Activity | None = None
    pet_id: str | None = None
    zone_type: ZoneType | None = None
    notes: str | None = Field(default=None, max_length=500)

    def to_command(self) -> ReviewEventCommand:
        return ReviewEventCommand(**self.model_dump())
