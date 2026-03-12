from pydantic import BaseModel
from datetime import date


class MFPNutritionResponse(BaseModel):
    date: date
    calories_in: int | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    protein_g: float | None = None
    sodium_mg: float | None = None
    sugar_g: float | None = None
    fiber_g: float | None = None
    cholesterol_mg: float | None = None
    logged_meals: int | None = None

    model_config = {"from_attributes": True}


class EnergyBalanceResponse(BaseModel):
    date: date
    calories_in: int | None = None
    calories_out: int | None = None      # from Garmin daily_summary.calories_total
    energy_balance: int | None = None    # calories_in - calories_out
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None

    model_config = {"from_attributes": True}
