# MFP ZIP Upload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users upload a MyFitnessPal export ZIP via the Admin UI to populate four DB tables with upsert deduplication and per-row error reporting.

**Architecture:** A new `POST /admin/upload/mfp` endpoint accepts a multipart ZIP, extracts and parses three CSVs in-memory, upserts into `mfp_daily_nutrition`, `mfp_measurements`, `mfp_food_diary`, and the new `mfp_exercises` table, and returns counts + per-row errors. The Admin page gains an "Uploads" tab with a file picker and results display.

**Tech Stack:** FastAPI `UploadFile`, Python `zipfile` + `csv` (stdlib only), SQLAlchemy 2.x dialect-aware upserts (same pattern as orchestrator), Vue 3 Composition API.

---

## Task 1: Add `MFPExercise` model and extend `MFPFoodDiaryEntry`

**Files:**
- Modify: `backend/garminview/models/nutrition.py`
- Modify: `backend/garminview/models/__init__.py`
- Test: `backend/tests/test_models.py`

### Step 1: Write failing test

Add to `backend/tests/test_models.py`:

```python
def test_mfp_exercise_model(session):
    from garminview.models.nutrition import MFPExercise
    from datetime import date
    ex = MFPExercise(
        date=date(2024, 1, 15),
        exercise_name="Running",
        exercise_type="Cardio",
        calories=350.0,
        duration_min=30.0,
    )
    session.add(ex)
    session.commit()
    row = session.get(MFPExercise, ex.id)
    assert row.exercise_name == "Running"
    assert row.duration_min == 30.0


def test_mfp_food_diary_extended_columns(session):
    from garminview.models.nutrition import MFPFoodDiaryEntry
    from datetime import date
    entry = MFPFoodDiaryEntry(
        date=date(2024, 1, 15),
        meal="Breakfast",
        food_name="Breakfast before 8a",
        calories=450,
        carbs_g=55.0,
        fat_g=12.0,
        protein_g=22.0,
        sodium_mg=800.0,
        sugar_g=18.0,
        fiber_g=6.0,
        cholesterol_mg=95.0,
    )
    session.add(entry)
    session.commit()
    row = session.query(MFPFoodDiaryEntry).filter_by(id=entry.id).one()
    assert row.sodium_mg == 800.0
    assert row.fiber_g == 6.0
```

Run: `uv run pytest backend/tests/test_models.py::test_mfp_exercise_model backend/tests/test_models.py::test_mfp_food_diary_extended_columns -v`
Expected: FAIL — `MFPExercise` does not exist; `MFPFoodDiaryEntry` has no `sodium_mg`.

### Step 2: Add `MFPExercise` and extend `MFPFoodDiaryEntry`

In `backend/garminview/models/nutrition.py`, add four columns to `MFPFoodDiaryEntry` and append the new class:

```python
# In MFPFoodDiaryEntry, add after protein_g:
sodium_mg: Mapped[float | None] = mapped_column(Float)
sugar_g: Mapped[float | None] = mapped_column(Float)
fiber_g: Mapped[float | None] = mapped_column(Float)
cholesterol_mg: Mapped[float | None] = mapped_column(Float)


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
```

### Step 3: Export `MFPExercise` from `__init__.py`

In `backend/garminview/models/__init__.py`:
- Change the nutrition import line to: `from garminview.models.nutrition import MFPDailyNutrition, MFPFoodDiaryEntry, MFPMeasurement, MFPExercise`
- Add `"MFPExercise"` to `__all__`

### Step 4: Run tests

Run: `uv run pytest backend/tests/test_models.py::test_mfp_exercise_model backend/tests/test_models.py::test_mfp_food_diary_extended_columns -v`
Expected: PASS

### Step 5: Run full test suite

Run: `uv run pytest backend/ -v`
Expected: All passing (new columns are additive, existing tests unaffected).

### Step 6: Commit

