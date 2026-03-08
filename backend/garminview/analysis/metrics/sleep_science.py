import statistics
from typing import Sequence


def calc_sleep_efficiency(total_sleep_min: float, awake_min: float,
                          time_in_bed_min: float) -> float | None:
    if time_in_bed_min <= 0:
        return None
    return round(total_sleep_min / time_in_bed_min * 100, 2)


def calc_sleep_debt(actual_hours: Sequence[float],
                    target_hours: float = 8.0) -> float:
    """Cumulative debt in hours over the provided window."""
    return round(sum(max(0, target_hours - h) for h in actual_hours), 2)


def calc_social_jet_lag(weekday_midpoints: Sequence[float],
                        weekend_midpoints: Sequence[float]) -> float | None:
    """Absolute difference between mean weekend and weekday sleep midpoints (hours)."""
    if not weekday_midpoints or not weekend_midpoints:
        return None
    return round(abs(statistics.mean(weekend_midpoints) -
                     statistics.mean(weekday_midpoints)), 2)


def calc_sleep_regularity_index(sleep_states: Sequence[Sequence[int]]) -> float | None:
    """
    SRI (Phillips 2017): probability of same state (0=awake, 1=asleep)
    at same time across consecutive day pairs.
    sleep_states: list of daily binary arrays (1=asleep, 0=awake), same length.
    """
    if len(sleep_states) < 2:
        return None
    matches = 0
    total = 0
    for i in range(len(sleep_states) - 1):
        day_a, day_b = sleep_states[i], sleep_states[i + 1]
        for a, b in zip(day_a, day_b):
            if a == b:
                matches += 1
            total += 1
    if total == 0:
        return None
    return round(matches / total * 100, 2)
