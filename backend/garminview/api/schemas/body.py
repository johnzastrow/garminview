from pydantic import BaseModel
from datetime import date


class WeightResponse(BaseModel):
    date: date
    weight_kg: float | None

    model_config = {"from_attributes": True}


class BodyCompositionResponse(BaseModel):
    date: date
    weight_kg: float | None
    fat_pct: float | None
    muscle_mass_kg: float | None
    bmi: float | None
    bmr: int | None

    model_config = {"from_attributes": True}