```bash
git add backend/garminview/models/nutrition.py backend/garminview/models/__init__.py backend/tests/test_models.py
git commit -m "feat: add MFPExercise model; extend MFPFoodDiaryEntry with macro columns"
```

---

## Task 2: Write MFP ZIP parser

**Files:**
- Create: `backend/garminview/ingestion/mfp_zip_parser.py`
- Create: `backend/tests/ingestion/test_mfp_zip_parser.py`

The parser is a standalone module (not a `BaseAdapter` subclass — it reads a zip, not a directory). It returns a `ParseResult` dataclass with lists of dicts ready for DB insertion plus a list of `ParseError` entries.

### Step 1: Write failing tests

Create `backend/tests/ingestion/test_mfp_zip_parser.py`:

```python
import io
import zipfile
import csv
from datetime import date
from garminview.ingestion.mfp_zip_parser import parse_mfp_zip, ParseResult, ParseError


def _make_zip(files: dict[str, str]) -> bytes:
    """Build an in-memory zip with the given filename → CSV content mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


NUTRITION_CSV = """Date,Meal,Calories,Fat (g),Saturated Fat,Polyunsaturated Fat,Monounsaturated Fat,Trans Fat,Cholesterol,Sodium (mg),Potassium,Carbohydrates (g),Fiber,Sugar,Protein (g),Vitamin A,Vitamin C,Calcium,Iron,Note
2024-01-15,Breakfast,500.0,15.0,5.0,1.0,1.0,0.0,50.0,600.0,0.0,70.0,3.0,20.0,25.0,0.0,0.0,0.0,2.0,
2024-01-15,Lunch,700.0,25.0,8.0,2.0,2.0,0.0,80.0,900.0,0.0,85.0,5.0,10.0,40.0,0.0,0.0,0.0,4.0,
2024-01-16,Breakfast,450.0,12.0,4.0,1.0,1.0,0.0,40.0,500.0,0.0,60.0,2.0,15.0,20.0,0.0,0.0,0.0,1.0,
"""

MEASUREMENT_CSV = """Date,Body Fat %,Weight
2024-01-15,18.5,175.0
2024-01-16,,176.0
"""

EXERCISE_CSV = """Date,Exercise,Type,Exercise Calories,Exercise Minutes,Sets,Reps Per Set,Pounds,Steps,Note
2024-01-15,Running,Cardio,350.0,30.0,,,,5000,
2024-01-15,Bench Press,Strength,120.0,20.0,3,10,135.0,,
2024-01-16,Bad Date Row,Cardio,100.0,20.0,,,,1000,
"""


def test_parse_nutrition_aggregates_by_date():
    data = _make_zip({
        "Nutrition-Summary-2024.csv": NUTRITION_CSV,
        "Measurement-Summary-2024.csv": MEASUREMENT_CSV,
        "Exercise-Summary-2024.csv": EXERCISE_CSV,
    })
    result = parse_mfp_zip(data)
    assert isinstance(result, ParseResult)
    daily = {r["date"]: r for r in result.nutrition_daily}
    assert date(2024, 1, 15) in daily
    jan15 = daily[date(2024, 1, 15)]
    assert jan15["calories_in"] == 1200   # 500 + 700
    assert jan15["fat_g"] == 40.0          # 15 + 25
    assert jan15["protein_g"] == 65.0      # 25 + 40
    assert jan15["logged_meals"] == 2


def test_parse_nutrition_food_diary_rows():
    data = _make_zip({
        "Nutrition-Summary-2024.csv": NUTRITION_CSV,
        "Measurement-Summary-2024.csv": MEASUREMENT_CSV,
        "Exercise-Summary-2024.csv": EXERCISE_CSV,
    })
    result = parse_mfp_zip(data)
    assert len(result.food_diary) == 3   # 2 meals on Jan 15 + 1 on Jan 16
    jan15_meals = [r for r in result.food_diary if r["date"] == date(2024, 1, 15)]
    assert len(jan15_meals) == 2
    breakfast = next(r for r in jan15_meals if r["food_name"] == "Breakfast")
    assert breakfast["sodium_mg"] == 600.0
    assert breakfast["fiber_g"] == 3.0


def test_parse_measurements():
    data = _make_zip({
        "Nutrition-Summary-2024.csv": NUTRITION_CSV,
        "Measurement-Summary-2024.csv": MEASUREMENT_CSV,
        "Exercise-Summary-2024.csv": EXERCISE_CSV,
    })
    result = parse_mfp_zip(data)
    # Body Fat % on Jan 15 + Weight on Jan 15 + Weight on Jan 16 = 3 rows
    # Jan 16 has no Body Fat % — skipped
    assert len(result.measurements) == 3
    bf = next(r for r in result.measurements if r["name"] == "body_fat_pct")
    assert bf["value"] == 18.5
    assert bf["unit"] == "%"
    weight_rows = [r for r in result.measurements if r["name"] == "weight"]
    assert len(weight_rows) == 2


def test_parse_exercises():
    data = _make_zip({
        "Nutrition-Summary-2024.csv": NUTRITION_CSV,
        "Measurement-Summary-2024.csv": MEASUREMENT_CSV,
        "Exercise-Summary-2024.csv": EXERCISE_CSV,
    })
    result = parse_mfp_zip(data)
    assert len(result.exercises) == 2   # "Bad Date Row" has no bad date actually
    # all 3 rows should parse — the name "Bad Date Row" is just the exercise name
    assert len(result.exercises) == 3
    bench = next(r for r in result.exercises if r["exercise_name"] == "Bench Press")
    assert bench["sets"] == 3
    assert bench["weight_lbs"] == 135.0
    assert bench["exercise_type"] == "Strength"


def test_date_range_detection():
    data = _make_zip({
        "Nutrition-Summary-2024.csv": NUTRITION_CSV,
        "Measurement-Summary-2024.csv": MEASUREMENT_CSV,
        "Exercise-Summary-2024.csv": EXERCISE_CSV,
    })
    result = parse_mfp_zip(data)
    assert result.min_date == date(2024, 1, 15)
    assert result.max_date == date(2024, 1, 16)


def test_invalid_zip_raises():
    with pytest.raises(ValueError, match="not a valid ZIP"):
        parse_mfp_zip(b"not a zip file")


def test_empty_zip_raises():
    data = _make_zip({"unrelated.txt": "hello"})
    with pytest.raises(ValueError, match="No expected MFP files"):
        parse_mfp_zip(data)


def test_bad_row_collected_as_error():
    bad_nutrition = """Date,Meal,Calories,Fat (g),Saturated Fat,Polyunsaturated Fat,Monounsaturated Fat,Trans Fat,Cholesterol,Sodium (mg),Potassium,Carbohydrates (g),Fiber,Sugar,Protein (g),Vitamin A,Vitamin C,Calcium,Iron,Note
NOT-A-DATE,Breakfast,500.0,15.0,5.0,1.0,1.0,0.0,50.0,600.0,0.0,70.0,3.0,20.0,25.0,0.0,0.0,0.0,2.0,
"""
    data = _make_zip({
        "Nutrition-Summary-2024.csv": bad_nutrition,
        "Measurement-Summary-2024.csv": MEASUREMENT_CSV,
        "Exercise-Summary-2024.csv": EXERCISE_CSV,
    })
    result = parse_mfp_zip(data)
    assert len(result.nutrition_daily) == 0
    assert any("NOT-A-DATE" in e.message for e in result.errors)
```

