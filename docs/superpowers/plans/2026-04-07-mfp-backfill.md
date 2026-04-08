# MFP Historical Data Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cross-populate the main `weight` and `body_composition` tables from MFP measurement data, with Garmin-wins conflict resolution and a `source` column tracking data origin.

**Architecture:** Alembic migration adds `source VARCHAR(16)` to both target tables. A new `mfp_backfill.py` module reads from `mfp_measurements` and writes to `weight`/`body_composition` only where no Garmin row exists. `POST /admin/backfill/mfp` exposes the function; the existing upload endpoint calls it automatically. Admin UI gains a manual "Backfill from MFP" button.

**Tech Stack:** Python/FastAPI, SQLAlchemy 2.x, Alembic, Vue 3 Composition API

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/alembic/versions/0007_add_source_to_weight_body_composition.py` | Create | Migration: add `source` column to both tables |
| `backend/garminview/models/health.py` | Modify | Add `source` field to `Weight` model |
| `backend/garminview/models/supplemental.py` | Modify | Add `source` field to `BodyComposition` model |
| `backend/garminview/ingestion/file_adapters/weight.py` | Modify | Emit `source='garmin'` on every row |
| `backend/garminview/ingestion/api_adapters/body.py` | Modify | Emit `source='garmin'` on every `BodyCompositionAdapter` row |
| `backend/garminview/ingestion/mfp_backfill.py` | Create | `backfill_mfp_to_main()` function |
| `backend/garminview/api/routes/admin.py` | Modify | Add `POST /admin/backfill/mfp`; call backfill from `upload_mfp` |
| `backend/tests/ingestion/test_mfp_backfill.py` | Create | Unit tests for backfill function |
| `backend/tests/api/test_admin_upload.py` | Modify | Add backfill response field checks |
| `frontend/src/views/Admin.vue` | Modify | Add backfill button and counts display |

---

## Task 1: Alembic migration — add `source` column

**Files:**
- Create: `backend/alembic/versions/0007_add_source_to_weight_body_composition.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/alembic/versions/0007_add_source_to_weight_body_composition.py
"""add source column to weight and body_composition

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('weight',
        sa.Column('source', sa.String(16), nullable=True, server_default='garmin'))
    op.execute("UPDATE weight SET source = 'garmin' WHERE source IS NULL")

    op.add_column('body_composition',
        sa.Column('source', sa.String(16), nullable=True, server_default='garmin'))
    op.execute("UPDATE body_composition SET source = 'garmin' WHERE source IS NULL")


def downgrade() -> None:
    op.drop_column('weight', 'source')
    op.drop_column('body_composition', 'source')
```

- [ ] **Step 2: Apply migration to dev DB**

```bash
cd backend && uv run alembic upgrade head
```

Expected: `Running upgrade 0006 -> 0007` with no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/0007_add_source_to_weight_body_composition.py
git commit -m "feat: migration 0007 — add source column to weight and body_composition"
```

---

## Task 2: Update SQLAlchemy models

**Files:**
- Modify: `backend/garminview/models/health.py`
- Modify: `backend/garminview/models/supplemental.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_models.py — add to existing file
def test_weight_has_source_column(engine):
    from sqlalchemy import inspect
    cols = {c['name'] for c in inspect(engine).get_columns('weight')}
    assert 'source' in cols

def test_body_composition_has_source_column(engine):
    from sqlalchemy import inspect
    cols = {c['name'] for c in inspect(engine).get_columns('body_composition')}
    assert 'source' in cols
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_models.py::test_weight_has_source_column tests/test_models.py::test_body_composition_has_source_column -v
```

Expected: FAIL — `source` not in columns.

- [ ] **Step 3: Update `Weight` model in `backend/garminview/models/health.py`**

```python
class Weight(Base):
    __tablename__ = "weight"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(16), default="garmin")
```

- [ ] **Step 4: Update `BodyComposition` model in `backend/garminview/models/supplemental.py`**

Find the `BodyComposition` class (around line 93) and add:

```python
class BodyComposition(Base):
    __tablename__ = "body_composition"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    fat_pct: Mapped[float | None] = mapped_column(Float)
    muscle_mass_kg: Mapped[float | None] = mapped_column(Float)
    bone_mass_kg: Mapped[float | None] = mapped_column(Float)
    hydration_pct: Mapped[float | None] = mapped_column(Float)
    bmi: Mapped[float | None] = mapped_column(Float)
    bmr: Mapped[int | None] = mapped_column(Integer)
    metabolic_age: Mapped[int | None] = mapped_column(SmallInteger)
    visceral_fat: Mapped[int | None] = mapped_column(SmallInteger)
    physique_rating: Mapped[int | None] = mapped_column(SmallInteger)
    source: Mapped[str | None] = mapped_column(String(16), default="garmin")
```

You will need `String` imported — check the existing imports at the top of `supplemental.py` and add it if absent.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_models.py::test_weight_has_source_column tests/test_models.py::test_body_composition_has_source_column -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/garminview/models/health.py backend/garminview/models/supplemental.py
git commit -m "feat: add source field to Weight and BodyComposition models"
```

---

## Task 3: Tag Garmin adapters with source='garmin'

**Files:**
- Modify: `backend/garminview/ingestion/file_adapters/weight.py`
- Modify: `backend/garminview/ingestion/api_adapters/body.py`

- [ ] **Step 1: Update `WeightAdapter.fetch` to emit `source='garmin'`**

In `backend/garminview/ingestion/file_adapters/weight.py`, the `yield` dict at line 33 becomes:

```python
            yield {
                "date": date.fromisoformat(d),
                "weight_kg": weight,
                "source": "garmin",
            }
```

- [ ] **Step 2: Update `BodyCompositionAdapter._parse` to emit `source='garmin'`**

In `backend/garminview/ingestion/api_adapters/body.py`, the `_parse` method return becomes:

```python
    def _parse(self, d: date, raw: dict) -> dict:
        return {
            "date": d,
            "weight_kg": raw.get("weight"),
            "fat_pct": raw.get("fatPercent"),
            "muscle_mass_kg": raw.get("muscleMass"),
            "bone_mass_kg": raw.get("boneMass"),
            "hydration_pct": raw.get("bodyWater"),
            "bmi": raw.get("bmi"),
            "bmr": raw.get("bmr"),
            "metabolic_age": raw.get("metabolicAge"),
            "visceral_fat": raw.get("visceralFat"),
            "physique_rating": raw.get("physiqueRating"),
            "source": "garmin",
        }
```

- [ ] **Step 3: Run the full test suite to confirm nothing breaks**

```bash
cd backend && uv run pytest -q
```

Expected: all existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/garminview/ingestion/file_adapters/weight.py \
        backend/garminview/ingestion/api_adapters/body.py
git commit -m "feat: tag Garmin weight and body_composition rows with source='garmin'"
```

---

## Task 4: Write `backfill_mfp_to_main()`

**Files:**
- Create: `backend/garminview/ingestion/mfp_backfill.py`
- Create: `backend/tests/ingestion/test_mfp_backfill.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/ingestion/test_mfp_backfill.py
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import garminview.models  # noqa: F401
from garminview.core.database import Base
from garminview.models.health import Weight
from garminview.models.supplemental import BodyComposition
from garminview.models.nutrition import MFPMeasurement


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        yield s


def _add_mfp_weight(session, d: date, lbs: float):
    session.add(MFPMeasurement(date=d, name="weight", value=lbs, unit="lbs"))
    session.commit()


def _add_mfp_bf(session, d: date, pct: float):
    session.add(MFPMeasurement(date=d, name="body_fat_pct", value=pct, unit="%"))
    session.commit()


def _add_garmin_weight(session, d: date, kg: float):
    session.add(Weight(date=d, weight_kg=kg, source="garmin"))
    session.commit()


def _add_mfp_weight_row(session, d: date, kg: float):
    session.add(Weight(date=d, weight_kg=kg, source="mfp"))
    session.commit()


def _add_garmin_body_comp(session, d: date, fat_pct: float):
    session.add(BodyComposition(date=d, fat_pct=fat_pct, source="garmin"))
    session.commit()


def test_backfill_inserts_weight_where_no_garmin_row(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_mfp_weight(session, d, 180.0)  # 180 lbs = 81.647 kg

    result = backfill_mfp_to_main(session)

    row = session.get(Weight, d)
    assert row is not None
    assert abs(row.weight_kg - 81.647) < 0.01
    assert row.source == "mfp"
    assert result["weight_rows"] == 1


def test_backfill_skips_garmin_weight(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_garmin_weight(session, d, 75.0)
    _add_mfp_weight(session, d, 180.0)  # would be ~81.6 kg

    result = backfill_mfp_to_main(session)

    row = session.get(Weight, d)
    assert row.weight_kg == 75.0   # Garmin wins
    assert row.source == "garmin"
    assert result["weight_rows"] == 0


def test_backfill_overwrites_stale_mfp_weight(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_mfp_weight_row(session, d, 80.0)   # old MFP row
    _add_mfp_weight(session, d, 180.0)      # new MFP export: 180 lbs = 81.647 kg

    result = backfill_mfp_to_main(session)

    row = session.get(Weight, d)
    assert abs(row.weight_kg - 81.647) < 0.01
    assert result["weight_rows"] == 1


def test_backfill_inserts_body_fat_where_no_garmin_row(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_mfp_bf(session, d, 18.5)

    result = backfill_mfp_to_main(session)

    row = session.get(BodyComposition, d)
    assert row is not None
    assert row.fat_pct == 18.5
    assert row.source == "mfp"
    assert result["body_fat_rows"] == 1


def test_backfill_skips_garmin_body_composition(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_garmin_body_comp(session, d, 20.0)
    _add_mfp_bf(session, d, 18.5)

    result = backfill_mfp_to_main(session)

    row = session.get(BodyComposition, d)
    assert row.fat_pct == 20.0   # Garmin wins
    assert row.source == "garmin"
    assert result["body_fat_rows"] == 0


def test_backfill_no_mfp_data_returns_zeros(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    result = backfill_mfp_to_main(session)
    assert result == {"weight_rows": 0, "body_fat_rows": 0}


def test_lbs_to_kg_conversion(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    _add_mfp_weight(session, date(2024, 3, 1), 198.0)  # 198 lbs = 89.811 kg

    backfill_mfp_to_main(session)

    row = session.get(Weight, date(2024, 3, 1))
    assert abs(row.weight_kg - 89.811) < 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/ingestion/test_mfp_backfill.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'garminview.ingestion.mfp_backfill'`

- [ ] **Step 3: Write `backend/garminview/ingestion/mfp_backfill.py`**

```python
"""Cross-populate weight and body_composition from mfp_measurements.

