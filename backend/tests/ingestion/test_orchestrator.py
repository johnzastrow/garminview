from datetime import date, datetime

from garminview.ingestion.orchestrator import IngestionOrchestrator
from garminview.models.sync import SyncLog
from garminview.models.health import DailySummary, Stress, SleepEvent


def _seed_stress(conn, rows):
    """rows: list of (timestamp_str, stress_int)."""
    conn.executescript("CREATE TABLE stress (timestamp TEXT, stress INTEGER);")
    conn.executemany("INSERT INTO stress VALUES (?,?)", rows)


def _seed_sleep_events(conn, rows):
    """rows: list of (timestamp_str, event, duration_str)."""
    conn.executescript(
        "CREATE TABLE sleep_events (timestamp TEXT, event TEXT, duration TEXT);"
    )
    conn.executemany("INSERT INTO sleep_events VALUES (?,?,?)", rows)


def test_orchestrator_runs_file_adapters(session, tmp_path, monkeypatch):
    orch = IngestionOrchestrator(session=session, health_data_dir=tmp_path)
    # Should not raise even with empty data dir
    orch.run_incremental()
    logs = session.query(SyncLog).all()
    assert len(logs) > 0


def test_run_full_ingests_from_health_data_dir(session, make_garmindb):
    """Regression: the class of bug just fixed was the orchestrator reading from
    the wrong data dir, so nothing landed. Prove run_full actually reads the
    garmindb DBs under the given health_data_dir and upserts the rows."""

    def seed(conn):
        _seed_stress(
            conn,
            [
                ("2025-06-15 10:00:00.000000", 42),
                ("2025-06-16 10:00:00.000000", 30),
                ("2025-06-15 10:01:00.000000", -1),  # guard: negative -> skipped
            ],
        )
        _seed_sleep_events(
            conn,
            [
                ("2025-06-15 23:30:00.000000", "deep", "00:45:00.000000"),
                ("2025-06-15 23:45:00.000000", "light", "00:20:00.000000"),
            ],
        )

    hdd = make_garmindb("garmin.db", seed)
    orch = IngestionOrchestrator(session=session, health_data_dir=hdd)
    orch.run_full(date(2025, 6, 1), date(2025, 6, 30))

    # The actual data landed in the target tables.
    stresses = session.query(Stress).order_by(Stress.timestamp).all()
    assert [s.stress_level for s in stresses] == [42, 30]

    events = session.query(SleepEvent).order_by(SleepEvent.start).all()
    assert [e.event_type for e in events] == ["deep", "light"]
    assert [e.duration_min for e in events] == [45, 20]

    # And the sync log records the successful upsert count for stress.
    stress_log = (
        session.query(SyncLog).filter_by(source="garmindb:stress").one()
    )
    assert stress_log.status == "success"
    assert stress_log.records_upserted == 2


def test_run_incremental_window_starts_three_days_before_last_summary(
    session, make_garmindb
):
    """run_incremental() derives its start from max(DailySummary.date) - 3 days.
    Seed a summary and two stress rows straddling that boundary; only the row
    inside the derived window should be ingested."""

    session.add(DailySummary(date=date(2025, 6, 20)))
    session.commit()
    # Window start = 2025-06-20 - 3 = 2025-06-17.

    def seed(conn):
        _seed_stress(
            conn,
            [
                ("2025-06-18 08:00:00.000000", 55),  # inside window -> ingested
                ("2025-06-10 08:00:00.000000", 60),  # before window -> excluded
            ],
        )

    hdd = make_garmindb("garmin.db", seed)
    orch = IngestionOrchestrator(session=session, health_data_dir=hdd)
    orch.run_incremental()

    stresses = session.query(Stress).all()
    assert len(stresses) == 1
    assert stresses[0].timestamp == datetime(2025, 6, 18, 8, 0, 0)
    assert stresses[0].stress_level == 55


def test_run_full_is_idempotent(session, make_garmindb):
    """Running the same range twice must not duplicate rows — stress upserts on
    its timestamp PK, and sleep_events is delete-then-insert per range."""

    def seed(conn):
        _seed_stress(
            conn,
            [
                ("2025-06-15 10:00:00.000000", 42),
                ("2025-06-16 10:00:00.000000", 30),
            ],
        )
        _seed_sleep_events(
            conn,
            [
                ("2025-06-15 23:30:00.000000", "deep", "00:45:00.000000"),
                ("2025-06-15 23:45:00.000000", "light", "00:20:00.000000"),
            ],
        )

    hdd = make_garmindb("garmin.db", seed)
    orch = IngestionOrchestrator(session=session, health_data_dir=hdd)

    orch.run_full(date(2025, 6, 1), date(2025, 6, 30))
    orch.run_full(date(2025, 6, 1), date(2025, 6, 30))

    assert session.query(Stress).count() == 2
    assert session.query(SleepEvent).count() == 2
