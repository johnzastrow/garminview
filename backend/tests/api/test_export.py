import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_export_csv_empty(engine):
    from garminview.api.main import create_app
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/export/csv", params={"start": "2024-01-01", "end": "2024-01-31"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


@pytest.mark.asyncio
async def test_export_json_empty(engine):
    from garminview.api.main import create_app
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/export/json", params={"start": "2024-01-01", "end": "2024-01-31"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.text == "[]"


@pytest.mark.asyncio
async def test_export_csv_unknown_metric(engine):
    from garminview.api.main import create_app
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/export/csv",
            params={"start": "2024-01-01", "end": "2024-01-31", "metrics": "bogus_table"},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_export_csv_with_data(engine):
    from datetime import date
    from garminview.api.main import create_app
    from garminview.models.health import DailySummary
    from sqlalchemy.orm import Session

    # Seed one row
    with Session(engine) as session:
        session.add(DailySummary(date=date(2024, 1, 15), steps=8000))
        session.commit()

    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/export/csv",
            params={"start": "2024-01-01", "end": "2024-01-31", "metrics": "daily_summary"},
        )
    assert response.status_code == 200
    lines = response.text.strip().splitlines()
    assert len(lines) == 2  # header + 1 data row
    assert "date" in lines[0]
    assert "2024-01-15" in lines[1]
