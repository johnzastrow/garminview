"""Tests for the /sync router.

The real sync work (`_run_sync`) shells out to garmindb_cli.py and runs the
ingestion + analysis pipeline. Every test here patches `_run_sync` so no
subprocess or network call ever happens — we only assert the HTTP contract and
the in-memory `_running` guard.
"""
import pytest

from garminview.api.routes import sync as sync_mod


@pytest.fixture(autouse=True)
def _reset_running():
    """Ensure the module-level `_running` flag is False before/after each test."""
    sync_mod._running = False
    yield
    sync_mod._running = False


def test_status_reports_idle(make_client):
    client = make_client()
    resp = client.get("/sync/status")
    assert resp.status_code == 200
    assert resp.json() == {"running": False}


def test_status_reports_running(make_client, monkeypatch):
    monkeypatch.setattr(sync_mod, "_running", True)
    client = make_client()
    resp = client.get("/sync/status")
    assert resp.status_code == 200
    assert resp.json() == {"running": True}


def test_trigger_starts_sync_when_idle(make_client, monkeypatch):
    called = {"count": 0}

    async def fake_run_sync():
        called["count"] += 1

    monkeypatch.setattr(sync_mod, "_run_sync", fake_run_sync)

    client = make_client()
    resp = client.post("/sync/trigger")
    assert resp.status_code == 200
    assert resp.json() == {"status": "started"}


def test_trigger_conflicts_when_already_running(make_client, monkeypatch):
    # Guard: a second trigger while a sync is in flight must be rejected 409.
    monkeypatch.setattr(sync_mod, "_running", True)

    async def fake_run_sync():  # must never be scheduled in this path
        raise AssertionError("_run_sync should not be called while running")

    monkeypatch.setattr(sync_mod, "_run_sync", fake_run_sync)

    client = make_client()
    resp = client.post("/sync/trigger")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Sync already running"


def test_logs_empty_when_no_log_file(make_client, monkeypatch, tmp_path):
    # Point the sync log dir at an empty tmp dir → no sync.log → empty list.
    from garminview.core import config as config_mod

    class _Cfg:
        log_dir = str(tmp_path)

    monkeypatch.setattr(config_mod, "get_config", lambda: _Cfg())

    client = make_client()
    resp = client.get("/sync/logs")
    assert resp.status_code == 200
    assert resp.json() == {"lines": []}


def test_logs_returns_tail(make_client, monkeypatch, tmp_path):
    from garminview.core import config as config_mod

    class _Cfg:
        log_dir = str(tmp_path)

    monkeypatch.setattr(config_mod, "get_config", lambda: _Cfg())

    (tmp_path / "sync.log").write_text("line-1\nline-2\nline-3\n", encoding="utf-8")

    client = make_client()
    resp = client.get("/sync/logs", params={"lines": 2})
    assert resp.status_code == 200
    # Only the last 2 lines, with trailing newlines stripped.
    assert resp.json() == {"lines": ["line-2", "line-3"]}
