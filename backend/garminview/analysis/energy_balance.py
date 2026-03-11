"""
Energy balance: MFP calories_in vs Garmin calories_out (active + BMR).
Coverage is validated here; actual balance computation happens at query time
in the /nutrition/energy-balance API endpoint.
"""
from sqlalchemy.orm import Session

from garminview.models.nutrition import MFPDailyNutrition
from garminview.models.health import DailySummary
from garminview.core.logging import get_logger

log = get_logger(__name__)


class EnergyBalanceAnalysis:
    def __init__(self, session: Session):
        self._session = session

    def run(self) -> None:
        nutrition = {r.date: r for r in self._session.query(MFPDailyNutrition).all()}
        if not nutrition:
            return
        summaries = {r.date: r for r in self._session.query(DailySummary).all()}
        log.info("energy_balance_computing", nutrition_days=len(nutrition))
        matched = sum(1 for d in nutrition if d in summaries)
        log.info(
            "energy_balance_coverage",
            nutrition_days=len(nutrition),
            garmin_days=len(summaries),
            matched_days=matched,
        )
