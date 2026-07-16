# Actalog Notes-Parser — LLM Model Bake-Off

**Date:** 2026-07-16
**Author:** engineering review (Claude-assisted)
**Purpose:** Decide which local LLM + decoding technique the actalog notes-parser
should use, after reports that extraction accuracy was poor. Decision driver:
**accuracy over speed** (this is an overnight batch job).

---

## 1. Context

The parser (`backend/garminview/ingestion/notes_parser.py`) turns free-text CrossFit
workout notes into a structured `ParsedNoteSchema` (WODs, scaling tiers, movements with
reps/sets/weight). That structured data feeds the **Movements / WODs / Personal Records**
tabs, which are currently near-empty.

Two independent problems were found:

1. **No constrained decoding.** `_call_ollama` sends the note with a system prompt asking
   for JSON, then post-hoc `_repair_json`s the reply. It does **not** use Ollama's
   `format` parameter, even though a full Pydantic schema (`ParsedNoteSchema`) already
   exists. The model is free to omit fields, mislabel, or emit prose.
2. **Model size.** The parser was recently switched to `qwen2.5:3b` for speed.

This bake-off isolates both variables.

## 2. Environment / fixed variables

| Variable | Value |
|---|---|
| Host | RAINBOZEN, **CPU-only** (Ryzen, 12 cores, AVX2). No usable GPU — the AMD RX 550 is gfx803/2 GB, unsupported by ROCm; see the GPU note. |
| Inference server | Ollama 0.13.5, local, `0.0.0.0:11434` |
| Temperature | 0.1 (all runs) |
| Schema (when enabled) | `ParsedNoteSchema.model_json_schema()` passed as Ollama `format` (grammar-constrained decoding) |
| System prompt | The parser's configured `parser.system_prompt` (unchanged across runs) |
| qwen3 thinking | Left **on** (default) — we chose accuracy over speed |

## 3. Configurations tested

| # | Model | Size | Schema-constrained | Rationale |
|---|---|---|---|---|
| A | qwen2.5:3b | 1.9 GB | No | **Current production baseline** |
| B | qwen2.5:3b | 1.9 GB | Yes | Isolate the effect of constrained decoding alone |
| C | qwen2.5:7b | 4.7 GB | Yes | Larger same-family model |
| D | qwen3:8b | 5.2 GB | Yes | Newer generation (hybrid reasoning) |

## 4. Inputs (three real workout notes)

### Note 231 — strength + accessory (379 chars)
Bench Press %1RM (4 sets @ 70/75/80/85%), Rotational Medball Chest Pass, then a "Wings"
block: Strict Pull-Ups, Ring Rows, Dual DB Hammer Curls.
**Ground truth:** ~5 distinct movements across 2 sections.

### Note 225 — "Baseline" EMOM with scaling tiers (772 chars)
Named **"Baseline"**, regime **EMOM**, score REPS. Three tiers (RX / Intermediate /
Foundations), each 4 movements (Row Cal, Burpee Box Jump Overs, a pull-up variant, Wall
Balls). Travel & Partner empty.
**Ground truth:** name "Baseline", regime EMOM, **12 movements** (3 x 4), empty travel/partner.

### Note 223 — mixed strength + "for time" (1484 chars)
"Back Squat" STRENGTH progression (4 set schemes) **plus** "Messin' with Squatsnatch" FOR
TIME with three tiers (~6 movements each).
**Ground truth:** **2 WODs**, ~18-22 movements across tiers.

> Full note text is preserved in the appendix.

## 5. Results

Metrics per run: wall-time (CPU), generated tokens, valid JSON, schema-valid, WOD count,
movement count, and — the accuracy tell — the extracted WOD **name**.

