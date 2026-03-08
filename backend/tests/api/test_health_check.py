import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_check(engine):
    from garminview.api.main import create_app
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_root(engine):
    from garminview.api.main import create_app
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_daily_summaries_empty(engine):
    from garminview.api.main import create_app
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/daily")
    assert response.status_code == 200
    assert response.json() == []