Garmin-wins: only writes where no row exists or existing source='mfp'.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from garminview.models.health import Weight
from garminview.models.nutrition import MFPMeasurement
from garminview.models.supplemental import BodyComposition

_LBS_TO_KG = 1 / 2.20462


def backfill_mfp_to_main(session: Session) -> dict[str, int]:
    """Read mfp_measurements and write to weight / body_composition.

    Returns {"weight_rows": N, "body_fat_rows": N}.
    """
    weight_written = 0
    body_fat_written = 0

    mfp_rows = (
        session.query(MFPMeasurement)
        .filter(MFPMeasurement.name.in_(["weight", "body_fat_pct"]))
        .all()
    )

    for row in mfp_rows:
        if row.name == "weight":
            weight_written += _backfill_weight(session, row)
        elif row.name == "body_fat_pct":
            body_fat_written += _backfill_body_fat(session, row)

    session.flush()
    return {"weight_rows": weight_written, "body_fat_rows": body_fat_written}


def _backfill_weight(session: Session, mfp_row: MFPMeasurement) -> int:
    kg = round(mfp_row.value * _LBS_TO_KG, 3)
    existing = session.get(Weight, mfp_row.date)

    if existing is None:
        session.add(Weight(date=mfp_row.date, weight_kg=kg, source="mfp"))
        return 1
    if existing.source == "mfp":
        existing.weight_kg = kg
        return 1
    return 0  # Garmin row — skip


