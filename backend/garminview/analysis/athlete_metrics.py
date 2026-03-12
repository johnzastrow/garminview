"""Derived athletic metrics — multiple calculation methods per metric."""
from __future__ import annotations
from datetime import date
from dataclasses import dataclass, field


# ─── Data structures ────────────────────────────────────────────────────────

@dataclass
class MethodValue:
    method: str
    label: str
    value: float | None
    recommended: bool = False
    note: str = ""


@dataclass
class HRZone:
    zone: int
    name: str
    min_bpm: int
    max_bpm: int
    description: str


@dataclass
class AthleteMetrics:
    age: float
    sex: str

    max_hr: int                        # primary value used for zones
    max_hr_source: str
    max_hr_methods: list[MethodValue]

    resting_hr: int | None
    weight_kg: float | None
    height_cm: float | None

    bmr: float | None

    vo2max_estimate: float | None      # primary
    vo2max_methods: list[MethodValue]

    fitness_age: float | None          # primary
    fitness_age_methods: list[MethodValue]

    hr_zones: list[HRZone]
    hr_zones_method: str


# ─── Age ─────────────────────────────────────────────────────────────────────

def calc_age(birth_date: date, on_date: date | None = None) -> float:
    ref = on_date or date.today()
    return (ref - birth_date).days / 365.25


# ─── Max HR ──────────────────────────────────────────────────────────────────

def calc_max_hr_methods(
    age: float,
    sex: str,
    override: int | None = None,
    measured_monitoring: int | None = None,
    measured_activities: int | None = None,
) -> tuple[int, str, list[MethodValue]]:
    """
    Returns (primary_max_hr, source, all_methods).
    Primary selection priority: override > measured_monitoring > tanaka.
    (measured_activities excluded from primary — too prone to sensor spikes.)
    """
    methods: list[MethodValue] = []

    fox     = round(220 - age)
    tanaka  = round(208 - 0.7 * age)
    gellish = round(207 - 0.7 * age)
    # Hulbert 2018 — slightly lower, validated on older adults
    hulbert = round(206.9 - 0.67 * age)
    # Gulati 2010 — female-specific
    gulati  = round(206 - 0.88 * age)

    methods.append(MethodValue("fox",     "Fox (220 − age)",        fox,
        note="Classic formula. Simple but overestimates for older athletes."))
    methods.append(MethodValue("tanaka",  "Tanaka (208 − 0.7 × age)", tanaka,
        note="Most widely validated across ages. Recommended default."))
    methods.append(MethodValue("gellish", "Gellish (207 − 0.7 × age)", gellish,
        note="Similar to Tanaka, validated in large clinical study."))
    methods.append(MethodValue("hulbert", "Hulbert (206.9 − 0.67 × age)", hulbert,
        note="Validated on older adults (40–70). More conservative."))
    if sex.lower() in ("female", "f"):
        methods.append(MethodValue("gulati", "Gulati — women (206 − 0.88 × age)", gulati,
            note="Female-specific formula from large women-only study."))

    if measured_monitoring is not None:
        methods.append(MethodValue("measured_monitoring",
            "Measured — wrist HR sensor",
            measured_monitoring,
            note="Highest HR recorded in continuous monitoring data. Wrist sensors may under-read during intense effort."))

    if measured_activities is not None:
        methods.append(MethodValue("measured_activities",
            "Measured — activity HR (chest strap / optical)",
            measured_activities,
            note="Highest HR recorded across all activities. May include sensor spikes — verify against effort level."))

    if override:
        methods.append(MethodValue("override", "User override", override,
            note="Manually set value — takes priority over all formulas."))

    # Choose primary
    if override:
        primary, source = override, "override"
    elif measured_monitoring and measured_monitoring >= tanaka - 5:
        # Trust monitoring max only if it's plausible (within 20 bpm above Tanaka)
        primary, source = measured_monitoring, "measured_monitoring"
    else:
        primary, source = tanaka, "tanaka"

    # Mark recommended
    for m in methods:
        m.recommended = (m.method == source)

    return primary, source, methods


# ─── BMR ─────────────────────────────────────────────────────────────────────

