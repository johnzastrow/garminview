"""End-to-end flow test for the Polar importer.

Points ``run_import`` at the fixtures/polar directory (which holds one file
per Polar export type) with the in-memory ``session`` fixture and asserts that
rows land in the target polar_* staging tables and the import log is complete.
"""

from pathlib import Path

from garminview.ingestion.polar.importer import run_import
from garminview.models.polar import (
    Polar247OHR,
    PolarAccount,
    PolarActivity,
    PolarActivityMetSource,
    PolarActivitySample,
    PolarCalendarItem,
    PolarDevice,
    PolarExercise,
    PolarExerciseSample,
    PolarExerciseStatistic,
    PolarExerciseZone,
    PolarFitnessTest,
    PolarImportFile,
    PolarImportLog,
    PolarProgram,
    PolarSleep,
    PolarSleepState,
    PolarSportProfile,
    PolarTrainingSession,
    PolarTrainingTarget,
    PolarTrainingTargetPhase,
)

FIXTURES = Path(__file__).parent / "fixtures" / "polar"


def test_run_import_full_flow(session):
    summary = run_import(session, str(FIXTURES))

    # Summary bookkeeping
    assert summary["status"] == "complete"
    assert summary["files_errored"] == 0
    assert summary["files_found"] == len(list(FIXTURES.glob("*.json")))
    assert summary["files_imported"] == summary["files_found"]

    # Training session + children
    ts = session.query(PolarTrainingSession).one()
    assert ts.session_id == "332906208"
    assert ts.name == "Morning Run"
    assert session.query(PolarExercise).count() == 1
    assert session.query(PolarExerciseStatistic).count() == 2
    assert session.query(PolarExerciseZone).count() == 2
    assert session.query(PolarExerciseSample).count() == 1

    # Activity + children
    act = session.query(PolarActivity).one()
    assert str(act.date) == "2024-01-15"
    assert session.query(PolarActivitySample).count() == 2  # mets + steps
    assert session.query(PolarActivityMetSource).count() == 2

    # Sleep
    assert session.query(PolarSleep).count() == 1
    assert session.query(PolarSleepState).count() == 4

    # 247ohr / fitness test / training target
    assert session.query(Polar247OHR).count() == 1
    assert session.query(PolarFitnessTest).count() == 1
    assert session.query(PolarTrainingTarget).count() == 1
    assert session.query(PolarTrainingTargetPhase).count() == 2

    # Account merged from account-data + account-profile
    acct = session.query(PolarAccount).one()
    assert acct.user_id == 17498985
    assert acct.username == "runner1"  # from account-data
    assert acct.city == "Pittsburgh"  # from account-profile

    # Calendar + generic blob tables
    assert session.query(PolarCalendarItem).count() == 1
    assert session.query(PolarSportProfile).count() == 2
    assert session.query(PolarDevice).count() == 1
    assert session.query(PolarProgram).count() == 1

    # Import log + per-file records
    log = session.query(PolarImportLog).one()
    assert log.status == "complete"
    assert log.files_errored == 0
    file_rows = session.query(PolarImportFile).all()
    assert len(file_rows) >= summary["files_found"]
    assert all(f.status == "imported" for f in file_rows)


def test_run_import_is_idempotent(session):
    """Running twice over the same export must not duplicate primary-key rows."""
    run_import(session, str(FIXTURES))
    run_import(session, str(FIXTURES))

    # PK-keyed tables stay at one row despite the second pass
    assert session.query(PolarTrainingSession).count() == 1
    assert session.query(PolarActivity).count() == 1
    assert session.query(PolarSleep).count() == 1
    assert session.query(PolarAccount).count() == 1
    # Two import-log entries, one per run
    assert session.query(PolarImportLog).count() == 2


def test_run_import_records_errored_file(session, tmp_path):
    """A malformed file is recorded as errored, not fatal to the run."""
    # A training-session file that will blow up (missing identifier)
    (tmp_path / "training-session-bad.json").write_text('{"name": "no id"}')
    # And one good sleep file so the run still imports something
    (tmp_path / "sleep_result_ok.json").write_text(
        '[{"night": "2024-01-15", "evaluation": {}, "sleepResult": {}}]'
    )

    summary = run_import(session, str(tmp_path))
    assert summary["status"] == "complete"
    assert summary["files_errored"] == 1
    assert summary["files_imported"] == 1

    errored = (
        session.query(PolarImportFile).filter(PolarImportFile.status == "errored").one()
    )
    assert errored.filename == "training-session-bad.json"
    assert errored.error_detail
