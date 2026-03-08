from typing import Sequence


def calc_rhr_zscore(rhr: float, mean_30d: float, std_30d: float) -> float | None:
    if std_30d == 0:
        return None
    return round((rhr - mean_30d) / std_30d, 4)


def calc_hrv_cv(hrv_series: Sequence[float]) -> float | None:
    """Coefficient of variation of HRV series."""
    import statistics
    clean = [v for v in hrv_series if v is not None]
    if len(clean) < 2:
        return None
    mean = statistics.mean(clean)
    if mean == 0:
        return None
    return round(statistics.stdev(clean) / mean * 100, 4)


def calc_heart_rate_recovery(hr_at_end: int, hr_1min_post: int) -> int:
    """HRR-1: drop in HR 1 minute post-exercise. Higher = better cardiovascular fitness."""
    return hr_at_end - hr_1min_post


def calc_cardiac_drift(first_half_ef: float, second_half_ef: float) -> float:
    """Cardiac drift: % change in efficiency factor between halves of activity."""
    if first_half_ef == 0:
        return 0.0
    return round((second_half_ef - first_half_ef) / first_half_ef * 100, 4)
