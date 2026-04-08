"""Cross-populate weight and body_composition from mfp_measurements.

Garmin-wins: only writes where no row exists or existing source='mfp'.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from garminview.models.health import Weight
from garminview.models.nutrition import MFPMeasurement
from garminview.models.supplemental import BodyComposition

_LBS_TO_KG = 1 / 2.20462


def backfill_mfp_to_main(session: Session) -> dict[str, int]:
    """Read mfp_measurements and write to weight / body_composition.

    Returns {"weight_rows": N, "body_fat_rows": N}.
    """
    weight_written = 0
    body_fat_written = 0

    mfp_rows = (
        session.query(MFPMeasurement)
        .filter(MFPMeasurement.name.in_(["weight", "body_fat_pct"]))
        .all()
    )

    for row in mfp_rows:
        if row.name == "weight":
            weight_written += _backfill_weight(session, row)
        elif row.name == "body_fat_pct":
            body_fat_written += _backfill_body_fat(session, row)

    session.flush()
    return {"weight_rows": weight_written, "body_fat_rows": body_fat_written}


def _backfill_weight(session: Session, mfp_row: MFPMeasurement) -> int:
    kg = round(mfp_row.value * _LBS_TO_KG, 3)
    existing = session.get(Weight, mfp_row.date)

    if existing is None:
        session.add(Weight(date=mfp_row.date, weight_kg=kg, source="mfp"))
        return 1
    if existing.source == "mfp":
        existing.weight_kg = kg
        return 1
    return 0  # Garmin row — skip


def _backfill_body_fat(session: Session, mfp_row: MFPMeasurement) -> int:
    existing = session.get(BodyComposition, mfp_row.date)

    if existing is None:
        session.add(BodyComposition(
            date=mfp_row.date, fat_pct=mfp_row.value, source="mfp"
        ))
        return 1
    if existing.source == "mfp":
        existing.fat_pct = mfp_row.value
        return 1
    return 0  # Garmin row — skip
