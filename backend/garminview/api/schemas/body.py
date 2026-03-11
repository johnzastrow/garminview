from pydantic import BaseModel
from datetime import date


class WeightResponse(BaseModel):
    date: date
    weight_kg: float | None = None

    model_config = {"from_attributes": True}


class BodyCompositionResponse(BaseModel):
    date: date
    weight_kg: float | None = None
    fat_pct: float | None = None
    muscle_mass_kg: float | None = None
    bmi: float | None = None
    bmr: int | None = None

    model_config = {"from_attributes": True}
