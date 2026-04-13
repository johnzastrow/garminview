"""Tests for Actalog write-back client."""
from unittest.mock import MagicMock, patch
from garminview.ingestion.actalog_writeback import ActalogWritebackClient


def test_login_stores_token():
    client = ActalogWritebackClient("http://test", "a@b.com", "pass")
    with patch.object(client.client, "post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"token": "jwt123"},
            raise_for_status=lambda: None,
        )
        client.login()
    assert client.token == "jwt123"


def test_update_workout_notes():
    client = ActalogWritebackClient("http://test", "a@b.com", "pass")
    client.token = "jwt123"
    with patch.object(client.client, "request") as mock_req:
        mock_req.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": 1, "notes": "updated"},
            raise_for_status=lambda: None,
        )
        client.update_workout_notes(1, "# WOD\nFran")
    assert mock_req.called


def test_create_wod():
    client = ActalogWritebackClient("http://test", "a@b.com", "pass")
    client.token = "jwt123"
    with patch.object(client.client, "request") as mock_req:
        mock_req.return_value = MagicMock(
            status_code=201,
            json=lambda: {"id": 42, "name": "Fran"},
            raise_for_status=lambda: None,
        )
        result = client.create_wod("Fran", "FOR_TIME", "TIME")
    assert result["name"] == "Fran"


def test_retry_on_401():
    client = ActalogWritebackClient("http://test", "a@b.com", "pass")
    client.token = "expired"

    call_count = 0
    def mock_request(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MagicMock(status_code=401)
        return MagicMock(
            status_code=200,
            json=lambda: {"ok": True},
            raise_for_status=lambda: None,
        )

    with patch.object(client.client, "request", side_effect=mock_request):
        with patch.object(client, "login"):
            client._request("GET", "/api/test")
    assert call_count == 2
