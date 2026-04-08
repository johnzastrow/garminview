# MFP Historical Data Backfill — Design Spec

**Date:** 2026-04-07

---

## Goal

Cross-populate the main `weight` and `body_composition` tables from already-parsed MFP measurement data. MFP often has years of weight and body-fat history that Garmin doesn't. Garmin data always wins on conflict; MFP fills gaps only, with a `source` column tracking origin.

---

## Architecture

Two layers:

1. **Schema** — add `source VARCHAR(16)` to `weight` and `body_composition`. Existing rows backfilled to `source = 'garmin'` in migration. New Garmin sync rows continue to write `source = 'garmin'`.
2. **Backfill function** (`backend/garminview/ingestion/mfp_backfill.py`) — reads `mfp_measurements`, writes to `weight` and `body_composition` using Garmin-wins logic.
3. **API** — `POST /admin/backfill/mfp` calls the function and returns counts. The existing `POST /admin/upload/mfp` endpoint auto-calls it after committing MFP data.
4. **Admin UI** — "Backfill from MFP" button added to the MFP upload panel. Shows row counts from the last run.

No new database tables. All data read from `mfp_measurements` (already populated by upload).

---

## Schema Changes

### `weight` table

Add column: `source VARCHAR(16) DEFAULT 'garmin'`

Existing rows: `UPDATE weight SET source = 'garmin'` in migration.

### `body_composition` table

Add column: `source VARCHAR(16) DEFAULT 'garmin'`

Existing rows: `UPDATE body_composition SET source = 'garmin'` in migration.

### Alembic migration

New file: `backend/alembic/versions/0008_add_source_to_weight_body_composition.py`

Revision chained after current head. `upgrade()` adds both columns and backfills existing rows. `downgrade()` drops both columns.

---

## Backfill Function

**File:** `backend/garminview/ingestion/mfp_backfill.py`

```python
def backfill_mfp_to_main(session: Session) -> dict[str, int]:
    """
    Read mfp_measurements and write to weight / body_composition.
    Garmin-wins: only writes where no row exists or existing source='mfp'.
    Returns {"weight_rows": N, "body_fat_rows": N}.
    """
```

**Logic — weight:**
1. Fetch all `mfp_measurements` rows where `name = 'weight'` (value in lbs)
2. Convert: `weight_kg = round(value / 2.20462, 3)`
3. For each date:
   - If no `weight` row exists → insert with `source='mfp'`
   - If existing row has `source='mfp'` → update (re-upload corrects stale data)
   - If existing row has `source='garmin'` → skip

**Logic — body fat:**
1. Fetch all `mfp_measurements` rows where `name = 'body_fat_pct'`
2. For each date:
   - If no `body_composition` row exists → insert with `fat_pct=value, source='mfp'`
   - If existing row has `source='mfp'` → update `fat_pct`
   - If existing row has `source='garmin'` → skip

**Return value:** `{"weight_rows": N, "body_fat_rows": N}` — counts of rows inserted or updated.

---

## API

### `POST /admin/backfill/mfp`

Added to `backend/garminview/api/routes/admin.py`.

No request body. Calls `backfill_mfp_to_main(session)`. Returns:

```json
{"weight_rows": 312, "body_fat_rows": 287}
```

### `POST /admin/upload/mfp` (modified)

After committing MFP data to `mfp_measurements`, automatically calls `backfill_mfp_to_main(session)`. Adds backfill counts to the upload response:

```json
{
  "nutrition_days": 1840,
  "food_diary_rows": 9200,
  "measurements": 650,
  "exercises": 120,
  "backfill": {"weight_rows": 312, "body_fat_rows": 287},
  "errors": []
}
```

---

## Admin UI

**File:** `frontend/src/views/Admin.vue` (modified)

Add to the existing MFP upload panel (after the upload button):

- **"Backfill from MFP" button** — calls `POST /admin/backfill/mfp`, shows result counts inline
- **Last backfill result** — displays `"312 weight rows, 287 body fat rows written"` after either a successful upload or a manual backfill run

No new tab or page needed — fits within the existing upload section.

---

## Garmin Sync Source Tagging

The `weight` and `body_composition` tables gain a `source` column. Existing ingestion adapters that write to these tables must set `source = 'garmin'` going forward.

Files to update:
- `backend/garminview/ingestion/file_adapters/weight.py` (or equivalent) — add `"source": "garmin"` to each emitted row dict
- Any other adapter writing to `weight` or `body_composition`

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Date has Garmin weight AND MFP weight | Skip — Garmin wins |
| Date has MFP weight, no Garmin row | Insert with `source='mfp'` |
| Date has `source='mfp'` weight, new MFP upload with different value | Overwrite — re-upload corrects stale MFP data |
| `body_composition` row has `source='garmin'` but no `fat_pct` | Skip — don't touch Garmin-sourced rows |
| No MFP measurements uploaded yet | Returns `{weight_rows: 0, body_fat_rows: 0}` |
| MFP weight value in kg instead of lbs | Not handled — MFP always exports lbs in `Measurement-Summary.csv` |

---

## Testing

- Migration: `source` column exists on both tables after upgrade; `downgrade()` removes it cleanly
- Existing rows have `source='garmin'` after migration
- `backfill_mfp_to_main`: skips dates where `weight.source='garmin'`
- `backfill_mfp_to_main`: inserts where no `weight` row exists
- `backfill_mfp_to_main`: overwrites where `weight.source='mfp'` (idempotent re-run)
- `backfill_mfp_to_main`: lbs→kg conversion correct (`180 lbs → 81.647 kg`)
- `POST /admin/backfill/mfp`: returns correct counts
- `POST /admin/upload/mfp`: backfill counts appear in response
- `body_composition` Garmin-sourced rows not touched by backfill
