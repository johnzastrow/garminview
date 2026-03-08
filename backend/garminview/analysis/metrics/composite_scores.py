from typing import Sequence


def calc_readiness_composite(hrv_norm: float | None, rhr_norm: float | None,
                             sleep_score: int | None, body_battery: int | None,
                             stress: int | None) -> float:
    """Weighted composite readiness score 0–100."""
    weights = {"hrv": 0.30, "rhr": 0.20, "sleep": 0.25, "battery": 0.15, "stress": 0.10}
    values = {
        "hrv": (hrv_norm or 50) / 100 * 100,
        "rhr": (rhr_norm or 50) / 100 * 100,
        "sleep": sleep_score or 50,
        "battery": body_battery or 50,
        "stress": max(0, 100 - (stress or 50)),
    }
    score = sum(values[k] * weights[k] for k in weights)
    return round(min(100, max(0, score)), 2)


def calc_overtraining_risk(rhr_zscore: float | None, hrv_status: str | None,
                           acwr: float | None, monotony: float | None) -> int:
    """Overtraining risk score 0 (none) to 3 (high)."""
    risk = 0
    if rhr_zscore is not None and rhr_zscore > 1.5:
        risk += 1
    if hrv_status in ("UNBALANCED", "LOW"):
        risk += 1
    if acwr is not None and acwr > 1.5:
        risk += 1
    if monotony is not None and monotony > 2.0:
        risk += 1
    return min(3, risk)


def calc_wellness_score(steps: int | None, sleep_score: int | None,
                        stress_avg: int | None, body_battery_max: int | None,
                        active_calories: int | None) -> float:
    """Simple daily wellness composite 0–100."""
    step_score = min(100, (steps or 0) / 100)
    sleep_s = sleep_score or 50
    stress_s = max(0, 100 - (stress_avg or 50))
    battery_s = body_battery_max or 50
    cal_s = min(100, (active_calories or 0) / 5)
    return round((step_score + sleep_s + stress_s + battery_s + cal_s) / 5, 2)