| Config | Note | Time | Tokens | Valid | WODs | Movements | Notes on accuracy |
|---|---|---:|---:|:--:|:--:|---:|---|
| **A. 3b, no schema** | 231 | 145s | 537 | yes | 2 | **0** | Movements dropped entirely |
| | 225 | 52s | 399 | yes | 1 | **0** | Named WOD **"EMOM"** (wrong — that's the regime); no movements |
| | 223 | 117s | 939 | yes | 1 | 16 | Missed the 2nd WOD (lumped into one) |
| **B. 3b + schema** | 231 | 159s | 601 | yes | 2 | **7** | Movements recovered (0 -> 7) |
| | 225 | 100s | 714 | yes | 1 | **12** | All 12 movements captured; name still **"EMOM"** (wrong) |
| | 223 | 192s | 1441 | yes | 2 | 32 | Both WODs; but 32 movs = over-extraction / duplicates |
| **C. 7b + schema** | 231 | 342s | 762 | yes | 2 | 8 | Clean |
| | 225 | 206s | 822 | yes | 1 | **12** | Name **"Baseline"** correct; regime EMOM; 12 movements |
| | 223 | 246s | 945 | yes | 2 | 18 | 2 WODs, clean count (closest to ground truth) |
| **D. qwen3:8b + schema** | 231 | 317s | 444 | yes | 2 | 3 | Under-extracted |
| | 225 | — | — | **TIMEOUT** | — | — | Thinking mode exceeded timeout on CPU |
| | 223 | — | — | **TIMEOUT** | — | — | Same |

### Accuracy scoring (vs ground truth)

| Config | Movement recall | WOD split | Naming | Verdict |
|---|---|---|---|---|
| A. 3b no-schema | **Poor** (0 on 2/3 notes) | Missed splits | Wrong ("EMOM") | This is the reported problem |
| B. 3b + schema | Good (over-extracts on 223) | Correct | **Wrong** ("EMOM") | Big jump from A; weak semantics |
| C. **7b + schema** | Good, clean counts | Correct | **Correct** ("Baseline") | **Best** |
| D. qwen3:8b | n/a (timeouts) | n/a | n/a | Unusable on CPU |

## 6. Assessment

1. **Constrained decoding is the decisive fix — and it is model-independent.** The
   production baseline (A) extracted **zero movements on two of three notes**; enabling the
   schema on the *same 3B model* (B) recovered them (0 -> 7, 0 -> 12). This single change
   explains most of the "accuracy is not great" report. It should be adopted regardless of
   model.

2. **7B is the accuracy winner.** Config C correctly named the WOD **"Baseline"** where both
   3B configs mislabeled it **"EMOM"** (the regime), and it produced the cleanest movement
   counts (18 on note 223 vs 3B's over-extracted 32). Naming accuracy matters because the
   WOD/Movement tabs key off names. Cost: ~3-6 min/note on CPU — irrelevant for an overnight
   batch drain.

3. **qwen3:8b is out.** Its thinking mode **timed out on 2 of 3 notes** on CPU and, where it
   finished, under-extracted (3 movements on note 231). A newer generation did not help; the
   reasoning tokens are pure cost here. (Disabling thinking would help speed but there is no
   accuracy case to pursue it.)

## 7. Recommendation

Adopt **`qwen2.5:7b` + schema-constrained decoding**, delivered as one PR with three changes:

1. **Structured outputs** — pass `format=ParsedNoteSchema.model_json_schema()` in
   `_call_ollama`. (Biggest accuracy lever; makes `_repair_json` largely redundant.)
2. **Model** — set `parser.ollama_model = qwen2.5:7b` (already pulled).
3. **`parse_pending` backlog-drain fix** — it applies `.limit()` before skipping
   already-staged workouts, so it re-scans the first ~50 (all done) and drains nothing;
   exclude staged IDs in SQL before `.limit()`.

Then drain the ~77-workout backlog **thermally paced** (thread cap + cooldowns + a temp
guard) so it runs safely overnight, and review the resulting parses in the QA/Review tab —
which is what populates Movements / WODs / PRs.

## 8. Caveats / method notes

- Times are CPU wall-clock and vary with load; treat as relative, not absolute.
- A second pass to capture every raw JSON output verbatim was **aborted deliberately**: the
  host reached 89.8 degC, so the run was stopped to protect the CPU. The metrics and the
  note-225 deep-dive above come from the first complete run and are sufficient for the
  decision. Full raw JSON can be captured later if needed, paced.
- Single temperature (0.1) and one prompt; no repeated trials for variance. Given the size
  of the effects (0 vs 12 movements; correct vs wrong name), added trials are unlikely to
  change the ranking.

---

## Appendix — full input notes

### Note 231
```
Bench Press

Every 2:30 x 4 Sets
Set 1: 5 Reps @ 70%
Set 2: 5 Reps @ 75%
Set 3: 5 Reps @ 80%
Set 4: 3+ Reps @ 85%

% of 1RM Bench Press
*Add 5/5 Rotational Medball Chest Pass Each Set
- These can be done to the Wall or to a Partner to create a fun partner version

"Wings" (T: Hammer Curl Time)

Every 5:00 x 3 Sets
6 Strict Pull-Ups
12 Ring Rows
24 Dual Dumbbell Hammer Curls
```

### Note 225
```
# Baseline
**EMOM** · Score: REPS · RPE: 8.5/10 · Stimulus: Mixed-modal baseline test ...

### RX
- 20:00 EMOM for Max Reps
  - Minute 1: Row Calories
  - Minute 2: Burpee Box Jump Overs (Facing)
  - Minute 3: Chest-to-Bar Pull-Ups
  - Minute 4: Wall Balls (20/14lb, 10/9ft)
### Intermediate
  - Minute 3: Pull-Ups  (else same)
### Foundations
  - Minute 2: Elevated Burpee Box Step-Ups; Minute 3: Jumping Pull-Ups; Minute 4: Wall Ball Thruster
### Travel / Hotel  —  (empty)
### Partner  —  (empty)
```

### Note 223
```
# Back Squat  — STRENGTH · Score: NONE · RPE: 8.5/10
- 1x10, 2x8, 3x6, 4x6 Back Squat

### Messin' with Squatsnatch  — FOR TIME · Time Cap 12 min
#### RX  (3 Sets 95/65lb): 7 OHS, 7 Bar-Facing Burpee, 5 Power Snatch, 5 BF Burpee, 3 Squat Snatch, 3 BF Burpee
#### INTERMEDIATE (3 Sets 75/55lb): 7 Front Squat, 7 Burpee, 5 Power Snatch, 5 Burpee, 3 Squat Snatch, 3 Burpee
#### FOUNDATIONS (3 Sets): 7 Front Squat (45#), 5 Elevated Burpee, 7 Hang Power Snatch, 5 Elevated Burpee
```
