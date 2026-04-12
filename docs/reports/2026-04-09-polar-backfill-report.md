# Polar → Core Tables: Transformation & Loading Report

**Generated:** 2026-04-09  
**Source:** 3,271 Polar Flow GDPR export files across 26 staging tables

## Summary

| Target Table | Polar Rows | Insert | Update | Skip (Garmin wins) |
|---|---:|---:|---:|---:|
| activities | 820 | 820 | 0 | 0 |
| sleep | 647 | 0 | 647 | 0 |
| weight | — | — | — | — |
| resting_heart_rate | 703 | 701 | 0 | 2 |
| vo2max | 703 | 703 | 0 | 0 |

**Weight excluded:** Polar export contains only 4 distinct weight values (70.0–73.0 kg) across 2,357 rows — these are user profile settings, not scale measurements. No backfill performed.

## 1. Activities

**Polar training sessions total:** 820  
**Garmin activities total:** 1,004 (2021-03-29 to 2026-03-15)

| Category | Count | Action |
|---|---:|---|
| Polar sessions BEFORE any Garmin activity | 675 | INSERT (no collision possible) |
| Polar sessions in overlap period, no ±5 min match | 145 | INSERT (gap fill) |
| Polar sessions colliding with Garmin (±5 min) | 0 | SKIP |
| **Total insertable** | **820** | |

**Zero collisions.** Polar was used for gym workouts (circuit training, bootcamp, spinning), while Garmin picked up in 2021 primarily for walking and HIIT. The two devices tracked different activity types with no temporal overlap.

### Sport ID Mapping

| sport_id | Count | Polar Name | → Core sport |
|---:|---:|---|---|
| 20 | 291 | Circuit training / None | `hiit` |
| 58 | 275 | Bootcamp | `hiit` |
| 1 | 69 | Running / None | `running` |
| 2 | 53 | Cycling | `cycling` |
| 83 | 30 | Other indoor | `other` |
| 118 | 28 | Spinning | `indoor_cycling` |
| 17 | 25 | Treadmill runn. | `treadmill_running` |
| 103 | 23 | Pool swimm. / Pool swimming | `lap_swimming` |
| 16 | 8 | Other outdoor | `other` |
| 126 | 4 | Core | `strength_training` |
| 15 | 4 | Strength tr. | `strength_training` |
| 18 | 2 | Indoor cycling | `indoor_cycling` |
| 34 | 2 | HIIT / None | `hiit` |
| 111 | 1 | Mobility (dyn.) | `yoga` |
| 113 | 1 | Backcountry skiing | `backcountry_skiing` |
| 117 | 1 | Indoor rowing | `indoor_rowing` |
| 55 | 1 | Cross-trainer | `fitness_equipment` |
| 127 | 1 | Mobility (stat.) | `yoga` |
| 11 | 1 | Other outdoor | `other` |

**HR statistics coverage:** 664 / 820 exercises have heart rate data from `polar_exercise_statistics`.

Note: Some sessions have `name="None"` — sport mapping falls back to sport_id lookup.

## 2. Sleep

**Polar sleep nights total:** 647 (2019-02-04 to 2022-06-13)

| Category | Count | Action |
|---|---:|---|
| Garmin row exists with REAL sleep data | 0 | SKIP |
| Garmin row exists but EMPTY (total_sleep_min=NULL) | 647 | UPDATE |
| No Garmin row | 0 | INSERT |
| **Total writable** | **647** | |

**Zero conflicts.** Every Polar sleep night has a corresponding Garmin row, but all 1,226 Garmin sleep rows in this period have `total_sleep_min=NULL`. Polar data fills a complete gap.

**Hypnogram data:** 33,291 state changes across 647 nights (avg 51 state changes/night)  
Sleep states: WAKE, NONREM1, NONREM2, NONREM3, REM

### Sample Data (first 5 nights)

| Night | Polar Duration | Efficiency % | Garmin total_sleep_min | Garmin score |
|---|---|---:|---|---|
| 2019-02-04 | PT6H53M30S | 91.7 | NULL | NULL |
| 2019-02-06 | PT6H49M | 94.5 | NULL | NULL |
| 2019-02-07 | PT6H48M | 95.6 | NULL | NULL |
| 2019-02-08 | PT6H20M | 95.5 | NULL | NULL |
| 2019-02-10 | PT8H38M | 92.8 | NULL | NULL |

### Transformation Notes

- `asleep_duration` (ISO 8601 like `PT6H53M30S`) → `total_sleep_min` (integer minutes)
- Sleep stage durations calculated from hypnogram: each state's duration = next state's offset − current offset
- Sleep score approximated from `efficiency_pct`: round to nearest integer (0–100 scale)
- Sleep qualifier: ≥90% → `'GOOD'`, ≥75% → `'FAIR'`, else `'POOR'`

## 3. Weight

**EXCLUDED from backfill.**

Polar export contains `polar_activity_physical_info.weight_kg` with only 4 distinct values (70.0, 71.0, 72.0, 73.0) across 2,357 rows. These are the user's profile weight setting in Polar Flow, not actual scale measurements. Backfilling these would pollute the weight table with low-fidelity data.

Existing weight sources: 265 Garmin rows, 458 MFP rows (actual measurements).

## 4. Resting Heart Rate

**Polar days with resting_hr:** 703  
**RHR range:** 55–60 bpm (avg 58)

| Category | Count | Action |
|---|---:|---|
| Garmin RHR exists for same date | 2 | SKIP |
| No Garmin RHR | 701 | INSERT |

### Collision Detail

Only 2 dates where both Polar and Garmin have resting HR. Both skipped (Garmin wins).

### Transformation Notes

- Multiple Polar sessions on the same day: take the resting_hr from the earliest session
- RHR values in Polar are the user's configured resting HR at time of recording (not measured like Garmin's overnight RHR). Lower fidelity but still useful for gap-filling.

## 5. VO2max

**Garmin vo2max rows:** 0 (table exists but empty)  
**Polar days with VO2max:** 703  
**Polar fitness test records:** 3  
**VO2max range:** 35.0–51.0 (avg 38.1)

All 703 dates insertable (no Garmin data exists).

### Transformation Notes

- Polar VO2max is from user profile settings attached to training sessions, not per-activity estimates
- 3 fitness test records provide independently measured VO2max values
- All inserted with `source='polar'`
