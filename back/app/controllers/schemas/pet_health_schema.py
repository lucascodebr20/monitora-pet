from pydantic import BaseModel, Field

from app.domain.enums import DoseKind, ExamType, FoodType


class FoodPeriodRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    brand: str = Field(default="", max_length=120)
    food_type: FoodType
    offered_amount: str = Field(default="", max_length=80)
    started_on: str
    ended_on: str | None = None
    notes: str = Field(default="", max_length=1000)
    replace_current: bool = False


class WeightRequest(BaseModel):
    measured_on: str
    weight_kg: float = Field(gt=0, le=150)
    notes: str = Field(default="", max_length=500)


class ExamRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    exam_type: ExamType
    performed_on: str | None = None
    laboratory: str = Field(default="", max_length=160)
    professional: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=2000)
    transcription: str = Field(default="", max_length=20000)


class TreatmentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body_region: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=2000)
    instructions: str = Field(default="", max_length=4000)
    started_on: str
    ended_on: str | None = None


class TreatmentEntryRequest(BaseModel):
    observed_at: str
    notes: str = Field(default="", max_length=2000)


class DoseRequest(BaseModel):
    kind: DoseKind
    name: str = Field(min_length=1, max_length=160)
    dose: str = Field(default="", max_length=120)
    given_on: str
    next_due_on: str | None = None
    notes: str = Field(default="", max_length=1000)
    treatment_id: str | None = None
