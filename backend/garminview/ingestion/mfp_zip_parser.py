import csv
import io
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class ParseError:
    file: str
    row: int
    message: str


class MFPNoFilesError(ValueError):
    """Raised when a valid ZIP contains none of the expected MFP CSV files."""


@dataclass
class ParseResult:
    nutrition_daily: list[dict[str, Any]] = field(default_factory=list)
    food_diary: list[dict[str, Any]] = field(default_factory=list)
    measurements: list[dict[str, Any]] = field(default_factory=list)
    exercises: list[dict[str, Any]] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    min_date: date | None = None
    max_date: date | None = None


def _parse_date(s: str) -> date | None:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _num(s: str | None) -> float | None:
    if not s:
        return None
    try:
        v = float(s.strip().replace(",", ""))
        return v if v == v else None  # NaN guard
    except (ValueError, AttributeError):
        return None


def _int_or_none(s: str | None) -> int | None:
    v = _num(s)
    return round(v) if v is not None else None


def _find_file(zf: zipfile.ZipFile, prefix: str) -> str | None:
    """Return the first ZIP member whose name starts with prefix (case-insensitive)."""
    for name in zf.namelist():
        if name.lower().startswith(prefix.lower()):
            return name
    return None


def _update_date_range(result: ParseResult, d: date) -> None:
    if result.min_date is None or d < result.min_date:
        result.min_date = d
    if result.max_date is None or d > result.max_date:
        result.max_date = d


def _parse_nutrition(zf: zipfile.ZipFile, member: str, result: ParseResult) -> None:
    """Parse Nutrition-Summary CSV → food_diary rows + aggregate into nutrition_daily."""
    daily: dict[date, dict] = {}

    with zf.open(member) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        for row_num, row in enumerate(reader, start=2):
            d = _parse_date(row.get("Date", ""))
            if d is None:
                result.errors.append(ParseError(member, row_num, f"Invalid date {row.get('Date', '')!r}"))
                continue

            _update_date_range(result, d)
            meal = (row.get("Meal") or "").strip()

            # Per-meal food diary row
            result.food_diary.append({
                "date": d,
                "meal": meal[:32],
                "food_name": meal[:512],
                "calories": _int_or_none(row.get("Calories")),
                "carbs_g": _num(row.get("Carbohydrates (g)")),
                "fat_g": _num(row.get("Fat (g)")),
                "protein_g": _num(row.get("Protein (g)")),
                "sodium_mg": _num(row.get("Sodium (mg)")),
                "sugar_g": _num(row.get("Sugar")),
                "fiber_g": _num(row.get("Fiber")),
                "cholesterol_mg": _num(row.get("Cholesterol")),
            })

            # Daily aggregation
            if d not in daily:
                daily[d] = {
                    "date": d, "calories_in": 0, "carbs_g": 0.0, "fat_g": 0.0,
                    "protein_g": 0.0, "sodium_mg": 0.0, "sugar_g": 0.0,
                    "fiber_g": 0.0, "cholesterol_mg": 0.0, "logged_meals": 0,
                    "source": "mfp_upload",
                }
            agg = daily[d]
            agg["calories_in"] += _int_or_none(row.get("Calories")) or 0
            for col, key in [
                ("Carbohydrates (g)", "carbs_g"), ("Fat (g)", "fat_g"),
                ("Protein (g)", "protein_g"), ("Sodium (mg)", "sodium_mg"),
                ("Sugar", "sugar_g"), ("Fiber", "fiber_g"), ("Cholesterol", "cholesterol_mg"),
            ]:
                agg[key] = round((agg[key] or 0.0) + (_num(row.get(col)) or 0.0), 4)
            agg["logged_meals"] += 1

    result.nutrition_daily.extend(daily.values())


def _parse_measurements(zf: zipfile.ZipFile, member: str, result: ParseResult) -> None:
    """Parse Measurement-Summary CSV → mfp_measurements rows."""
    with zf.open(member) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        for row_num, row in enumerate(reader, start=2):
            d = _parse_date(row.get("Date", ""))
            if d is None:
                result.errors.append(ParseError(member, row_num, f"Invalid date {row.get('Date', '')!r}"))
                continue
            _update_date_range(result, d)

            bf = _num(row.get("Body Fat %"))
            if bf is not None:
                result.measurements.append({"date": d, "name": "body_fat_pct", "value": bf, "unit": "%"})

            wt = _num(row.get("Weight"))
            if wt is not None:
                result.measurements.append({"date": d, "name": "weight", "value": wt, "unit": "lbs"})


def _parse_exercises(zf: zipfile.ZipFile, member: str, result: ParseResult) -> None:
    """Parse Exercise-Summary CSV → mfp_exercises rows."""
    with zf.open(member) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        for row_num, row in enumerate(reader, start=2):
            d = _parse_date(row.get("Date", ""))
            if d is None:
                result.errors.append(ParseError(member, row_num, f"Invalid date {row.get('Date', '')!r}"))
                continue
            _update_date_range(result, d)

            name = (row.get("Exercise") or "").strip()
            if not name:
                result.errors.append(ParseError(member, row_num, "Missing exercise name"))
                continue

            result.exercises.append({
                "date": d,
                "exercise_name": name[:256],
                "exercise_type": (row.get("Type") or "").strip()[:32] or None,
                "calories": _num(row.get("Exercise Calories")),
                "duration_min": _num(row.get("Exercise Minutes")),
                "sets": _int_or_none(row.get("Sets")),
                "reps_per_set": _int_or_none(row.get("Reps Per Set")),
                "weight_lbs": _num(row.get("Pounds")),
                "steps": _int_or_none(row.get("Steps")),
                "note": (row.get("Note") or "").strip()[:512] or None,
            })


def parse_mfp_zip(data: bytes) -> ParseResult:
    """Parse a MyFitnessPal export ZIP from raw bytes. Returns ParseResult."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ValueError(f"not a valid ZIP file: {e}") from e

    with zf:
        nutrition_file = _find_file(zf, "Nutrition-Summary")
        measurement_file = _find_file(zf, "Measurement-Summary")
        exercise_file = _find_file(zf, "Exercise-Summary")

        if not any([nutrition_file, measurement_file, exercise_file]):
            raise MFPNoFilesError("No expected MFP files found in ZIP (expected Nutrition-Summary, Measurement-Summary, or Exercise-Summary)")

        result = ParseResult()

        if nutrition_file:
            _parse_nutrition(zf, nutrition_file, result)
        if measurement_file:
            _parse_measurements(zf, measurement_file, result)
        if exercise_file:
            _parse_exercises(zf, exercise_file, result)

        return result