Fix the test — `"Bad Date Row"` is a valid exercise name, not a bad date. The test has an inconsistency. The correct assertion is `len(result.exercises) == 3`. Remove the first `assert len(result.exercises) == 2` line from `test_parse_exercises`.

Run: `uv run pytest backend/tests/ingestion/test_mfp_zip_parser.py -v`
Expected: FAIL — module does not exist.

### Step 2: Implement the parser

Create `backend/garminview/ingestion/mfp_zip_parser.py`:

```python
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
    return int(v) if v is not None else None


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

    nutrition_file = _find_file(zf, "Nutrition-Summary")
    measurement_file = _find_file(zf, "Measurement-Summary")
    exercise_file = _find_file(zf, "Exercise-Summary")

    if not any([nutrition_file, measurement_file, exercise_file]):
        raise ValueError("No expected MFP files found in ZIP (expected Nutrition-Summary, Measurement-Summary, or Exercise-Summary)")

    result = ParseResult()

    if nutrition_file:
        _parse_nutrition(zf, nutrition_file, result)
    if measurement_file:
        _parse_measurements(zf, measurement_file, result)
    if exercise_file:
        _parse_exercises(zf, exercise_file, result)

    return result
```

### Step 3: Run tests

Run: `uv run pytest backend/tests/ingestion/test_mfp_zip_parser.py -v`
Expected: All PASS.

