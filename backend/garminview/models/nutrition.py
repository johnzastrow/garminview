from datetime import date
from sqlalchemy import Date, Float, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class MFPDailyNutrition(Base):
    __tablename__ = "mfp_daily_nutrition"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    calories_in: Mapped[int | None] = mapped_column(Integer)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    sugar_g: Mapped[float | None] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float)
    cholesterol_mg: Mapped[float | None] = mapped_column(Float)
    logged_meals: Mapped[int | None] = mapped_column(SmallInteger)
    source: Mapped[str] = mapped_column(String(32), default="mfp_export")


class MFPFoodDiaryEntry(Base):
    __tablename__ = "mfp_food_diary"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(32))
    food_name: Mapped[str] = mapped_column(String(512))
    calories: Mapped[int | None] = mapped_column(Integer)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    sugar_g: Mapped[float | None] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float)
    cholesterol_mg: Mapped[float | None] = mapped_column(Float)


class MFPMeasurement(Base):
    __tablename__ = "mfp_measurements"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))


class MFPExercise(Base):
    __tablename__ = "mfp_exercises"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    exercise_name: Mapped[str] = mapped_column(String(256))
    exercise_type: Mapped[str | None] = mapped_column(String(32))
    calories: Mapped[float | None] = mapped_column(Float)
    duration_min: Mapped[float | None] = mapped_column(Float)
    sets: Mapped[int | None] = mapped_column(Integer)
    reps_per_set: Mapped[int | None] = mapped_column(Integer)
    weight_lbs: Mapped[float | None] = mapped_column(Float)
    steps: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(512))
