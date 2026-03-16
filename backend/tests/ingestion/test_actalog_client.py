import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from garminview.ingestion.actalog_client import ActalogClient


@pytest.mark.asyncio
async def test_login_sends_remember_me():
    """Login must include remember_me: true to receive a refresh token."""
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "token": "acc123",
        "refresh_token": "ref456",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        token = await client._login()
        call_json = mock_post.call_args.kwargs.get("json") or mock_post.call_args.args[1]
        assert call_json.get("remember_me") is True
        assert token == "acc123"  # value from mocked "token" key
        assert client.refresh_token == "ref456"


@pytest.mark.asyncio
async def test_refresh_returns_access_token():
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw",
                           refresh_token="old_ref")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"token": "new_acc"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        token = await client._refresh()
        assert token == "new_acc"  # value from mocked "token" key


@pytest.mark.asyncio
async def test_authenticate_uses_refresh_when_available():
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw",
                           refresh_token="ref")
    client._refresh = AsyncMock(return_value="acc_from_refresh")
    client._login = AsyncMock(return_value="acc_from_login")

    token = await client.authenticate()
    assert token == "acc_from_refresh"
    client._login.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_falls_back_to_login_on_refresh_failure():
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw",
                           refresh_token="bad_ref")
    client._refresh = AsyncMock(side_effect=Exception("401"))
    client._login = AsyncMock(return_value="acc_from_login")

    token = await client.authenticate()
    assert token == "acc_from_login"


@pytest.mark.asyncio
async def test_list_workouts_paginates():
    """Should keep fetching until an empty page is returned."""
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw")
    client._access_token = "tok"

    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = {"workouts": [{"id": 1}, {"id": 2}], "limit": 2, "offset": 0}
    page1.raise_for_status = MagicMock()

    page2 = MagicMock()
    page2.status_code = 200
    page2.json.return_value = {"workouts": [], "limit": 2, "offset": 2}
    page2.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[page1, page2]):
        workouts = await client.list_workouts()
        assert len(workouts) == 2


@pytest.mark.asyncio
async def test_list_pr_movements_unwraps_envelope():
    """Should extract list from a wrapped dict response."""
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw")
    client._access_token = "tok"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"pr_movements": [{"movement_id": 1}, {"movement_id": 2}]}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        prs = await client.list_pr_movements()
        assert len(prs) == 2
        assert prs[0]["movement_id"] == 1


@pytest.mark.asyncio
async def test_list_pr_movements_bare_list():
    """Should handle a bare list response without unwrapping."""
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw")
    client._access_token = "tok"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"movement_id": 3}]
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        prs = await client.list_pr_movements()
        assert len(prs) == 1