def calc_bmr(weight_kg: float, height_cm: float, age: float, sex: str) -> float:
    """Mifflin-St Jeor BMR (kcal/day)."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex.lower() in ("male", "m") else base - 161


# ─── VO2max ──────────────────────────────────────────────────────────────────

def calc_vo2max_methods(
    max_hr: int,
    resting_hr: int | None,
    age: float,
    sex: str,
    weight_kg: float | None,
    running_vo2max: float | None = None,   # pre-computed from DB
    garmin_vo2max: float | None = None,    # Garmin FirstBeat estimate from device
) -> tuple[float | None, list[MethodValue]]:
    """Returns (primary_estimate, all_methods).

    Garmin's value is included in the primary average when present — it's derived
    from a more sophisticated algorithm and deserves equal weight to our estimates.
    """
    methods: list[MethodValue] = []
    estimates: list[float] = []

    # Garmin device estimate (FirstBeat algorithm) — shown first for prominence
    if garmin_vo2max is not None:
        methods.append(MethodValue("garmin",
            "Garmin (FirstBeat Technologies)",
            round(garmin_vo2max, 1),
            note="Computed by Garmin's licensed FirstBeat algorithm using GPS pace, heart rate, "
                 "and running dynamics. Calibrates against thousands of lab VO₂max tests. "
                 "Generally the most accurate single estimate for regular runners."))
        estimates.append(garmin_vo2max)

    # Method 1: Uth-Sørensen (needs resting HR)
    if resting_hr:
        uth = round(15 * (max_hr / resting_hr), 1)
        methods.append(MethodValue("uth",
            "Uth-Sørensen (15 × HRmax / HRrest)",
            uth,
            note="Validated formula using HR ratio. Simple but sensitive to resting HR measurement. "
                 "Tends to slightly overestimate in highly trained athletes."))
        estimates.append(uth)

    # Method 2: Running-based ACSM + HR Reserve (pre-computed by endpoint)
    if running_vo2max is not None:
        methods.append(MethodValue("running",
            "Running-based (ACSM + HR Reserve)",
            round(running_vo2max, 1),
            note="Estimated from steady-state running pace and HR. Uses ACSM oxygen cost equation "
                 "(VO₂ = 0.2 × speed_m_min + 3.5) extrapolated via HR Reserve fraction."))
        estimates.append(running_vo2max)

    # Method 3: Scharhag-Rosenberger regression (needs weight, no exercise test)
    if weight_kg and resting_hr:
        sex_val = 1 if sex.lower() in ("male", "m") else 0
        sr = round(54.07 - 0.1938 * weight_kg + 4.47 * sex_val - 0.1453 * resting_hr, 1)
        methods.append(MethodValue("scharhag",
            "Scharhag-Rosenberger regression",
            sr,
            note="Regression model using weight, sex, and resting HR. "
                 "No exercise test required. Valid for 18–65-year-olds."))
        estimates.append(sr)

    # Method 4: Population age norm (contextual reference, not included in primary average)
    avg_norm = round((72.3 if sex.lower() in ("male", "m") else 65.1) - 0.62 * age, 1)
    methods.append(MethodValue("age_norm",
        "Age-group average (population norm)",
        avg_norm,
        note=f"Average VO₂max for a {round(age)}-year-old {sex}. "
              "Included for context — not used in the primary estimate."))

    primary = round(sum(e for e in estimates if e > 0) / len(estimates), 1) if estimates else None
    return primary, methods


# ─── Fitness Age ─────────────────────────────────────────────────────────────

def calc_fitness_age_methods(
    vo2max: float,
    age: float,
    sex: str,
    resting_hr: int | None = None,
    weight_kg: float | None = None,
    height_cm: float | None = None,
    garmin_vo2max: float | None = None,
) -> tuple[float | None, list[MethodValue]]:
    """Returns (primary_fitness_age, all_methods)."""
    methods: list[MethodValue] = []

    # Method 1: Cooper Institute — invert VO2max age norms
    # Male: VO2max ≈ 72.3 - 0.62*age  →  age = (72.3 - VO2max) / 0.62
    # Female: VO2max ≈ 65.1 - 0.58*age
    if sex.lower() in ("male", "m"):
        cooper_age = round((72.3 - vo2max) / 0.62, 1)
    else:
        cooper_age = round((65.1 - vo2max) / 0.58, 1)
    cooper_age = max(18.0, min(80.0, cooper_age))
    methods.append(MethodValue("cooper",
        "Cooper Institute (VO2max age norms)",
        cooper_age,
        recommended=True,
        note="Inverts VO2max population age norms to find equivalent biological age. "
             "Values below chronological age indicate above-average fitness."))

    # Method 2: Norwegian CERG model
    # Simplified form of the CERG fitness age calculator
    # Uses: sex, age, waist circumference, resting HR, exercise frequency, exercise intensity
    # Since we don't have waist or exercise frequency, use available variables
    # Approximate: fitness_age = 88.7 - 0.68*VO2max (from CERG regression, male)
    #              fitness_age = 87.4 - 0.69*VO2max (female)
    if sex.lower() in ("male", "m"):
        cerg_age = round(88.7 - 0.68 * vo2max, 1)
    else:
        cerg_age = round(87.4 - 0.69 * vo2max, 1)
    cerg_age = max(18.0, min(80.0, cerg_age))
    methods.append(MethodValue("cerg",
        "Norwegian CERG (simplified)",
        cerg_age,
        note="Based on the HUNT Fitness Study (Nes et al. 2011). Full CERG uses 5 variables "
             "(waist, exercise frequency/intensity, resting HR). This simplified version uses only VO2max."))

    # Method 3: VO2max percentile classification
    # Male VO2max percentiles by age (50–59) from ACSM guidelines
    MALE_PERCENTILES = {
        "20-29": [(28, "Very Poor"), (38, "Poor"), (44, "Fair"), (51, "Good"), (57, "Excellent"), (999, "Superior")],
        "30-39": [(27, "Very Poor"), (37, "Poor"), (42, "Fair"), (49, "Good"), (55, "Excellent"), (999, "Superior")],
        "40-49": [(25, "Very Poor"), (35, "Poor"), (40, "Fair"), (46, "Good"), (52, "Excellent"), (999, "Superior")],
        "50-59": [(21, "Very Poor"), (31, "Poor"), (37, "Fair"), (43, "Good"), (49, "Excellent"), (999, "Superior")],
        "60-69": [(18, "Very Poor"), (26, "Poor"), (32, "Fair"), (38, "Good"), (44, "Excellent"), (999, "Superior")],
    }
    FEMALE_PERCENTILES = {
        "20-29": [(24, "Very Poor"), (31, "Poor"), (37, "Fair"), (44, "Good"), (50, "Excellent"), (999, "Superior")],
        "30-39": [(20, "Very Poor"), (27, "Poor"), (33, "Fair"), (39, "Good"), (45, "Excellent"), (999, "Superior")],
        "40-49": [(17, "Very Poor"), (24, "Poor"), (29, "Fair"), (35, "Good"), (41, "Excellent"), (999, "Superior")],
        "50-59": [(15, "Very Poor"), (21, "Poor"), (27, "Fair"), (32, "Good"), (38, "Excellent"), (999, "Superior")],
        "60-69": [(13, "Very Poor"), (18, "Poor"), (23, "Fair"), (28, "Good"), (35, "Excellent"), (999, "Superior")],
    }

    age_bracket = "50-59" if 50 <= age < 60 else (
        "20-29" if age < 30 else "30-39" if age < 40 else
        "40-49" if age < 50 else "60-69"
    )
    table = MALE_PERCENTILES if sex.lower() in ("male", "m") else FEMALE_PERCENTILES
    category = "Superior"
    for threshold, cat in table.get(age_bracket, []):
        if vo2max <= threshold:
            category = cat
            break

    methods.append(MethodValue("percentile",
        f"ACSM percentile classification ({age_bracket})",
        None,
        note=f"Rating: **{category}** for a {round(age)}-year-old {sex} "
             f"(VO2max = {vo2max} ml/kg/min). "
             "Based on ACSM Guidelines for Exercise Testing and Prescription."))

    # Garmin-derived fitness age: apply Cooper norms to Garmin's VO2max
    if garmin_vo2max is not None:
        if sex.lower() in ("male", "m"):
            g_cooper = round((72.3 - garmin_vo2max) / 0.62, 1)
        else:
            g_cooper = round((65.1 - garmin_vo2max) / 0.58, 1)
        g_cooper = max(18.0, min(80.0, g_cooper))
        methods.append(MethodValue("garmin_cooper",
            "Cooper norms (Garmin VO₂max input)",
            g_cooper,
            note=f"Cooper Institute age norms applied to Garmin's VO₂max of {garmin_vo2max} ml/kg/min. "
                 "Shows what fitness age would be if we trust Garmin's device estimate as ground truth."))

    primary = cooper_age
    return primary, methods


# ─── HR Zones ────────────────────────────────────────────────────────────────

def calc_hr_zones(max_hr: int, resting_hr: int | None = None) -> tuple[list[HRZone], str]:
    ZONE_DEFS = [
        (1, "Recovery",      0.50, 0.60, "Easy recovery — sustainable all day, conversational pace"),
        (2, "Aerobic Base",  0.60, 0.70, "Aerobic base building — builds aerobic endurance and fat metabolism"),
        (3, "Tempo",         0.70, 0.80, "Tempo / moderate intensity — comfortably hard, builds lactate threshold"),
        (4, "Threshold",     0.80, 0.90, "Lactate threshold — hard effort, improves speed endurance"),
        (5, "VO₂max",        0.90, 1.00, "Max effort — anaerobic, builds peak aerobic capacity"),
    ]
    if resting_hr:
        hrr = max_hr - resting_hr
        zones = [HRZone(z, n, round(resting_hr + lo*hrr), round(resting_hr + hi*hrr), d)
                 for z, n, lo, hi, d in ZONE_DEFS]
        return zones, "karvonen"
    zones = [HRZone(z, n, round(lo*max_hr), round(hi*max_hr), d)
             for z, n, lo, hi, d in ZONE_DEFS]
    return zones, "percent_max"


# ─── Top-level ───────────────────────────────────────────────────────────────

def compute_athlete_metrics(
    profile,
    measured_max_hr_monitoring: int | None = None,
    measured_max_hr_activities: int | None = None,
    running_vo2max: float | None = None,
    garmin_vo2max: float | None = None,
) -> "AthleteMetrics | None":
    if not profile or not profile.birth_date:
        return None

    age  = calc_age(profile.birth_date)
    sex  = profile.sex or "male"
    rhr  = profile.resting_hr
    wt   = profile.weight_kg
    ht   = profile.height_cm

    max_hr, max_hr_source, max_hr_methods = calc_max_hr_methods(
        age, sex,
        override=profile.max_hr_override,
        measured_monitoring=measured_max_hr_monitoring,
        measured_activities=measured_max_hr_activities,
    )

    bmr = round(calc_bmr(wt, ht, age, sex)) if wt and ht else None

    vo2max_primary, vo2max_methods = calc_vo2max_methods(
        max_hr, rhr, age, sex, wt,
        running_vo2max=running_vo2max,
        garmin_vo2max=garmin_vo2max,
    )

    fitness_age_primary = None
    fitness_age_methods_list = []
    if vo2max_primary:
        fitness_age_primary, fitness_age_methods_list = calc_fitness_age_methods(
            vo2max_primary, age, sex, rhr, wt, ht,
            garmin_vo2max=garmin_vo2max,
        )

    zones, method = calc_hr_zones(max_hr, rhr)

    return AthleteMetrics(
        age=round(age, 1),
        sex=sex,
        max_hr=max_hr,
        max_hr_source=max_hr_source,
        max_hr_methods=max_hr_methods,
        resting_hr=rhr,
        weight_kg=wt,
        height_cm=ht,
        bmr=bmr,
        vo2max_estimate=vo2max_primary,
        vo2max_methods=vo2max_methods,
        fitness_age=fitness_age_primary,
        fitness_age_methods=fitness_age_methods_list,
        hr_zones=zones,
        hr_zones_method=method,
    )
