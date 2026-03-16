# Actalog Notes Parser — Design & Planning

## Goal

Allow workouts to be pasted as unstructured text through Actalog's QuickLog function,
then automatically parse and structure them so that:

**A.** The WOD is recorded as a reusable structured entry for future workouts.
**B.** The first instance of the workout becomes the baseline for future comparisons.

The source notes field in GarminView should eventually display Markdown-formatted output.
Approved structured WODs are eventually sent back to Actalog (remote feature not yet built).

---

## Data Assessment (2026-03-16)

- **Source field:** `actalog_workouts.notes` (free text, often pasted from a gym programming system)
- **Coverage:** 61 of 264 workouts have non-empty notes (~23%)
- **Format:** Semi-structured prose — WOD name on first line, movements as line items,
  rep schemes, weight prescriptions, scaling tiers (RX / Intermediate / Foundations),
  score type, RPE, intended stimulus, coach commentary
- **Content classes (mixed within a single note):**
  - Workout description (structured, parseable)
  - Performance notes ("felt great", "all sets unbroken")
  - Coach commentary / context
  - Empty / irrelevant text
- **Complicating factors:**
  - Multiple WODs per note (e.g. a strength piece + an AMRAP)
  - Three scaling tiers per WOD — need to decide which to store or store all
  - No ground-truth labels exist yet

---

## Operational Context

- Workouts logged ~5×/week in Actalog via QuickLog (paste unstructured text into notes)
- GarminView fetches new records from Actalog on a schedule (daily or a few times/week)
- Parser runs automatically on newly fetched notes as part of that sync cycle
- **QA phase required:** model output must be human-reviewed before any write-back is trusted
- Once QA confidence is established, approved records flow back to Actalog automatically

---

## Full Pipeline

```
──────────────────────────────────────────────────────────────────────────
PHASE 1 — INGEST (existing)
──────────────────────────────────────────────────────────────────────────

  Actalog remote API
        │  (scheduled sync, daily or a few times/week)
        ▼
  actalog_workouts.notes   ← raw pasted text stored as-is

──────────────────────────────────────────────────────────────────────────
PHASE 2 — PARSE (new)
──────────────────────────────────────────────────────────────────────────

  Trigger: post-sync hook on new/updated workouts with non-empty notes
        │
        ▼
  Content classifier       ← Does this note contain a parseable workout?
  (regex + LLM)            ← Labels: WORKOUT | PERFORMANCE_ONLY | MIXED | SKIP
        │
        ├── SKIP / PERFORMANCE_ONLY → mark parsed, no further action
        │
        └── WORKOUT / MIXED
              │
              ▼
        regex pre-pass     ← cheap: WOD name, score_type, RPE, regime
              │
              ▼
        LLM (qwen2.5:3b)   ← movements, reps, weights, scaling tiers
        single prompt       ← returns JSON struct + Markdown formatted text
              │
              ├──▶  JSON → Pydantic validation
              │           → actalog_note_parses (staging table, status=pending)
              │
              └──▶  Markdown → actalog_note_parses.formatted_notes

──────────────────────────────────────────────────────────────────────────
PHASE 3 — QA REVIEW (new, Admin UI)
──────────────────────────────────────────────────────────────────────────

  Admin UI — Notes Parser panel
        │
        ├── List pending parses (original note, parsed JSON, Markdown preview)
        ├── Approve → status = approved
        ├── Edit then approve → human corrects JSON/Markdown, then approves
        └── Reject → status = rejected (note flagged for manual handling)

──────────────────────────────────────────────────────────────────────────
PHASE 4 — WRITE-BACK (new, triggers on approval)
──────────────────────────────────────────────────────────────────────────

  On approval:
        │
        ├──▶  actalog_wods / actalog_workout_wods   ← structured records written locally
        │
        ├──▶  actalog_workouts.notes updated         ← Markdown replaces raw text
        │
        └──▶  POST to remote Actalog API             ← FUTURE: blocked on Actalog changes
              parse_status set to "approved"          ← queued locally until API exists
              (Actalog must also be updated           ← see: Remote Actalog Requirements)
               to accept structured WODs)
```

---

## GarminView UI — All Touchpoints

