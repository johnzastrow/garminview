# backend/tests/ingestion/test_mfp_backfill.py
import pytest
from datetime import date
from garminview.models.health import Weight
from garminview.models.supplemental import BodyComposition
from garminview.models.nutrition import MFPMeasurement


def _add_mfp_weight(session, d: date, lbs: float):
    session.add(MFPMeasurement(date=d, name="weight", value=lbs, unit="lbs"))
    session.commit()


def _add_mfp_bf(session, d: date, pct: float):
    session.add(MFPMeasurement(date=d, name="body_fat_pct", value=pct, unit="%"))
    session.commit()


def _add_garmin_weight(session, d: date, kg: float):
    session.add(Weight(date=d, weight_kg=kg, source="garmin"))
    session.commit()


def _add_mfp_weight_row(session, d: date, kg: float):
    session.add(Weight(date=d, weight_kg=kg, source="mfp"))
    session.commit()


def _add_garmin_body_comp(session, d: date, fat_pct: float):
    session.add(BodyComposition(date=d, fat_pct=fat_pct, source="garmin"))
    session.commit()


def test_backfill_inserts_weight_where_no_garmin_row(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_mfp_weight(session, d, 180.0)  # 180 lbs = 81.647 kg

    result = backfill_mfp_to_main(session)

    row = session.get(Weight, d)
    assert row is not None
    assert abs(row.weight_kg - 81.647) < 0.01
    assert row.source == "mfp"
    assert result["weight_rows"] == 1


def test_backfill_skips_garmin_weight(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_garmin_weight(session, d, 75.0)
    _add_mfp_weight(session, d, 180.0)

    result = backfill_mfp_to_main(session)

    row = session.get(Weight, d)
    assert row.weight_kg == 75.0   # Garmin wins
    assert row.source == "garmin"
    assert result["weight_rows"] == 0


def test_backfill_overwrites_stale_mfp_weight(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_mfp_weight_row(session, d, 80.0)   # old MFP row
    _add_mfp_weight(session, d, 180.0)      # new MFP export: 180 lbs = 81.647 kg

    result = backfill_mfp_to_main(session)

    row = session.get(Weight, d)
    assert abs(row.weight_kg - 81.647) < 0.01
    assert result["weight_rows"] == 1


def test_backfill_inserts_body_fat_where_no_garmin_row(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_mfp_bf(session, d, 18.5)

    result = backfill_mfp_to_main(session)

    row = session.get(BodyComposition, d)
    assert row is not None
    assert row.fat_pct == 18.5
    assert row.source == "mfp"
    assert result["body_fat_rows"] == 1


def test_backfill_skips_garmin_body_composition(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    d = date(2024, 1, 15)
    _add_garmin_body_comp(session, d, 20.0)
    _add_mfp_bf(session, d, 18.5)

    result = backfill_mfp_to_main(session)

    row = session.get(BodyComposition, d)
    assert row.fat_pct == 20.0   # Garmin wins
    assert row.source == "garmin"
    assert result["body_fat_rows"] == 0


def test_backfill_no_mfp_data_returns_zeros(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    result = backfill_mfp_to_main(session)
    assert result == {"weight_rows": 0, "body_fat_rows": 0}


def test_lbs_to_kg_conversion(session):
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    from garminview.models.nutrition import MFPMeasurement
    session.add(MFPMeasurement(date=date(2024, 3, 1), name="weight", value=198.0, unit="lbs"))
    session.commit()

    backfill_mfp_to_main(session)

    row = session.get(Weight, date(2024, 3, 1))
    assert abs(row.weight_kg - 89.811) < 0.01