### Step 4: Smoke test against the real export

```bash
uv run python -c "
import pathlib
from garminview.ingestion.mfp_zip_parser import parse_mfp_zip
data = pathlib.Path('docs/myfitnesspal/File-Export-2012-03-24-to-2026-03-11.zip').read_bytes()
r = parse_mfp_zip(data)
print(f'nutrition_daily={len(r.nutrition_daily)}, food_diary={len(r.food_diary)}, measurements={len(r.measurements)}, exercises={len(r.exercises)}, errors={len(r.errors)}')
print(f'date_range={r.min_date} to {r.max_date}')
if r.errors: print('First 3 errors:', r.errors[:3])
"
```
Expected output: ~`nutrition_daily=609, food_diary=609, measurements=715, exercises=3194, errors=0` (or very few errors).

### Step 5: Commit

```bash
git add backend/garminview/ingestion/mfp_zip_parser.py backend/tests/ingestion/test_mfp_zip_parser.py
git commit -m "feat: MFP ZIP in-memory parser with per-row error collection"
```

---

## Task 3: Add `POST /admin/upload/mfp` endpoint

**Files:**
- Modify: `backend/garminview/api/routes/admin.py`
- Test: `backend/tests/api/test_admin_upload.py`

### Step 1: Write failing test

Create `backend/tests/api/test_admin_upload.py`:

```python
import io
import zipfile
import pytest
from fastapi.testclient import TestClient
from garminview.api.main import create_app


@pytest.fixture
def client(session, monkeypatch):
    monkeypatch.setattr("garminview.api.deps.get_db", lambda: session)
    app = create_app()
    with TestClient(app) as c:
        yield c


def _make_mfp_zip() -> bytes:
    nutrition = (
        "Date,Meal,Calories,Fat (g),Saturated Fat,Polyunsaturated Fat,Monounsaturated Fat,"
        "Trans Fat,Cholesterol,Sodium (mg),Potassium,Carbohydrates (g),Fiber,Sugar,Protein (g),"
        "Vitamin A,Vitamin C,Calcium,Iron,Note\n"
        "2024-01-15,Breakfast,500.0,15.0,5.0,1.0,1.0,0.0,50.0,600.0,0.0,70.0,3.0,20.0,25.0,0.0,0.0,0.0,2.0,\n"
    )
    measurements = "Date,Body Fat %,Weight\n2024-01-15,18.5,175.0\n"
    exercises = (
        "Date,Exercise,Type,Exercise Calories,Exercise Minutes,Sets,Reps Per Set,Pounds,Steps,Note\n"
        "2024-01-15,Running,Cardio,350.0,30.0,,,,5000,\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Nutrition-Summary-2024.csv", nutrition)
        zf.writestr("Measurement-Summary-2024.csv", measurements)
        zf.writestr("Exercise-Summary-2024.csv", exercises)
    return buf.getvalue()


def test_upload_mfp_returns_counts(client):
    zdata = _make_mfp_zip()
    resp = client.post(
        "/admin/upload/mfp",
        files={"file": ("export.zip", zdata, "application/zip")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nutrition_days"] == 1
    assert body["food_diary_rows"] == 1
    assert body["measurements"] == 2   # body fat + weight
    assert body["exercises"] == 1
    assert body["errors"] == []


def test_upload_mfp_idempotent(client):
    """Uploading the same ZIP twice should not duplicate rows."""
    zdata = _make_mfp_zip()
    client.post("/admin/upload/mfp", files={"file": ("export.zip", zdata, "application/zip")})
    resp = client.post("/admin/upload/mfp", files={"file": ("export.zip", zdata, "application/zip")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["nutrition_days"] == 1
    assert body["exercises"] == 1


def test_upload_mfp_invalid_zip(client):
    resp = client.post(
        "/admin/upload/mfp",
        files={"file": ("bad.zip", b"not a zip", "application/zip")},
    )
    assert resp.status_code == 422


def test_upload_mfp_wrong_file_type(client):
    resp = client.post(
        "/admin/upload/mfp",
        files={"file": ("data.csv", b"col1,col2\n1,2\n", "text/csv")},
    )
    assert resp.status_code == 422
```

