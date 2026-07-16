"""Tests for the /admin config + schedule CRUD endpoints and the scheduler's
cron validation guard (`_register_job`).

Note: the admin `create_schedule` / `update_schedule` endpoints validate the
`source` field but do NOT reject an invalid cron expression at the API layer —
cron parsing happens later in the scheduler. The invalid-cron *rejection* is
therefore tested where it actually lives: `startup._register_job`.
"""
from garminview.models.config import AppConfig, SyncSchedule


# --- /admin/config -------------------------------------------------------

def test_get_config_lists_rows_sorted(make_client):
    def seed(s):
        s.add(AppConfig(key="b_key", value="1", category="zebra", data_type="string"))
        s.add(AppConfig(key="a_key", value="2", category="alpha", data_type="string"))
    client = make_client(seed)
    resp = client.get("/admin/config")
    assert resp.status_code == 200
    cfg = resp.json()["config"]
    # Ordered by (category, key): "alpha" before "zebra".
    assert [c["category"] for c in cfg] == ["alpha", "zebra"]
    assert cfg[0]["key"] == "a_key"
    assert cfg[0]["value"] == "2"


def test_update_config_changes_value(make_client):
    def seed(s):
        s.add(AppConfig(key="actalog_url", value="http://old", category="actalog", data_type="string"))
    client = make_client(seed)
    resp = client.put("/admin/config/actalog_url", json="http://new")
    assert resp.status_code == 200
    assert resp.json() == {"key": "actalog_url", "value": "http://new"}
    # And it persisted.
    listed = client.get("/admin/config").json()["config"]
    assert listed[0]["value"] == "http://new"


def test_update_config_missing_key_404(make_client):
    client = make_client()
    resp = client.put("/admin/config/does_not_exist", json="x")
    assert resp.status_code == 404


# --- /admin/schedules ----------------------------------------------------

def test_list_schedules_returns_seeded(make_client):
    def seed(s):
        s.add(SyncSchedule(source="garminview", mode="full",
                           cron_expression="0 3 * * *", enabled=True))
    client = make_client(seed)
    resp = client.get("/admin/schedules")
    assert resp.status_code == 200
    schedules = resp.json()["schedules"]
    assert len(schedules) == 1
    assert schedules[0]["source"] == "garminview"
    assert schedules[0]["cron"] == "0 3 * * *"
    assert schedules[0]["enabled"] is True


def test_create_schedule_valid_source(make_client):
    client = make_client()
    resp = client.post("/admin/schedules", params={"source": "actalog", "cron": "30 2 * * *"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "actalog"
    assert body["cron"] == "30 2 * * *"
    assert body["enabled"] is True
    # Confirm it landed in the DB.
    assert len(client.get("/admin/schedules").json()["schedules"]) == 1


def test_create_schedule_invalid_source_400(make_client):
    client = make_client()
    resp = client.post("/admin/schedules", params={"source": "strava", "cron": "0 3 * * *"})
    assert resp.status_code == 400
    assert "garminview" in resp.json()["detail"]


def test_update_schedule_changes_cron_and_enabled(make_client):
    def seed(s):
        s.add(SyncSchedule(id=1, source="garminview", mode="full",
                           cron_expression="0 3 * * *", enabled=True))
    client = make_client(seed)
    resp = client.put("/admin/schedules/1", params={"cron": "15 6 * * *", "enabled": False})
    assert resp.status_code == 200
    assert resp.json() == {"id": 1, "cron": "15 6 * * *", "enabled": False}
    updated = client.get("/admin/schedules").json()["schedules"][0]
    assert updated["cron"] == "15 6 * * *"
    assert updated["enabled"] is False


def test_update_schedule_missing_404(make_client):
    client = make_client()
    resp = client.put("/admin/schedules/999", params={"cron": "0 3 * * *", "enabled": True})
    assert resp.status_code == 404


def test_delete_schedule(make_client):
    def seed(s):
        s.add(SyncSchedule(id=1, source="garminview", mode="full",
                           cron_expression="0 3 * * *", enabled=True))
    client = make_client(seed)
    resp = client.delete("/admin/schedules/1")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert client.get("/admin/schedules").json()["schedules"] == []


def test_delete_schedule_missing_404(make_client):
    client = make_client()
    resp = client.delete("/admin/schedules/999")
    assert resp.status_code == 404


# --- scheduler cron validation (where invalid-cron is actually rejected) --

class _DummyScheduler:
    """Minimal stand-in for AsyncIOScheduler capturing add/remove calls."""
    def __init__(self):
        self.jobs = {}

    def get_job(self, jid):
        return self.jobs.get(jid)

    def add_job(self, fn, trigger, *, id, **kwargs):
        self.jobs[id] = trigger

    def remove_job(self, jid):
        self.jobs.pop(jid, None)


def test_register_job_skips_invalid_cron(monkeypatch):
    from garminview.core import startup
    dummy = _DummyScheduler()
    monkeypatch.setattr(startup, "_scheduler", dummy)

    row = SyncSchedule(id=1, source="garminview", mode="full",
                       cron_expression="not a valid cron", enabled=True)
    # Must not raise, and must not register a job for the bad cron.
    startup._register_job(row)
    assert dummy.jobs == {}


def test_register_job_registers_valid_cron(monkeypatch):
    from garminview.core import startup
    dummy = _DummyScheduler()
    monkeypatch.setattr(startup, "_scheduler", dummy)

    row = SyncSchedule(id=2, source="garminview", mode="full",
                       cron_expression="0 3 * * *", enabled=True)
    startup._register_job(row)
    assert "sync_garminview_2" in dummy.jobs