GarminView is the sole interface for managing the entire pipeline. No steps require
direct database access or CLI interaction by the user.

### Admin section — Parser Config tab (new tab alongside Actalog config)

Controls the LLM backend and parse settings:

| Control | Purpose |
|---|---|
| Ollama base URL | e.g. `http://localhost:11434` |
| Model selector | `qwen2.5:3b` / `qwen2.5:7b` / custom |
| Min note length (chars) | Threshold below which notes are auto-skipped |
| Parse on sync toggle | Auto-run parser after each Actalog sync |
| Run parser now button | Manually trigger parse on all unprocessed notes |
| Parser status | Last run time, counts: pending / approved / rejected / skipped |

### Actalog dashboard — QA Review tab (new tab)

Where the user inspects and approves/rejects parsed records:

| Element | Purpose |
|---|---|
| Filter bar | Filter by status: pending / approved / rejected / all |
| Record list | Workout date, name, content_class, parse_status, parsed_at |
| Detail panel | Side-by-side: raw notes (left), Markdown preview (right) |
| Parsed WODs section | Expandable: each WOD with scaling tiers, movements, score type |
| Performance notes section | Extracted personal notes shown separately |
| Approve button | Writes Markdown to `notes`, commits WODs to local DB |
| Edit + Approve button | Opens inline editor for Markdown and JSON before approving |
| Reject button | Marks rejected, raw notes preserved untouched |
| Re-parse button | Discards current parse, re-runs LLM on the original note |

### Actalog dashboard — existing workout list / detail views

- `formatted_notes` displayed in workout detail once parse is complete (pre-approval)
- `performance_notes` displayed as a separate section in the same detail view
- Raw `notes` shown as fallback if no parse exists yet
- Parse status badge shown on each workout card (pending / approved / rejected / none)

---

## Staging Table: `actalog_note_parses`

Holds parser output between generation and approval. Decouples the LLM step from
any permanent writes.

```
id                 integer PK
workout_id         FK → actalog_workouts.id
content_class      enum: WORKOUT | MIXED | PERFORMANCE_ONLY | SKIP
raw_notes          text    ← snapshot of notes at parse time
formatted_notes    text    ← LLM Markdown output
parsed_json        text    ← LLM structured JSON output (raw)
parse_status       enum: pending | approved | rejected | sent
parsed_at          datetime
reviewed_at        datetime
reviewed_by        text    ← "human" or future user field
error_message      text    ← populated if parse failed
llm_model          text    ← model used (e.g. qwen2.5:3b)
```

---

## Target Schema (existing — written to on approval)

```
actalog_wods          — name, alt_name, name_source, regime, score_type
                        name        ← canonical name used for deduplication/matching
                        alt_name    ← secondary name (e.g. local gym name vs PRVN name)
                        name_source ← enum: PRVN | GYM | UNKNOWN
actalog_workout_wods  — workout_id, wod_id, score_value, time_s, rounds, reps,
                        weight_kg, rpe, is_pr, order_index
```

### Dual-name handling

Some WODs have two names: a PRVN (programming provider) name and a local gym name.
Both should be captured. The LLM should be prompted to extract both if present.
Deduplication matches on either name — if "Amanda" matches an existing WOD's `name`
or `alt_name`, link to it rather than creating a new record.

The dual-name pattern is usually visible in the text (e.g. a headline WOD name plus
a "CFY Quick Log" title on the workout). The LLM prompt should include 2–3 few-shot
examples demonstrating this pattern so the model learns to distinguish the PRVN name
from the local gym label without explicit fine-tuning. The QA review phase will catch
and correct misidentifications during the trust-building period.

---

## LLM Output Schema (per note)

A single LLM call returns both structured data and formatted text:

```json
{
  "content_class": "WORKOUT",
  "performance_notes": "Felt strong. All sets unbroken.",
  "wods": [
    {
      "name": "Turducken",
      "alt_name": "Turkey Day WOD",
      "name_source": "PRVN",
      "regime": "FOR_TIME",
      "score_type": "TIME",
      "rpe": 9,
      "intended_stimulus": "16-22 minutes",
      "scaling_tiers": {
        "rx": [
          {"movement": "Deadlift", "reps": 20, "weight_lbs": 185},
          {"movement": "Pull-Ups", "reps": 30}
        ],
        "intermediate": [...],
        "foundations": [...]
      }
    }
  ],
  "formatted_markdown": "## Turducken\n**Type:** For Time ..."
}
```

