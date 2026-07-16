"""Fixture-driven tests for the MFP file adapters (nutrition / food diary /
measurements). These read plain CSVs the MFP web export produces."""

from datetime import date
from pathlib import Path

import pytest

from garminview.ingestion.file_adapters.mfp_nutrition import (
    MFPFoodDiaryAdapter,
    MFPMeasurementAdapter,
    MFPNutritionAdapter,
    _clean_num,
    _parse_date,
)

RANGE_START = date(2024, 1, 1)
RANGE_END = date(2024, 12, 31)


def _write(tmp_path: Path, name: str, content: str) -> None:
    (tmp_path / name).write_text(content, encoding="utf-8")


# ── helpers ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2024-01-15", date(2024, 1, 15)),
        ("Jan 15, 2024", date(2024, 1, 15)),
        ("01/15/2024", date(2024, 1, 15)),
        ("", None),
        ("not-a-date", None),
    ],
)
def test_parse_date_formats(raw, expected):
    assert _parse_date(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1,234", 1234.0),
        (" 42 ", 42.0),
        ("", None),
        ("—", None),
        (None, None),
        ("abc", None),
    ],
)
def test_clean_num(raw, expected):
    assert _clean_num(raw) == expected


# ── nutrition summary ────────────────────────────────────────────────

NUTRITION_CSV = (
    "Date,Calories,Carbohydrates,Fat,Protein,Sodium,Sugar,Fiber,Cholesterol\n"
    "2024-01-15,2100,250,70,120,2300,80,30,200\n"
    "2024-01-16,1900,,,,,,,\n"
    "2023-12-31,1000,100,30,50,1000,40,10,90\n"  # out of range
)


def test_nutrition_adapter_parses_and_filters(tmp_path):
    _write(tmp_path, "Nutrition Summary.csv", NUTRITION_CSV)
    rows = list(MFPNutritionAdapter(tmp_path).fetch(RANGE_START, RANGE_END))
    assert len(rows) == 2  # out-of-range row excluded

    r = {row["date"]: row for row in rows}
    jan15 = r[date(2024, 1, 15)]
    assert jan15["calories_in"] == 2100
    assert jan15["carbs_g"] == 250.0
    assert jan15["protein_g"] == 120.0
    assert jan15["sodium_mg"] == 2300.0
    assert jan15["source"] == "mfp_export"

    jan16 = r[date(2024, 1, 16)]
    assert jan16["calories_in"] == 1900
    assert jan16["carbs_g"] is None  # blank column -> None


def test_nutrition_adapter_alt_calorie_column(tmp_path):
    _write(
        tmp_path, "Nutrition Summary.csv", "Date,Calories Consumed\n2024-01-15,1800\n"
    )
    rows = list(MFPNutritionAdapter(tmp_path).fetch(RANGE_START, RANGE_END))
    assert rows[0]["calories_in"] == 1800


def test_nutrition_adapter_missing_file(tmp_path):
    # No file written -> adapter logs and yields nothing (no crash).
    assert list(MFPNutritionAdapter(tmp_path).fetch(RANGE_START, RANGE_END)) == []


# ── food diary ───────────────────────────────────────────────────────

FOOD_DIARY_CSV = (
    "Date,Meal,Food Name,Calories,Carbohydrates,Fat,Protein\n"
    "2024-01-15,Breakfast,Oatmeal,300,54,6,10\n"
    "2024-01-15,Lunch,Chicken Salad,450,20,25,40\n"
)


def test_food_diary_adapter(tmp_path):
    _write(tmp_path, "Food Diary.csv", FOOD_DIARY_CSV)
    rows = list(MFPFoodDiaryAdapter(tmp_path).fetch(RANGE_START, RANGE_END))
    assert len(rows) == 2
    assert rows[0]["meal"] == "Breakfast"
    assert rows[0]["food_name"] == "Oatmeal"
    assert rows[0]["calories"] == 300
    assert rows[1]["food_name"] == "Chicken Salad"
    assert rows[1]["protein_g"] == 40.0


# ── measurements ─────────────────────────────────────────────────────

MEASUREMENT_CSV = (
    "Date,Measurement,Value,Unit\n"
    "2024-01-15,Weight,180.0,lbs\n"
    "2024-01-15,Body Fat,18.5,%\n"
    "2024-01-16,,5.0,cm\n"  # no name -> skipped
    "2024-01-17,Waist,,in\n"  # no value -> skipped
)


def test_measurement_adapter_normalises_weight_to_kg(tmp_path):
    _write(tmp_path, "Measurements.csv", MEASUREMENT_CSV)
    rows = list(MFPMeasurementAdapter(tmp_path).fetch(RANGE_START, RANGE_END))
    # Only the two valid rows survive
    assert len(rows) == 2

    weight = next(r for r in rows if r["name"] == "Weight")
    assert weight["unit"] == "kg"
    assert weight["value"] == pytest.approx(180.0 * 0.453592)

    bf = next(r for r in rows if r["name"] == "Body Fat")
    assert bf["value"] == 18.5
    assert bf["unit"] == "%"