def _backfill_body_fat(session: Session, mfp_row: MFPMeasurement) -> int:
    existing = session.get(BodyComposition, mfp_row.date)

    if existing is None:
        session.add(BodyComposition(
            date=mfp_row.date, fat_pct=mfp_row.value, source="mfp"
        ))
        return 1
    if existing.source == "mfp":
        existing.fat_pct = mfp_row.value
        return 1
    return 0  # Garmin row — skip
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/ingestion/test_mfp_backfill.py -v
```

Expected: 7/7 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/garminview/ingestion/mfp_backfill.py \
        backend/tests/ingestion/test_mfp_backfill.py
git commit -m "feat: add backfill_mfp_to_main() — cross-populate weight and body_composition from MFP"
```

---

## Task 5: API endpoint + auto-trigger on upload

**Files:**
- Modify: `backend/garminview/api/routes/admin.py`
- Modify: `backend/tests/api/test_admin_upload.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/api/test_admin_upload.py`:

```python
@pytest.mark.asyncio
async def test_upload_mfp_includes_backfill_counts(engine):
    """Upload response includes backfill key with weight_rows and body_fat_rows."""
    from garminview.api.main import create_app
    app = create_app(engine)
    zdata = _make_mfp_zip()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/admin/upload/mfp",
            files={"file": ("export.zip", zdata, "application/zip")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "backfill" in body
    assert "weight_rows" in body["backfill"]
    assert "body_fat_rows" in body["backfill"]
    # MFP has 1 weight + 1 body fat row; no Garmin rows exist → both backfilled
    assert body["backfill"]["weight_rows"] == 1
    assert body["backfill"]["body_fat_rows"] == 1


@pytest.mark.asyncio
async def test_backfill_mfp_endpoint(engine):
    """POST /admin/backfill/mfp returns counts dict."""
    from garminview.api.main import create_app
    app = create_app(engine)
    # Seed mfp_measurements directly
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    from garminview.models.nutrition import MFPMeasurement
    from datetime import date
    with Session() as s:
        s.add(MFPMeasurement(date=date(2024, 6, 1), name="weight", value=170.0, unit="lbs"))
        s.add(MFPMeasurement(date=date(2024, 6, 1), name="body_fat_pct", value=20.0, unit="%"))
        s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/admin/backfill/mfp")
    assert resp.status_code == 200
    body = resp.json()
    assert body["weight_rows"] == 1
    assert body["body_fat_rows"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/api/test_admin_upload.py::test_upload_mfp_includes_backfill_counts tests/api/test_admin_upload.py::test_backfill_mfp_endpoint -v
```

