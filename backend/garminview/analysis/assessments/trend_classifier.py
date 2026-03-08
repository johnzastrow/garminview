from dataclasses import dataclass
from datetime import date
from typing import Sequence
import numpy as np
from scipy import stats


@dataclass
class TrendResult:
    direction: str  # improving / stable / declining / insufficient_data
    slope: float | None = None
    r_squared: float | None = None
    p_value: float | None = None


def classify_trend(dates: Sequence[date], values: Sequence[float],
                   lower_is_better: bool = False,
                   min_samples: int = 7) -> TrendResult:
    clean = [(d, v) for d, v in zip(dates, values) if v is not None]
    if len(clean) < min_samples:
        return TrendResult(direction="insufficient_data")

    xs = np.array([(d - clean[0][0]).days for d, _ in clean], dtype=float)
    ys = np.array([v for _, v in clean], dtype=float)
    slope, intercept, r, p, se = stats.linregress(xs, ys)

    if p > 0.05:
        return TrendResult(direction="stable", slope=slope, r_squared=r**2, p_value=p)

    if (slope < 0 and lower_is_better) or (slope > 0 and not lower_is_better):
        direction = "improving"
    else:
        direction = "declining"

    return TrendResult(direction=direction, slope=round(slope, 6),
                       r_squared=round(r**2, 4), p_value=round(p, 6))
