from typing import Sequence


def calc_lbm(weight_kg: float, fat_pct: float) -> float:
    """Lean body mass in kg."""
    return round(weight_kg * (1 - fat_pct / 100), 4)


def calc_ffmi(lbm_kg: float, height_m: float) -> float:
    """Fat-Free Mass Index."""
    if height_m <= 0:
        return 0.0
    return round(lbm_kg / (height_m ** 2), 4)


def calc_weight_velocity(weights: Sequence[float], days: int) -> float | None:
    """Rate of weight change in kg/week over the window."""
    clean = [w for w in weights if w is not None]
    if len(clean) < 2 or days <= 0:
        return None
    change = clean[-1] - clean[0]
    return round(change / days * 7, 4)
