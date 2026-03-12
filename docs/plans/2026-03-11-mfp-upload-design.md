# MyFitnessPal ZIP Upload — Design

**Date:** 2026-03-11
**Status:** Approved

---

## Overview

Allow users to upload a MyFitnessPal data export ZIP through the Admin UI. The backend extracts and parses the three CSVs in-memory, upserts all valid rows into the database, skips bad rows, and returns a per-table row count plus a list of any parse errors.

---

## Export Format

MFP exports a single ZIP containing three CSVs:

| File (glob) | Rows (sample export) | Content |
|---|---|---|
| `Nutrition-Summary-*.csv` | ~609 | Per-meal macro totals (one row per meal per day) |
| `Measurement-Summary-*.csv` | ~715 | Body weight and body fat % entries |
| `Exercise-Summary-*.csv` | ~3,194 | Manual exercise log entries |

Files are matched by glob prefix — the date suffix in the filename is ignored.

---

## Data Model Changes

### 1. New table: `mfp_exercises`

Stores MFP manual exercise log entries, separate from Garmin activity data to allow direct comparison.

```python
class MFPExercise(Base):
    __tablename__ = "mfp_exercises"
    id:            autoincrement PK
    date:          Date (indexed)
    exercise_name: String(256)
    exercise_type: String(32) | None   # "Cardio" | "Strength"
    calories:      Float | None
    duration_min:  Float | None
    sets:          Integer | None
    reps_per_set:  Integer | None
    weight_lbs:    Float | None
    steps:         Integer | None
    note:          String(512) | None
```

### 2. Extend `mfp_food_diary`

Add columns to capture the full per-meal macro breakdown available in the Nutrition Summary export:

- `sodium_mg: Float | None`
- `sugar_g: Float | None`
- `fiber_g: Float | None`
- `cholesterol_mg: Float | None`

Applied via lazy `ALTER TABLE` (same pattern as `data_quality_flags` anomaly columns).

### 3. No changes to `mfp_daily_nutrition` or `mfp_measurements`

Existing columns map cleanly to the export format.

---

## Column Mappings

### Nutrition-Summary → `mfp_food_diary` (per-meal rows)

| CSV column | Model field |
|---|---|
| Date | date |
| Meal | food_name (also used for meal) |
| Calories | calories |
| Fat (g) | fat_g |
| Carbohydrates (g) | carbs_g |
| Protein (g) | protein_g |
| Sodium (mg) | sodium_mg |
| Sugar | sugar_g |
| Fiber | fiber_g |
| Cholesterol | cholesterol_mg |

### Nutrition-Summary → `mfp_daily_nutrition` (daily aggregation)

Group by Date, sum all macro columns, count distinct meals → `logged_meals`.

### Measurement-Summary → `mfp_measurements`

| CSV column | name | unit | notes |
|---|---|---|---|
| Body Fat % | `body_fat_pct` | `%` | |
| Weight | `weight` | `lbs` | stored as-is (lbs); existing adapter converts to kg — upload preserves original unit |

### Exercise-Summary → `mfp_exercises`

| CSV column | Model field |
|---|---|
| Date | date |
| Exercise | exercise_name |
| Type | exercise_type |
| Exercise Calories | calories |
| Exercise Minutes | duration_min |
| Sets | sets |
| Reps Per Set | reps_per_set |
| Pounds | weight_lbs |
| Steps | steps |
| Note | note |

---

## Deduplication Strategy

Consistent with existing pipeline patterns:

| Table | PK type | Strategy |
|---|---|---|
| `mfp_food_diary` | autoincrement | Delete date range covered by upload, then bulk insert |
| `mfp_exercises` | autoincrement | Delete date range covered by upload, then bulk insert |
| `mfp_daily_nutrition` | natural (date) | Upsert — `ON DUPLICATE KEY UPDATE` / `ON CONFLICT DO UPDATE` |
| `mfp_measurements` | natural (date, name) | Upsert — `ON DUPLICATE KEY UPDATE` / `ON CONFLICT DO UPDATE` |

Date range for delete is derived from `min(date)` and `max(date)` across all rows parsed from the upload.

---

## API Endpoint

```
POST /admin/upload/mfp
Content-Type: multipart/form-data
Body: file=<zip bytes>
```

**Response (200 OK):**
```json
{
  "nutrition_days": 609,
  "food_diary_rows": 609,
  "measurements": 715,
  "exercises": 3191,
  "errors": [
    { "file": "Exercise-Summary-2012-03-24-to-2026-03-11.csv", "row": 142, "message": "Invalid date '2019-13-01'" }
  ]
}
```

- Bad rows are skipped (non-fatal); valid rows still insert.
- Returns `400` if the ZIP contains none of the expected files.
- Returns `422` if the uploaded file is not a valid ZIP.

---

## Admin UI — Uploads Tab

Location: `/admin` page, new "Uploads" tab alongside Sync and Schedule tabs.

Components:
- File picker restricted to `.zip`
- "Import" button (disabled until file selected)
- Upload spinner while POST is in-flight
- Result card showing per-table row counts on success
- Collapsible error list (hidden when empty) showing file, row number, and message for each skipped row

---

## Files to Create / Modify

| File | Change |
|---|---|
| `backend/garminview/models/nutrition.py` | Add `MFPExercise` model; extend `MFPFoodDiaryEntry` with 4 columns |
| `backend/garminview/models/__init__.py` | Export `MFPExercise` |
| `backend/garminview/api/routes/admin.py` | Add `POST /admin/upload/mfp` endpoint + lazy migration for new columns |
| `frontend/src/views/Admin.vue` | Add "Uploads" tab with file picker and results display |

No new adapter file needed — parsing logic lives directly in the upload endpoint (single-use, not reusable pipeline adapter).

---

## Out of Scope

- Streaming progress (SSE) — counts are small enough that a synchronous JSON response is appropriate
- Automatic re-upload on schedule — manual upload only
- Parsing individual food items — MFP export does not include per-item food diary data, only meal-level aggregates
