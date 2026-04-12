"""Polar Flow GDPR export importer — orchestrates scan, parse, upsert, and logging."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from garminview.ingestion.polar.scanner import scan_directory
from garminview.models.polar import (
    Polar247OHR,
    PolarAccount,
    PolarActivity,
    PolarActivityMetSource,
    PolarActivityPhysicalInfo,
    PolarActivitySample,
    PolarCalendarItem,
    PolarDevice,
    PolarExercise,
    PolarExerciseLap,
    PolarExerciseRoute,
    PolarExerciseSample,
    PolarExerciseStatistic,
    PolarExerciseZone,
    PolarFavouriteTarget,
    PolarFitnessTest,
    PolarImportFile,
    PolarImportLog,
    PolarPlannedRoute,
    PolarProgram,
    PolarSleep,
    PolarSleepState,
    PolarSportProfile,
    PolarTrainingSession,
    PolarTrainingTarget,
    PolarTrainingTargetPhase,
)

_log = logging.getLogger(__name__)


def _upsert_row(session: Session, model, data: dict, pk_cols: list[str]) -> None:
    """Upsert a single row using dialect-aware INSERT ... ON CONFLICT."""
    dialect = session.bind.dialect.name
    non_pk = [c for c in data if c not in pk_cols]

    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as _ins
        stmt = _ins(model).values([data])
        if non_pk:
            stmt = stmt.on_conflict_do_update(
                index_elements=pk_cols,
                set_={c: getattr(stmt.excluded, c) for c in non_pk},
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
    else:
        from sqlalchemy.dialects.mysql import insert as _ins
        stmt = _ins(model).values([data])
        if non_pk:
            stmt = stmt.on_duplicate_key_update(**{c: stmt.inserted[c] for c in non_pk})
    session.execute(stmt)


def _upsert_batch(session: Session, model, rows: list[dict], pk_cols: list[str]) -> None:
    """Upsert a batch of rows."""
    if not rows:
        return
    dialect = session.bind.dialect.name
    non_pk = [c for c in rows[0] if c not in pk_cols]
    batch_size = 500

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as _ins
            stmt = _ins(model).values(batch)
            if non_pk:
                stmt = stmt.on_conflict_do_update(
                    index_elements=pk_cols,
                    set_={c: getattr(stmt.excluded, c) for c in non_pk},
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
        else:
            from sqlalchemy.dialects.mysql import insert as _ins
            stmt = _ins(model).values(batch)
            if non_pk:
                stmt = stmt.on_duplicate_key_update(**{c: stmt.inserted[c] for c in non_pk})
        session.execute(stmt)


def _bulk_insert(session: Session, model, rows: list[dict]) -> None:
    """Insert rows (for autoincrement-PK tables where we delete-then-reinsert)."""
    if not rows:
        return
    dialect = session.bind.dialect.name
    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as _ins
        else:
            from sqlalchemy.dialects.mysql import insert as _ins
        session.execute(_ins(model).values(batch))


def _delete_by(session: Session, model, col_name: str, value) -> None:
    """Delete all rows matching a column value."""
    col = getattr(model, col_name)
    session.query(model).filter(col == value).delete(synchronize_session=False)


def _record_file(
    session: Session,
    import_id: int,
    filename: str,
    file_type: str,
    file_size: int,
    status: str,
    records: int = 0,
    error: str | None = None,
) -> None:
    """Record a processed file in polar_import_files."""
    session.add(PolarImportFile(
        import_id=import_id,
        filename=filename,
        file_type=file_type,
        file_size_bytes=file_size,
        status=status,
        records_upserted=records,
        error_detail=error,
        processed_at=datetime.now(timezone.utc),
    ))


def _import_training_sessions(
    session: Session, files: list[Path], import_id: int, now: datetime,
) -> tuple[int, int, int]:
    """Import training-session files. Returns (imported, skipped, errored)."""
    from garminview.ingestion.polar.parsers.training_session import parse_training_session

    imported = skipped = errored = 0
    for fp in files:
        try:
            result = parse_training_session(fp, now)
            sid = result["session"]["session_id"]

            # Upsert session
            _upsert_row(session, PolarTrainingSession, result["session"], ["session_id"])

            # Child tables: delete existing children then reinsert
            for ex in result["exercises"]:
                _upsert_row(session, PolarExercise, ex, ["exercise_id"])
                ex_id = ex["exercise_id"]

                # Delete old child rows for this exercise
                _delete_by(session, PolarExerciseStatistic, "exercise_id", ex_id)
                _delete_by(session, PolarExerciseZone, "exercise_id", ex_id)
                _delete_by(session, PolarExerciseLap, "exercise_id", ex_id)

            # Bulk insert child rows
            _bulk_insert(session, PolarExerciseStatistic, result["statistics"])
            _bulk_insert(session, PolarExerciseZone, result["zones"])
            _bulk_insert(session, PolarExerciseLap, result["laps"])

            # Samples and routes: upsert on composite unique
            for s in result["samples"]:
                _upsert_row(session, PolarExerciseSample, s, ["exercise_id", "sample_type"])
            for r in result["routes"]:
                _upsert_row(session, PolarExerciseRoute, r, ["exercise_id", "route_type"])

            count = (1 + len(result["exercises"]) + len(result["statistics"])
                     + len(result["zones"]) + len(result["laps"])
                     + len(result["samples"]) + len(result["routes"]))
            _record_file(session, import_id, fp.name, "training-session", fp.stat().st_size, "imported", count)
            imported += 1

        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, "training-session", fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    return imported, skipped, errored


def _import_activities(
    session: Session, files: list[Path], import_id: int, now: datetime,
) -> tuple[int, int, int]:
    from garminview.ingestion.polar.parsers.activity import parse_activity

    imported = skipped = errored = 0
    for fp in files:
        try:
            result = parse_activity(fp, now)
            d = result["activity"]["date"]

            _upsert_row(session, PolarActivity, result["activity"], ["date"])

            # Samples: upsert on (date, sample_type)
            for s in result["samples"]:
                _upsert_row(session, PolarActivitySample, s, ["date", "sample_type"])

            # Met sources: delete + reinsert
            _delete_by(session, PolarActivityMetSource, "date", d)
            _bulk_insert(session, PolarActivityMetSource, result["met_sources"])

            # Physical info
            if result["physical_info"]:
                _upsert_row(session, PolarActivityPhysicalInfo, result["physical_info"], ["date"])

            count = 1 + len(result["samples"]) + len(result["met_sources"]) + (1 if result["physical_info"] else 0)
            _record_file(session, import_id, fp.name, "activity", fp.stat().st_size, "imported", count)
            imported += 1

        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, "activity", fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    return imported, skipped, errored


def _import_sleep(
    session: Session, files: list[Path], import_id: int, now: datetime,
) -> tuple[int, int, int]:
    from garminview.ingestion.polar.parsers.sleep import parse_sleep

    imported = skipped = errored = 0
    for fp in files:
        try:
            nights = parse_sleep(fp, now)
            total_records = 0
            for entry in nights:
                _upsert_row(session, PolarSleep, entry["sleep"], ["night"])
                night = entry["sleep"]["night"]
                _delete_by(session, PolarSleepState, "night", night)
                _bulk_insert(session, PolarSleepState, entry["states"])
                total_records += 1 + len(entry["states"])

            _record_file(session, import_id, fp.name, "sleep", fp.stat().st_size, "imported", total_records)
            imported += 1
        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, "sleep", fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    return imported, skipped, errored


def _import_247ohr(
    session: Session, files: list[Path], import_id: int, now: datetime,
) -> tuple[int, int, int]:
    from garminview.ingestion.polar.parsers.ohr import parse_247ohr

    imported = skipped = errored = 0
    for fp in files:
        try:
            rows = parse_247ohr(fp, now)
            for row in rows:
                _upsert_row(session, Polar247OHR, row, ["date", "device_id"])
            _record_file(session, import_id, fp.name, "247ohr", fp.stat().st_size, "imported", len(rows))
            imported += 1
        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, "247ohr", fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    return imported, skipped, errored


def _import_fitness_tests(
    session: Session, files: list[Path], import_id: int, now: datetime,
) -> tuple[int, int, int]:
    from garminview.ingestion.polar.parsers.fitness_test import parse_fitness_test

    imported = skipped = errored = 0
    for fp in files:
        try:
            row = parse_fitness_test(fp, now)
            # Dedup by start_time: check if already exists
            existing = session.query(PolarFitnessTest).filter(
                PolarFitnessTest.start_time == row["start_time"]
            ).first()
            if existing:
                for k, v in row.items():
                    setattr(existing, k, v)
            else:
                session.add(PolarFitnessTest(**row))
            _record_file(session, import_id, fp.name, "fitness-test", fp.stat().st_size, "imported", 1)
            imported += 1
        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, "fitness-test", fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    return imported, skipped, errored


def _import_training_targets(
    session: Session, files: list[Path], import_id: int, now: datetime,
) -> tuple[int, int, int]:
    from garminview.ingestion.polar.parsers.training_target import parse_training_target

    imported = skipped = errored = 0
    for fp in files:
        try:
            result = parse_training_target(fp, now)
            t = result["target"]

            # Dedup by (start_time, name)
            existing = session.query(PolarTrainingTarget).filter(
                PolarTrainingTarget.start_time == t["start_time"],
                PolarTrainingTarget.name == t["name"],
            ).first()

            if existing:
                for k, v in t.items():
                    setattr(existing, k, v)
                target_id = existing.id
                session.flush()
            else:
                obj = PolarTrainingTarget(**t)
                session.add(obj)
                session.flush()
                target_id = obj.id

            # Delete old phases and reinsert
            _delete_by(session, PolarTrainingTargetPhase, "target_id", target_id)
            for phase in result["phases"]:
                phase["target_id"] = target_id
            _bulk_insert(session, PolarTrainingTargetPhase, result["phases"])

            _record_file(session, import_id, fp.name, "training-target", fp.stat().st_size, "imported",
                         1 + len(result["phases"]))
            imported += 1
        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, "training-target", fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    return imported, skipped, errored


def _import_account(
    session: Session,
    data_files: list[Path],
    profile_files: list[Path],
    import_id: int,
    now: datetime,
) -> tuple[int, int, int]:
    from garminview.ingestion.polar.parsers.account import parse_account_data, parse_account_profile

    imported = errored = 0

    # Merge account-data and account-profile into one row
    merged: dict = {}

    for fp in data_files:
        try:
            d = parse_account_data(fp, now)
            merged.update(d)
            _record_file(session, import_id, fp.name, "account-data", fp.stat().st_size, "imported", 1)
            imported += 1
        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, "account-data", fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    for fp in profile_files:
        try:
            d = parse_account_profile(fp, now)
            merged.update(d)
            _record_file(session, import_id, fp.name, "account-profile", fp.stat().st_size, "imported", 1)
            imported += 1
        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, "account-profile", fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    if merged and merged.get("user_id") is not None:
        _upsert_row(session, PolarAccount, merged, ["user_id"])

    return imported, 0, errored


def _import_calendar(
    session: Session, files: list[Path], import_id: int, now: datetime,
) -> tuple[int, int, int]:
    from garminview.ingestion.polar.parsers.calendar import parse_calendar

    imported = skipped = errored = 0
    for fp in files:
        try:
            rows = parse_calendar(fp, now)
            # Delete all existing calendar items (single file, full replace)
            session.query(PolarCalendarItem).delete(synchronize_session=False)
            _bulk_insert(session, PolarCalendarItem, rows)
            _record_file(session, import_id, fp.name, "calendar", fp.stat().st_size, "imported", len(rows))
            imported += 1
        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, "calendar", fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    return imported, skipped, errored


def _import_generic(
    session: Session,
    model,
    file_type: str,
    files: list[Path],
    import_id: int,
    now: datetime,
    parser_fn,
) -> tuple[int, int, int]:
    imported = skipped = errored = 0
    for fp in files:
        try:
            result = parser_fn(fp, now)
            if isinstance(result, list):
                # Delete existing for this source file, then insert
                session.query(model).filter(model.source_file == fp.name).delete(synchronize_session=False)
                for row in result:
                    session.add(model(**row))
                count = len(result)
            else:
                # Single row — delete by source_file then insert
                session.query(model).filter(model.source_file == fp.name).delete(synchronize_session=False)
                session.add(model(**result))
                count = 1
            _record_file(session, import_id, fp.name, file_type, fp.stat().st_size, "imported", count)
            imported += 1
        except Exception as exc:
            _log.warning("Error parsing %s: %s", fp.name, exc)
            _record_file(session, import_id, fp.name, file_type, fp.stat().st_size, "errored", error=str(exc))
            errored += 1

    return imported, skipped, errored


def run_import(session: Session, source_path: str) -> dict:
    """Run a full Polar Flow GDPR export import.

    Args:
        session: SQLAlchemy session
        source_path: Path to the polar-user-data-export directory

    Returns:
        Summary dict with counts and status.
    """
    now = datetime.now(timezone.utc)

    # Create import log entry
    log_entry = PolarImportLog(
        started_at=now,
        source_path=source_path,
        status="running",
    )
    session.add(log_entry)
    session.flush()
    import_id = log_entry.id

    try:
        file_groups = scan_directory(source_path)
        total_files = sum(len(v) for v in file_groups.values())
        log_entry.files_found = total_files

        total_imported = 0
        total_skipped = 0
        total_errored = 0

        # Process each file type
        type_handlers = []

        if "training-session" in file_groups:
            i, s, e = _import_training_sessions(session, file_groups["training-session"], import_id, now)
            total_imported += i; total_skipped += s; total_errored += e
            session.flush()
            _log.info("Training sessions: %d imported, %d skipped, %d errors", i, s, e)

        if "activity" in file_groups:
            i, s, e = _import_activities(session, file_groups["activity"], import_id, now)
            total_imported += i; total_skipped += s; total_errored += e
            session.flush()
            _log.info("Activities: %d imported, %d skipped, %d errors", i, s, e)

        if "sleep" in file_groups:
            i, s, e = _import_sleep(session, file_groups["sleep"], import_id, now)
            total_imported += i; total_skipped += s; total_errored += e
            session.flush()
            _log.info("Sleep: %d imported, %d skipped, %d errors", i, s, e)

        if "247ohr" in file_groups:
            i, s, e = _import_247ohr(session, file_groups["247ohr"], import_id, now)
            total_imported += i; total_skipped += s; total_errored += e
            session.flush()
            _log.info("247ohr: %d imported, %d skipped, %d errors", i, s, e)

        if "fitness-test" in file_groups:
            i, s, e = _import_fitness_tests(session, file_groups["fitness-test"], import_id, now)
            total_imported += i; total_skipped += s; total_errored += e
            session.flush()

        if "training-target" in file_groups:
            i, s, e = _import_training_targets(session, file_groups["training-target"], import_id, now)
            total_imported += i; total_skipped += s; total_errored += e
            session.flush()

        # Account: merge account-data + account-profile
        account_data = file_groups.get("account-data", [])
        account_profile = file_groups.get("account-profile", [])
        if account_data or account_profile:
            i, s, e = _import_account(session, account_data, account_profile, import_id, now)
            total_imported += i; total_skipped += s; total_errored += e
            session.flush()

        if "calendar" in file_groups:
            i, s, e = _import_calendar(session, file_groups["calendar"], import_id, now)
            total_imported += i; total_skipped += s; total_errored += e
            session.flush()

        # Generic blob tables
        from garminview.ingestion.polar.parsers.generic import (
            parse_sport_profiles, parse_generic_blob, parse_programs,
        )

        generic_handlers = [
            ("sport-profiles", PolarSportProfile, parse_sport_profiles),
            ("devices", PolarDevice, parse_generic_blob),
            ("programs", PolarProgram, parse_programs),
            ("planned-route", PolarPlannedRoute, parse_generic_blob),
            ("favourite-targets", PolarFavouriteTarget, parse_generic_blob),
        ]
        for file_type, model, parser_fn in generic_handlers:
            if file_type in file_groups:
                i, s, e = _import_generic(session, model, file_type, file_groups[file_type], import_id, now, parser_fn)
                total_imported += i; total_skipped += s; total_errored += e
                session.flush()

        # Update import log
        log_entry.completed_at = datetime.now(timezone.utc)
        log_entry.files_imported = total_imported
        log_entry.files_skipped = total_skipped
        log_entry.files_errored = total_errored
        log_entry.status = "complete"
        session.commit()

        summary = {
            "import_id": import_id,
            "status": "complete",
            "files_found": total_files,
            "files_imported": total_imported,
            "files_skipped": total_skipped,
            "files_errored": total_errored,
            "file_types": {k: len(v) for k, v in file_groups.items()},
        }
        _log.info("Polar import complete: %s", summary)
        return summary

    except Exception as exc:
        log_entry.completed_at = datetime.now(timezone.utc)
        log_entry.status = "failed"
        log_entry.error_detail = str(exc)
        session.commit()
        _log.error("Polar import failed: %s", exc)
        raise
