from dataclasses import dataclass

from app.domain.enums import Activity, ReviewDecision, ZoneType


@dataclass(frozen=True)
class ReviewEventCommand:
    decision: ReviewDecision
    corrected_activity: Activity | None
    pet_id: str | None
    notes: str | None
    zone_type: ZoneType | None = None