Run: `uv run pytest backend/tests/api/test_admin_upload.py -v`
Expected: FAIL — endpoint does not exist.

### Step 2: Add lazy migration for new `mfp_food_diary` columns + schema version record

In `backend/garminview/api/routes/admin.py`, add a new migration helper immediately after `_migrate_anomaly_columns`. It both alters the table and inserts a `schema_version` row to record what changed:

```python
def _migrate_mfp_food_diary_columns(session: Session) -> None:
    """Add extended macro columns to mfp_food_diary if not present (lazy migration).
    Also creates mfp_exercises table if missing, and records changes in schema_version.
    """
    from datetime import datetime, timezone
    from garminview.models.sync import SchemaVersion
    from garminview.core.database import Base
    try:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(session.bind)
        existing_cols = {c["name"] for c in inspector.get_columns("mfp_food_diary")}
        added = []
        with session.connection() as conn:
            for col, definition in [
                ("sodium_mg", "FLOAT"),
                ("sugar_g", "FLOAT"),
                ("fiber_g", "FLOAT"),
                ("cholesterol_mg", "FLOAT"),
            ]:
                if col not in existing_cols:
                    conn.execute(text(f"ALTER TABLE mfp_food_diary ADD COLUMN {col} {definition}"))
                    added.append(col)

            # Create mfp_exercises if it doesn't exist yet
            existing_tables = set(inspector.get_table_names())
            if "mfp_exercises" not in existing_tables:
                from garminview.models.nutrition import MFPExercise
                MFPExercise.__table__.create(bind=session.bind)
                added.append("table:mfp_exercises")

        if added:
            session.add(SchemaVersion(
                version="mfp_upload_v1",
                description=f"MFP upload migration: added {', '.join(added)}",
                applied_at=datetime.now(timezone.utc),
                applied_by="mfp_upload",
            ))
        session.commit()
    except Exception:
        session.rollback()
```

### Step 3: Add the upload endpoint

Add to `backend/garminview/api/routes/admin.py` (after the existing imports, add `UploadFile, File` to the fastapi import and add the endpoint):

