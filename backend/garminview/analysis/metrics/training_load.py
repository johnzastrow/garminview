import math
from typing import Sequence


def calc_trimp(duration_min: float, avg_hr: int, max_hr: int,
               resting_hr: int = 50) -> float:
    """Banister (1991) TRIMP."""
    if max_hr <= resting_hr or avg_hr <= resting_hr:
        return 0.0
    hr_fraction = (avg_hr - resting_hr) / (max_hr - resting_hr)
    return duration_min * hr_fraction * math.exp(1.92 * hr_fraction)


def calc_ewma_series(values: Sequence[float | None], tau: int) -> list[float]:
    """Exponentially weighted moving average with time constant tau (days)."""
    result = []
    ewma = 0.0
    for v in values:
        if v is None:
            v = 0.0
        ewma = ewma + (v - ewma) / tau
        result.append(round(ewma, 4))
    return result


def calc_acwr(atl: float, ctl: float) -> float | None:
    """Acute:Chronic Workload Ratio. None if CTL is zero."""
    if ctl == 0:
        return None
    return round(atl / ctl, 4)


def calc_monotony(daily_loads: Sequence[float]) -> float | None:
    """Foster (1998) monotony = mean / SD of 7-day window."""
    import statistics
    if len(daily_loads) < 2:
        return None
    mean = statistics.mean(daily_loads)
    stdev = statistics.stdev(daily_loads)
    if stdev == 0:
        return None
    return round(mean / stdev, 4)


def calc_strain(weekly_load: float, monotony: float) -> float:
    return round(weekly_load * monotony, 4)
