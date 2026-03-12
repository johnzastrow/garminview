import io
import zipfile
import pytest
from httpx import AsyncClient, ASGITransport


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


@pytest.mark.asyncio
async def test_upload_mfp_returns_counts(engine):
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
    assert body["nutrition_days"] == 1
    assert body["food_diary_rows"] == 1
    assert body["measurements"] == 2   # body fat + weight
    assert body["exercises"] == 1
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_upload_mfp_idempotent(engine):
    """Uploading the same ZIP twice should not duplicate rows."""
    from garminview.api.main import create_app
    app = create_app(engine)
    zdata = _make_mfp_zip()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/admin/upload/mfp", files={"file": ("export.zip", zdata, "application/zip")})
        resp = await client.post("/admin/upload/mfp", files={"file": ("export.zip", zdata, "application/zip")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["nutrition_days"] == 1
    assert body["exercises"] == 1


@pytest.mark.asyncio
async def test_upload_mfp_invalid_zip(engine):
    from garminview.api.main import create_app
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/admin/upload/mfp",
            files={"file": ("bad.zip", b"not a zip", "application/zip")},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_mfp_wrong_file_type(engine):
    from garminview.api.main import create_app
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/admin/upload/mfp",
            files={"file": ("data.csv", b"col1,col2\n1,2\n", "text/csv")},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_mfp_creates_exercises_table_if_missing(engine):
    """Verifies _migrate_mfp_food_diary_columns creates mfp_exercises when absent."""
    from sqlalchemy import inspect as sa_inspect, text as sa_text
    # Drop mfp_exercises to simulate a DB that predates the table
    with engine.begin() as conn:
        conn.execute(sa_text("DROP TABLE IF EXISTS mfp_exercises"))
    # Confirm it's gone
    assert "mfp_exercises" not in sa_inspect(engine).get_table_names()
    # Upload should recreate it
    from garminview.api.main import create_app
    app = create_app(engine)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Exercise-Summary-2024.csv",
                    "Date,Exercise,Type,Exercise Calories,Exercise Minutes,Sets,Reps Per Set,Pounds,Steps,Note\n"
                    "2024-01-15,Running,Cardio,350.0,30.0,,,,5000,\n")
        zf.writestr("Nutrition-Summary-2024.csv",
                    "Date,Meal,Calories,Fat (g),Saturated Fat,Polyunsaturated Fat,Monounsaturated Fat,"
                    "Trans Fat,Cholesterol,Sodium (mg),Potassium,Carbohydrates (g),Fiber,Sugar,Protein (g),"
                    "Vitamin A,Vitamin C,Calcium,Iron,Note\n"
                    "2024-01-15,Breakfast,500.0,15.0,0.0,0.0,0.0,0.0,0.0,600.0,0.0,70.0,3.0,20.0,25.0,0.0,0.0,0.0,0.0,\n")
        zf.writestr("Measurement-Summary-2024.csv", "Date,Body Fat %,Weight\n2024-01-15,18.5,175.0\n")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/admin/upload/mfp",
            files={"file": ("export.zip", buf.getvalue(), "application/zip")},
        )
    assert resp.status_code == 200
    assert resp.json()["exercises"] == 1
    assert "mfp_exercises" in sa_inspect(engine).get_table_names()


@pytest.mark.asyncio
async def test_upload_mfp_no_mfp_files_returns_400(engine):
    """A valid ZIP with no MFP CSVs should return 400, not 422."""
    from garminview.api.main import create_app
    app = create_app(engine)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("unrelated.txt", "hello")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/admin/upload/mfp",
            files={"file": ("export.zip", buf.getvalue(), "application/zip")},
        )
    assert resp.status_code == 400