Expected: FAIL.

- [ ] **Step 3: Add `POST /admin/backfill/mfp` to `admin.py`**

Find the block after `upload_mfp` (around line 658, after the `return` statement) and add:

```python
@router.post("/backfill/mfp")
def backfill_mfp(session: Annotated[Session, Depends(get_db)]):
    """Cross-populate weight and body_composition from already-uploaded MFP measurements."""
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    result = backfill_mfp_to_main(session)
    session.commit()
    return result
```

- [ ] **Step 4: Call backfill automatically in `upload_mfp`**

Find the `session.commit()` near line 649 in `upload_mfp` and add the backfill call immediately after:

```python
    session.commit()

    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    backfill = backfill_mfp_to_main(session)
    session.commit()

    return {
        "nutrition_days": len(result.nutrition_daily),
        "food_diary_rows": len(result.food_diary),
        "measurements": len(result.measurements),
        "exercises": len(result.exercises),
        "backfill": backfill,
        "errors": [{"file": e.file, "row": e.row, "message": e.message} for e in result.errors],
    }
```

(Replace the existing `return` block entirely.)

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/api/test_admin_upload.py -v
```

Expected: all pass.

- [ ] **Step 6: Run full suite**

```bash
cd backend && uv run pytest -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/garminview/api/routes/admin.py \
        backend/tests/api/test_admin_upload.py