```python
# Add to fastapi import line:
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File

# Add this endpoint:
@router.post("/upload/mfp")
async def upload_mfp(
    session: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Upload a MyFitnessPal export ZIP and upsert all data into the DB."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="File must be a .zip")

    data = await file.read()

    from garminview.ingestion.mfp_zip_parser import parse_mfp_zip, ParseResult
    try:
        result: ParseResult = parse_mfp_zip(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    _migrate_mfp_food_diary_columns(session)

    dialect = session.bind.dialect.name
    start, end = result.min_date, result.max_date

    # --- mfp_food_diary: delete range then reinsert ---
    if result.food_diary and start and end:
        from sqlalchemy import text as _text
        session.execute(_text("DELETE FROM mfp_food_diary WHERE date >= :s AND date <= :e"),
                        {"s": start, "e": end})
        session.commit()
        from garminview.models.nutrition import MFPFoodDiaryEntry
        _bulk_insert(session, MFPFoodDiaryEntry, result.food_diary, dialect)

    # --- mfp_exercises: delete range then reinsert ---
    if result.exercises and start and end:
        from sqlalchemy import text as _text
        session.execute(_text("DELETE FROM mfp_exercises WHERE date >= :s AND date <= :e"),
                        {"s": start, "e": end})
        session.commit()
        from garminview.models.nutrition import MFPExercise
        _bulk_insert(session, MFPExercise, result.exercises, dialect)

    # --- mfp_daily_nutrition: upsert by date ---
    if result.nutrition_daily:
        from garminview.models.nutrition import MFPDailyNutrition
        _upsert(session, MFPDailyNutrition, result.nutrition_daily, ["date"], dialect)

    # --- mfp_measurements: upsert by (date, name) ---
    if result.measurements:
        from garminview.models.nutrition import MFPMeasurement
        _upsert(session, MFPMeasurement, result.measurements, ["date", "name"], dialect)

    session.commit()

    return {
        "nutrition_days": len(result.nutrition_daily),
        "food_diary_rows": len(result.food_diary),
        "measurements": len(result.measurements),
        "exercises": len(result.exercises),
        "errors": [{"file": e.file, "row": e.row, "message": e.message} for e in result.errors],
    }


def _bulk_insert(session, model, rows, dialect):
    """Insert rows in 500-row batches (for autoincrement-PK tables)."""
    _BATCH = 500
    for i in range(0, len(rows), _BATCH):
        batch = rows[i:i + _BATCH]
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as _ins
        else:
            from sqlalchemy.dialects.mysql import insert as _ins
        session.execute(_ins(model).values(batch))
    session.commit()


def _upsert(session, model, rows, pk_cols, dialect):
    """Upsert rows in 500-row batches (for natural-PK tables)."""
    _BATCH = 500
    for i in range(0, len(rows), _BATCH):
        batch = rows[i:i + _BATCH]
        non_pk = [c for c in batch[0] if c not in pk_cols]
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as _ins
            stmt = _ins(model).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=pk_cols,
                set_={c: getattr(stmt.excluded, c) for c in non_pk},
            )
        else:
            from sqlalchemy.dialects.mysql import insert as _ins
            stmt = _ins(model).values(batch)
            stmt = stmt.on_duplicate_key_update(**{c: stmt.inserted[c] for c in non_pk})
        session.execute(stmt)
    session.commit()
```

### Step 4: Run tests

Run: `uv run pytest backend/tests/api/test_admin_upload.py -v`
Expected: All PASS.

### Step 5: Run full suite

Run: `uv run pytest backend/ -v`
Expected: All green.

### Step 6: Commit

```bash
git add backend/garminview/api/routes/admin.py backend/tests/api/test_admin_upload.py
git commit -m "feat: POST /admin/upload/mfp endpoint with upsert dedup and error reporting"
```

---

## Task 4: Add "Uploads" tab to Admin.vue

**Files:**
- Modify: `frontend/src/views/Admin.vue`

No automated frontend tests — verify manually after implementation.

### Step 1: Add "Uploads" to the tabs array

In `frontend/src/views/Admin.vue`, find the `tabs` array (line ~77) and add:

```typescript
const tabs = [
  { id: "sync", label: "Sync" },
  { id: "schedules", label: "Schedules" },
  { id: "config", label: "Config" },
  { id: "logs", label: "Sync Logs" },
  { id: "uploads", label: "Uploads" },   // ADD THIS
]
```