---

## Example Markdown Output Format

```markdown
## Turducken
**Type:** For Time | **Score:** Time | **RPE:** 9

### RX
- 20 Deadlifts (185#)
- 30 Pull-Ups
- 40 Wall Balls (20#)
- 50 Box Jumps
*(repeat ladder descending)*

### Intermediate
- 20 Deadlifts (135#)
- 30 Vertical Ring Rows
- 40 Wall Balls (14#)

### Foundations
- 20 Deadlifts (75#)
- 30 Ring Rows
- 40 Wall Ball Thrusters (10#)

*Intended stimulus: 16–22 minutes*

---
*Performance notes: Felt strong. All sets unbroken.*
```

---

## Model Selection and Testing

### Hardware context

| | Spec |
|---|---|
| Development machine | 32 GB system RAM, AMD RX 560 (2 GB VRAM) |
| Target VM (production) | CPU-only, 2–6 GB RAM budget |
| GPU viable? | No — RX 560 is Polaris (2016), no ROCm support in Ollama; 2 GB VRAM too small for 7B anyway |

**Inference backend:** [Ollama](https://ollama.com) — manages GGUF quantized models,
exposes a local REST API, uses llama.cpp under the hood. Already installed on dev machine.

```bash
ollama pull qwen2.5:7b   # required model
```

---

### Model comparison (tested 2026-03-16)

Four real notes were used as test cases covering every content class:

| ID | Workout name | Note content | Length |
|---|---|---|---|
| 199 | Even escence Quick Log | "great!" | 6 chars |
| 191 | Thanksgiving turducken | "Not good. Took a lot of time off" | 32 chars |
| 190 | Turducken | Full WOD — For Time, 3 scaling tiers, ladder structure | 493 chars |
| 205 | CFY Quick Log Dec 12 | Two segments: Landmine Press (strength) + The Present Tens (AMRAP, 3 tiers) | 904 chars |

#### Round 1 — initial prompt (no few-shot example)

| Note | `qwen2.5:3b` (~47s) | `qwen2.5:7b` (~187s) |
|---|---|---|
| Trivial ("great!") | ✅ `SKIP` | ✅ `SKIP` |
| Performance only | ✅ `PERFORMANCE_ONLY`, correct text | ✅ `PERFORMANCE_ONLY`, correct text |
| Turducken (single WOD, 3 tiers) | ✅ 1 WOD, 3 movements per tier | ✅ 1 WOD, 3 movements per tier |
| Landmine Press + The Present Tens | ❌ 3 WODs — confused RX/Intermediate/Foundations as separate WODs, movements wrong | ⚠️ 1 WOD (The Present Tens only) — missed Landmine Press strength segment entirely; scaling tiers correct |

**Conclusion after round 1:** 3B is not viable — it fundamentally misunderstands the
tier/WOD distinction on complex notes. 7B understands tiers but missed the separate
strength segment.

#### Round 2 — improved prompt (added explicit rule + few-shot example)

The prompt was strengthened with:
1. An explicit rule: *"Scaling tiers (RX/INTERMEDIATE/FOUNDATIONS) are variants of the SAME WOD — they go inside `scaling_tiers`, NOT as separate `wods` entries."*
2. A few-shot example showing a strength piece + conditioning piece as two distinct `wods` entries.

| Note | `qwen2.5:7b` (~232s) |
|---|---|
| Landmine Press + The Present Tens | ✅ 2 WODs correctly split: `STRENGTH` (Landmine Press, score=WEIGHT, RPE=6) + `AMRAP` (The Present Tens, score=ROUNDS_REPS, RPE=8, all 3 tiers populated) |

**Remaining gap:** Landmine Press had empty `intermediate` and `foundations` tiers.
The prompt rule to copy RX to other tiers when only one is described needs reinforcement.
This is a prompt wording issue, not a model capability issue.

#### Markdown output quality (round 2, 7B)

```markdown
# Workout
## Landmine Press
Score Weight — 4 Sets — RPE: 6

## The Present Tens
### RX
2 Sets AMRAP x 8 MINUTES
- 10 Strict Pull-Ups
- 10 Ring Dips
- 10 Alt. DB Farmer Box Step-Ups (35/50#)(20/24")
  -Rest 1:30 b/t Sets-  RPE: 8, Intended Stimulus: 4-6 Rounds

### INTERMEDIATE
- 10 Vertical Ring Rows / 10 Dips / 10 Alt. DB Farmer Box Step-Ups (20/35#)

### FOUNDATIONS
- 10 Ring Rows / 10 Dips / 10 Alt. DB Farmer Box Step-Ups (up to 20#)
```

Clean, readable, correct structure. Minor formatting polish possible via prompt.

---

### Performance characteristics

| Note type | Typical time (7B, CPU) |
|---|---|
| SKIP / PERFORMANCE_ONLY | < 5s |
| Single WOD, 1–3 tiers | ~60–90s |
| Multi-WOD, complex tiers | ~190–240s |

At 5 new notes/week, worst-case batch time is ~20 minutes. Acceptable for a nightly
scheduled job. Not suitable for real-time on-demand parsing from the UI.

---

### Model verdict

| Model | RAM | Verdict |
|---|---|---|
| `qwen2.5:3b` | ~2.0 GB | ❌ Fails on multi-tier WODs |
| `qwen2.5:7b` | ~4.5 GB | ✅ **Required minimum — use this** |
| `llama3.1:8b` | ~4.7 GB | Untested |

---

### Prompt storage in production

The system prompt is stored in the `app_config` table (existing), not hardcoded in
Python. This allows:

- Editing from the Admin UI without a code deployment
- Runtime model/prompt swapping as new WOD formats emerge
- Future: storing prompt version history alongside approval/rejection stats

Prompt iteration is the primary optimization lever at this scale — lower effort and
faster feedback than fine-tuning or RAG. The Admin UI will include a prompt editor
with a "test against last 5 notes" dry-run button before saving.

---

## Open Questions

### Resolved

1. **Does Actalog render Markdown?** ✅ Yes — Markdown write-back to notes is worthwhile.

2. **Remote Actalog WOD API:** ✅ No API exists yet. Phase 4 write-back (structured WOD
   upload) is blocked until Actalog builds the endpoint. Approved parses will be queued
   locally in `actalog_note_parses` with `status=approved` until the API is available.

### Resolved (continued)

3. **Scaling tier storage:** ✅ Always store all three tiers (RX / Intermediate /
   Foundations) as separate scaling entries within the WOD record.

4. **Multi-WOD notes:** ✅ If a strength piece is clearly a separate segment, store it
   as a separate `actalog_wod` record. Ambiguous combined blocks stored as one record.

5. **Re-parse trigger:** ✅ If notes are edited in Actalog and re-synced, re-parse and
   reset to `pending`. Any existing approved parse is overwritten.

6. **Deduplication:** ✅ Link repeated WODs to the same `actalog_wod` record. Match
   priority: exact name → fuzzy name → movement signature.

7. **Markdown write-back timing:** ✅ Write Markdown to `actalog_workouts.formatted_notes`
   immediately on parse (before QA). Write to `actalog_workouts.notes` only after approval.

8. **Performance notes handling:** ✅ Extract performance notes into a separate Markdown
   section and store in the new `actalog_workouts.performance_notes` TEXT column.
   The `formatted_notes` field contains the structured WOD Markdown only.

9. **QA UI location:** ✅ Review panel lives as a tab in the Actalog dashboard.

10. **Minimum viable note:** ✅ Skip with pure regex — check length and absence of
    workout keywords before invoking the LLM. No classification pass needed.

---

## Model Improvement Over Time

The QA approval step does not directly retrain the model — Ollama runs a static
quantized model whose weights never change. However, approved records form a
ground-truth dataset that feeds improvement indirectly.

### What QA approvals accumulate

Each approved record in `actalog_note_parses` is a labeled example:
`raw_notes → correct parsed_json + formatted_notes`. Over time this becomes a
structured training corpus.

### Improvement options

| Option | When | Effort | Effect |
|---|---|---|---|
| Add corrected examples to few-shot prompt | Immediately, as failures occur | Very low | Immediate; no retraining needed |
| RAG — retrieve similar past parses at inference time | ~50+ approved records | Medium | Model sees relevant examples per note |
| Fine-tune a small model (e.g. via `unsloth` or `llama-factory`) | ~100+ approved records, GPU available | High | Permanent weight-level improvement |

### Near-term strategy

Use QA approvals to improve the few-shot prompt. When a note type fails review,
add a corrected `(input → output)` example of that type to the prompt. This requires
no retraining, works at any dataset size, and is the highest-leverage action for
a corpus of this scale.

Track model accuracy over time using `actalog_note_parses` — count approvals vs.
rejections per `llm_model` to measure improvement as the prompt evolves or the
model is swapped.

---

## Remote Actalog Requirements (Phase 4 dependency)

Phase 4 write-back is blocked until Actalog implements the following on its side.
GarminView will queue approved records locally (`parse_status = approved`) until
these endpoints exist.

### API endpoints needed in Actalog

| Endpoint | Purpose |
|---|---|
| `POST /api/wods` | Create a new named WOD with scaling tiers and movements |
| `POST /api/workout-wods` | Link a WOD to an existing workout (with score, RPE, etc.) |
| `PATCH /api/workouts/:id` | Update `notes` field with Markdown-formatted text |

### Data model changes needed in Actalog

| Change | Purpose |
|---|---|
| `wods` table | Store reusable named WODs (name, regime, score_type) |
| `wod_movements` table | Movements per WOD with scaling tier, reps, weight |
| `workout_wods` join table | Link workouts to WODs with performance data |
| `workouts.notes` | Must support Markdown (rendering already confirmed) |

These requirements should be communicated to the Actalog developer as a spec when
GarminView's parser and QA pipeline are functional and the output format is stable.

---

## Schema Changes Required

### `actalog_workouts` — two new columns
```
formatted_notes    TEXT    ← LLM Markdown output, written immediately on parse
performance_notes  TEXT    ← extracted personal notes, written immediately on parse
```

### New table: `actalog_note_parses` — staging / audit trail
```
id                 INTEGER PK
workout_id         FK → actalog_workouts.id
content_class      TEXT    ← WORKOUT | MIXED | PERFORMANCE_ONLY | SKIP
raw_notes          TEXT    ← snapshot of notes at parse time
parsed_json        TEXT    ← full LLM JSON output
parse_status       TEXT    ← pending | approved | rejected | sent
parsed_at          DATETIME
reviewed_at        DATETIME
error_message      TEXT
llm_model          TEXT    ← e.g. qwen2.5:3b
```

---

## Phases and Status

| Phase | Description | Status |
|---|---|---|
| 1 | Ingest (sync from Actalog) | ✅ Complete |
| 2 | Parser (LLM + regex + staging table) | ⬜ Not started |
| 3 | QA review tab in Actalog dashboard | ⬜ Not started |
| 4 | Write-back on approval (local DB + queued for remote API) | ⬜ Not started |

---

## Next Steps

- [x] Install Ollama (already present)
- [x] Pull and test `qwen2.5:3b` and `qwen2.5:7b` — 7b confirmed as required model
- [ ] Strengthen prompt with few-shot example for multi-segment WOD detection (Landmine Press case)
- [ ] Add `formatted_notes` and `performance_notes` columns to `actalog_workouts` (Alembic migration)
- [ ] Create `actalog_note_parses` staging table (Alembic migration)
- [ ] Write regex pre-pass (trivial note detection, score_type, WOD name, RPE)
- [ ] Write LLM prompt template (extraction + Markdown + performance notes separation)
- [ ] Write Pydantic validation + error handling for bad parses
- [ ] Wire parser into post-sync hook (runs on new/changed notes automatically)
- [ ] Build Parser Config tab in Admin section (Ollama URL, model, threshold, run now, status)
- [ ] Build QA Review tab in Actalog dashboard (list, side-by-side preview, approve/edit/reject/re-parse)
- [ ] Show formatted_notes + performance_notes + parse status badge in existing workout detail view
- [ ] Build write-back on approval (structured WODs to local DB, Markdown to notes field)
- [ ] Communicate Remote Actalog Requirements spec to Actalog developer when output format is stable
- [ ] Write full implementation plan