git commit -m "feat: add POST /admin/backfill/mfp endpoint and auto-trigger on upload"
```

---

## Task 6: Admin UI — backfill button and counts

**Files:**
- Modify: `frontend/src/views/Admin.vue`

- [ ] **Step 1: Add backfill result display to the upload result block**

In `Admin.vue`, find the `<div v-if="uploadResult" class="upload-result">` block (around line 139). After the existing result grid and before `v-if="uploadResult.errors.length"`, add:

```html
          <div v-if="uploadResult.backfill" class="backfill-result">
            <span class="backfill-label">Backfilled to main tables:</span>
            <span class="backfill-count">{{ uploadResult.backfill.weight_rows }} weight rows</span>
            <span class="backfill-sep">·</span>
            <span class="backfill-count">{{ uploadResult.backfill.body_fat_rows }} body fat rows</span>
          </div>
```

- [ ] **Step 2: Add "Backfill from MFP" button after the upload form**

After the `<div v-if="uploadError" ...>` line (around line 174) and before the closing `</div>` of the uploads panel, add:

```html
        <div class="backfill-section">
          <button class="btn-secondary" :disabled="backfilling" @click="runBackfill">
            {{ backfilling ? 'Backfilling…' : 'Backfill from MFP' }}
          </button>
          <span v-if="backfillResult" class="backfill-inline">
            {{ backfillResult.weight_rows }} weight · {{ backfillResult.body_fat_rows }} body fat rows written
          </span>
          <span v-if="backfillError" class="upload-error">{{ backfillError }}</span>
        </div>
```

- [ ] **Step 3: Add reactive state and `runBackfill` function**

In the `<script setup>` section, find the upload state variables (around line 492) and add after them:

```typescript
const backfilling = ref(false)
const backfillResult = ref<{ weight_rows: number; body_fat_rows: number } | null>(null)
const backfillError = ref<string | null>(null)

async function runBackfill() {
  backfilling.value = true
  backfillResult.value = null
  backfillError.value = null
  try {
    const resp = await api.post('/admin/backfill/mfp')
    backfillResult.value = resp.data
  } catch (e: any) {
    backfillError.value = e.response?.data?.detail ?? e.message ?? 'Backfill failed'
  } finally {
    backfilling.value = false
  }
}
```

- [ ] **Step 4: Add styles**

In the `<style scoped>` section at the bottom of `Admin.vue`, add:

```css
.backfill-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.backfill-result {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  color: var(--muted);
  margin-top: 8px;
}
.backfill-label { font-weight: 600; color: var(--text); }
.backfill-sep { color: var(--border); }
.backfill-inline { font-size: 0.82rem; color: var(--muted); }
```

- [ ] **Step 5: Verify frontend builds**

```bash
cd frontend && npx vite build 2>&1 | tail -5
```

Expected: `✓ built in X.XXs`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/Admin.vue
git commit -m "feat: add Backfill from MFP button and counts to Admin uploads panel"
```

---

## Final QA

- [ ] **Run full backend test suite**

```bash
cd backend && uv run pytest -q
```

Expected: all pass.

- [ ] **Rebuild and restart**

```bash
docker build -t ghcr.io/johnzastrow/garminview-backend:local ./backend -q
docker build -t ghcr.io/johnzastrow/garminview-frontend:local ./frontend -q
docker compose down && docker compose up -d
```

- [ ] **Smoke test: upload MFP ZIP in Admin → Uploads, confirm backfill counts appear**

- [ ] **Smoke test: click "Backfill from MFP" button, confirm counts shown**

- [ ] **Bump version to 0.9.1**

In `backend/pyproject.toml` change `version = "0.9.0"` → `"0.9.1"`.
In `backend/garminview/api/main.py` change both `"0.9.0"` strings → `"0.9.1"`.

```bash
git add backend/pyproject.toml backend/garminview/api/main.py
git commit -m "chore: bump version to v0.9.1 (MFP backfill)"
```