### Step 2: Add reactive state for the Uploads tab

In the `<script setup>` block, after the existing reactive declarations:

```typescript
// --- Uploads ---
const uploadFile = ref<File | null>(null)
const uploading = ref(false)
const uploadResult = ref<{
  nutrition_days: number
  food_diary_rows: number
  measurements: number
  exercises: number
  errors: { file: string; row: number; message: string }[]
} | null>(null)
const uploadError = ref<string | null>(null)
const showErrors = ref(false)

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  uploadFile.value = input.files?.[0] ?? null
  uploadResult.value = null
  uploadError.value = null
}

async function submitUpload() {
  if (!uploadFile.value) return
  uploading.value = true
  uploadResult.value = null
  uploadError.value = null
  showErrors.value = false
  try {
    const form = new FormData()
    form.append("file", uploadFile.value)
    const resp = await api.post("/admin/upload/mfp", form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    uploadResult.value = resp.data
  } catch (e: any) {
    uploadError.value = e.response?.data?.detail ?? e.message ?? "Upload failed"
  } finally {
    uploading.value = false
  }
}
```

### Step 3: Add the Uploads tab template

In the template, inside `<div class="tab-content">`, add after the `<!-- Logs tab -->` closing `</div>`:

```html
<!-- Uploads tab -->
<div v-if="activeTab === 'uploads'" class="uploads-panel">
  <h2>Import Data</h2>
  <p class="uploads-desc">
    Upload a MyFitnessPal export ZIP to import nutrition, measurements, and exercise logs.
    Existing rows for the uploaded date range are replaced (upsert).
  </p>

  <div class="upload-form">
    <label class="file-label">
      <span>{{ uploadFile ? uploadFile.name : "Choose .zip file…" }}</span>
      <input type="file" accept=".zip" class="file-input" @change="onFileChange" />
    </label>
    <button
      class="upload-btn"
      :disabled="!uploadFile || uploading"
      @click="submitUpload"
    >
      {{ uploading ? "Importing…" : "Import" }}
    </button>
  </div>

  <div v-if="uploading" class="upload-spinner">
    <div class="spinner"></div><span>Processing ZIP…</span>
  </div>

  <div v-if="uploadResult" class="upload-result">
    <div class="result-grid">
      <div class="result-card">
        <div class="result-num">{{ uploadResult.nutrition_days }}</div>
        <div class="result-label">Nutrition days</div>
      </div>
      <div class="result-card">
        <div class="result-num">{{ uploadResult.food_diary_rows }}</div>
        <div class="result-label">Meal diary rows</div>
      </div>
      <div class="result-card">
        <div class="result-num">{{ uploadResult.measurements }}</div>
        <div class="result-label">Measurements</div>
      </div>
      <div class="result-card">
        <div class="result-num">{{ uploadResult.exercises }}</div>
        <div class="result-label">Exercise entries</div>
      </div>
    </div>

    <div v-if="uploadResult.errors.length" class="error-summary">
      <button class="toggle-errors" @click="showErrors = !showErrors">
        {{ uploadResult.errors.length }} rows skipped
        {{ showErrors ? "▲" : "▼" }}
      </button>
      <div v-if="showErrors" class="error-list">
        <div v-for="(e, i) in uploadResult.errors" :key="i" class="error-row">
          <span class="error-loc">{{ e.file }} row {{ e.row }}</span>
          <span class="error-msg">{{ e.message }}</span>
        </div>
      </div>
    </div>
    <div v-else class="no-errors">✓ No parse errors</div>
  </div>

  <div v-if="uploadError" class="upload-error">{{ uploadError }}</div>
</div>
```

### Step 4: Add scoped styles

In the `<style scoped>` block, append:

```css
/* Uploads tab */
.uploads-panel { padding: 8px 0; }
.uploads-desc { font-size: 0.82rem; color: var(--muted); margin: 0 0 20px; line-height: 1.5; }
.upload-form { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.file-label {
  display: flex; align-items: center;
  padding: 7px 14px; border: 1px solid var(--border); border-radius: 8px;
  font-size: 0.83rem; color: var(--muted); cursor: pointer;
  background: var(--bg); transition: border-color 0.12s;
}
.file-label:hover { border-color: var(--accent); }
.file-input { display: none; }
.upload-btn {
  padding: 7px 20px; background: var(--accent); color: #fff;
  border: none; border-radius: 8px; font-size: 0.85rem; font-weight: 600;
  cursor: pointer; transition: background 0.15s;
}
.upload-btn:hover:not(:disabled) { background: #2563eb; }
.upload-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.upload-spinner { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 0.85rem; }
.upload-result { margin-top: 16px; }
.result-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 12px; }
.result-card {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 12px 14px; text-align: center;
}
.result-num { font-size: 1.6rem; font-weight: 800; color: var(--text); line-height: 1; }
.result-label { font-size: 0.72rem; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
.error-summary { margin-top: 8px; }
.toggle-errors {
  background: none; border: none; color: var(--accent); font-size: 0.82rem;
  cursor: pointer; padding: 0; font-weight: 600;
}
.error-list { margin-top: 8px; max-height: 200px; overflow-y: auto; font-size: 0.78rem; }
.error-row { display: flex; gap: 12px; padding: 4px 0; border-bottom: 1px solid var(--border); }
.error-loc { color: var(--muted); flex-shrink: 0; }
.error-msg { color: #DC2626; }
.no-errors { font-size: 0.82rem; color: #16A34A; font-weight: 600; }
.upload-error { margin-top: 12px; padding: 10px 14px; background: #FEF2F2; border-radius: 8px; color: #DC2626; font-size: 0.83rem; }
```

### Step 5: Manual verification

Start the dev server and navigate to `/admin` → Uploads tab:
1. Upload `docs/myfitnesspal/File-Export-2012-03-24-to-2026-03-11.zip`
2. Verify result shows ~609 nutrition days, ~609 meal diary rows, ~715 measurements, ~3194 exercises
3. Upload the same file again — counts should be identical (upsert is idempotent)
4. Try uploading a non-zip file — should show error

### Step 6: Commit

```bash
git add frontend/src/views/Admin.vue
git commit -m "feat: Admin Uploads tab for MFP ZIP import"
```

---

## Task 5: Wire `MFPExercise` into orchestrator TABLE_MAP

**Files:**
- Modify: `backend/garminview/ingestion/orchestrator.py`

The orchestrator TABLE_MAP is used by `_get_model_for_table`. Add `mfp_exercises` so any future file-based adapter can use the standard upsert path.

### Step 1: Update TABLE_MAP

In `backend/garminview/ingestion/orchestrator.py`, find `TABLE_MAP` inside `_get_model_for_table` and add:

```python
"mfp_exercises": m.MFPExercise,
```

### Step 2: Verify

Run: `uv run python -c "from garminview.ingestion.orchestrator import IngestionOrchestrator; print('OK')"`
Expected: `OK`

### Step 3: Commit

```bash
git add backend/garminview/ingestion/orchestrator.py
git commit -m "feat: register mfp_exercises in orchestrator TABLE_MAP"
```

---

## Final verification

```bash
# Run full test suite
uv run pytest backend/ -v

# Smoke test the real export against the live DB
uv run python -c "
from garminview.core.config import get_config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
cfg = get_config()
engine = create_engine(f'mysql+pymysql://{cfg.db_url}')
with Session(engine) as s:
    for t in ['mfp_daily_nutrition', 'mfp_food_diary', 'mfp_measurements', 'mfp_exercises']:
        n = s.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar()
        print(f'{t}: {n}')
"
```
Expected: all four tables populated after uploading through the Admin UI.
