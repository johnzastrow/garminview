"""notes_parser.py — LLM-backed parser for actalog_workouts.notes

Pipeline per note:
  1. Regex pre-pass: skip trivially short or empty notes immediately
  2. Call Ollama /api/generate with system prompt from app_config
  3. Parse and Pydantic-validate the JSON response
  4. Write staging record to actalog_note_parses (status=pending)
  5. Write formatted_notes and performance_notes to actalog_workouts

The system prompt is stored in app_config under key "parser.system_prompt"
so it can be edited from the Admin UI without a code deployment.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from garminview.core.logging import get_logger
from garminview.models.actalog import ActalogNoteParse, ActalogWorkout
from garminview.models.config import AppConfig

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_KEY_PROMPT = "parser.system_prompt"
CONFIG_KEY_MODEL = "parser.ollama_model"
CONFIG_KEY_URL = "parser.ollama_url"
CONFIG_KEY_MIN_LENGTH = "parser.min_note_length"

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_MIN_LENGTH = 20  # notes shorter than this are auto-SKIPped

DEFAULT_SYSTEM_PROMPT = """\
You are a CrossFit/fitness workout parser. Given raw notes from a workout log, \
extract structured data and return ONLY valid JSON — no commentary, no markdown fences.

Return this exact schema:
{
  "content_class": "WORKOUT" | "MIXED" | "PERFORMANCE_ONLY" | "SKIP",
  "performance_notes": "<personal notes if any, else null>",
  "wods": [
    {
      "name": "<primary WOD name>",
      "alt_name": "<secondary/local gym name if present, else null>",
      "name_source": "PRVN" | "GYM" | "UNKNOWN",
      "regime": "FOR_TIME" | "AMRAP" | "EMOM" | "STRENGTH" | "CHIPPER" | "OTHER",
      "score_type": "TIME" | "ROUNDS_REPS" | "WEIGHT" | "REPS" | "CALORIES" | "NONE",
      "rpe": <integer 1-10 or null>,
      "intended_stimulus": "<text or null>",
      "time_cap_min": <integer minutes or null — AMRAP only>,
      "scaling_tiers": {
        "rx": [{"movement": "<name>", "reps": <int or null>, "sets": <int or null>, \
"weight_lbs": <float or null>, "notes": "<text or null>"}],
        "intermediate": [...],
        "foundations": [...],
        "travel": [...],
        "partner": [...]
      }
    }
  ],
  "formatted_markdown": "<Markdown — follow the template below exactly>"
}

Rules:
- If trivially short or no workout content: content_class=SKIP, empty wods array.
- If only personal feelings/performance with no workout description: \
content_class=PERFORMANCE_ONLY.
- MIXED requires actual personal commentary present in performance_notes. If there are \
no personal observations, use WORKOUT instead of MIXED.
- IMPORTANT — Multiple segments: A note often contains two SEPARATE workout pieces. \
A strength/lifting piece (Score is Weight, sets x reps of one movement) is ALWAYS a \
separate WOD entry from a conditioning piece (AMRAP, For Time, EMOM). Create one wods \
entry per distinct segment, not one per scaling tier. Finisher sections are also \
separate WOD entries.
- WOD naming: assign the WOD name to the conditioning piece it labels. A preceding \
strength or warm-up block (e.g. "Strength + Stability + Plyo", "Every 4:00 x 3 Sets") \
is a separate WOD with its OWN name — do not carry the conditioning WOD name back \
onto the strength block.
- Scaling tiers (RX / INTERMEDIATE / FOUNDATIONS) are variants of the SAME WOD — they \
go inside scaling_tiers, NOT as separate wods entries.
- Travel / Hotel tier: many notes include an extra scaling option labeled \
"Travel / Hotel:" or "[WOD Name: Travel]". Extract this into the `travel` key of \
scaling_tiers. It follows the same movement schema as rx/intermediate/foundations.
- Partner tier: sections labeled "Partner Workout Option", "IN TEAMS OF 2", or similar \
are a scaling tier, NOT a separate WOD. Extract into the `partner` key of \
scaling_tiers. Do NOT create a new wods entry for it.
- Scaling tiers: only populate a tier if it is explicitly described in the notes. \
For single-tier WODs (typically STRENGTH or when only one tier is given), leave \
intermediate, foundations, and travel as empty arrays []. Do NOT copy RX to fill \
empty tiers.
- Personal performance observations go in performance_notes only.
- AMRAP: regime=AMRAP always has score_type=ROUNDS_REPS. Never assign score_type=TIME \
to an AMRAP. The time_cap_min field holds the AMRAP duration in minutes.
- time_cap_min ONLY applies when regime=AMRAP. It MUST be null for FOR_TIME, EMOM, \
STRENGTH, and all other regimes.
- name_source: use PRVN for branded PRVN programming names, GYM for local gym names \
or generic exercise names (Back Squat, Bench Press, Deadlift, Lunge, Metcon, etc.), \
UNKNOWN only when the source is genuinely ambiguous.
- Some WODs have two names: a PRVN programming name and a local gym name. Extract both \
if present — primary in name, secondary in alt_name.
- IMPORTANT — Movement extraction: the `movement` field must contain ONLY the exercise \
name, never a rep count. Always extract the integer rep count into `reps`. \
Rep ranges (e.g. "15-20 DB Rows") → movement="DB Bent Over Rows", reps=null, \
notes="15-20 reps". Calorie targets (e.g. "21 Cal Row") → movement="Row", reps=21, \
notes="calories". Complex combined movements (e.g. "Back Squats + 3 Box Jumps") → \
split into two separate movement entries.
- Descending and pyramid rep schemes (e.g. "9-7-5", "21-15-9", "30-25-15-8-15-25-30"): \
set reps=null and notes="30-25-15-8-15-25-30" on EACH movement in the scheme. \
ALL movements in the scheme share the same notes value. Never extract only the first \
number — always capture the full hyphen-separated sequence.
- Interval structures: "EVERY X:00 x N SETS" or "E{X}MOM" means regime=EMOM. \
Put the full interval description (e.g. "Every 4:00 x 3 Sets") in `intended_stimulus`. \
The movements listed inside are the work done each interval.
- Combined tiers: when two tiers are explicitly merged (e.g. "INTERMEDIATE / FOUNDATIONS"), \
extract the movements under `intermediate` only — do not duplicate into foundations.
- CRITICAL — bracket-label travel syntax: "[WOD Name: Travel]" (e.g. "[John Wick: Travel]", \
"[Falling Hard: Travel]") is NOT a new WOD. It is the travel scaling tier of the WOD whose \
name precedes the colon. Add those movements to the `travel` array of the matching wod entry. \
Never create a wods entry with a name containing ": Travel".
- CRITICAL — WOD name invention: NEVER invent or infer a WOD name that does not appear \
verbatim in the raw notes. If movements are described without an explicit workout name, derive \
a short descriptive label from the movements (e.g. "Clean / Push Press / Wall Ball") or use \
"Metcon". Do NOT assign any famous benchmark WOD name (Fran, Diane, Helen, Annie, Cindy, \
Karen, Isabel, Grace, etc.) unless that exact name is present in the raw text.

Markdown template — follow this structure exactly:

Single-tier WOD (no scaling, e.g. a pure strength piece):
```
# {WOD Name}
*{alt_name}*  ← omit if no alt name; always in italics

**{REGIME}** · Score: {SCORE_TYPE} · RPE: {rpe}/10 · Stimulus: {intended_stimulus}
← For AMRAP replace Stimulus with: Time Cap: {time_cap_min} minutes
← Omit Stimulus and Time Cap if neither is present

- {sets}×{reps} {movement} ({weight}#)

---

*{performance_notes}*  ← omit if no performance notes
```

Multi-tier WOD (RX / Intermediate / Foundations, and optionally Travel):
```
# {WOD Name}
*{alt_name}*  ← omit if no alt name

**{REGIME}** · Score: {SCORE_TYPE} · RPE: {rpe}/10 · Stimulus: {intended_stimulus}

### RX
- {reps} × {movement} ({weight}#)

### Intermediate
- {reps} × {movement} ({weight}#)

### Foundations
- {reps} × {movement} ({weight}#)

### Travel / Hotel
- {reps} × {movement} ({weight}#)
← omit Travel / Hotel section if no travel tier exists

### Partner
- {reps} × {movement} ({weight}#)
← omit Partner section if no partner tier exists

---

*{performance_notes}*
```

Descending rep scheme (e.g. 9-7-5, 21-15-9) — movements share the scheme:
```
### RX
**9-7-5:**
- {movement} ({weight}#)
- {movement} ({weight}#)
```

Multi-WOD note (two or more separate segments):
```
### Part 1

# {WOD Name 1}
*{alt_name}*  ← omit if no alt name

**{REGIME}** · Score: {SCORE_TYPE} · RPE: {rpe}/10

- {sets}×{reps} {movement} ({weight}#)

---

### Part 2

# {WOD Name 2}

**{REGIME}** · Score: {SCORE_TYPE} · RPE: {rpe}/10 · Time Cap: {time_cap_min} minutes

### RX
- {reps} × {movement} ({weight}#)

### Intermediate
- {reps} × {movement} ({weight}#)

### Foundations
- {reps} × {movement} ({weight}#)

### Travel / Hotel
- {reps} × {movement} ({weight}#)
← omit Travel / Hotel if not present

---

*{performance_notes}*
```

Few-shot examples:

Multi-segment detection:
Input: "Back Squat 5x5 (Score is Weight) RPE: 7\\n\\nFran\\nFor Time 21-15-9\\n\
Thrusters (95/135#)\\nPull-Ups\\n(Score is Time)"
Output wods: two entries — one STRENGTH wod named "Back Squat" and one FOR_TIME wod \
named "Fran"

Pyramid rep scheme:
Input: "Sit Happens\\nFOR TIME\\n30-25-15-8-15-25-30\\nCal Bike\\nSit-Ups"
Output rx movements: [{movement: "Cal Bike", reps: null, notes: "30-25-15-8-15-25-30"}, \
{movement: "Sit-Ups", reps: null, notes: "30-25-15-8-15-25-30"}]
Markdown: "**30-25-15-8-15-25-30:**\\n- Cal Bike\\n- Sit-Ups"

Interval structure:
Input: "EVERY 4:00 x 3 SETS\\n15-20 DB Bent Over Rows\\n12-15 DB Floor Press"
Output: regime=EMOM, intended_stimulus="Every 4:00 x 3 Sets", \
movements with reps=null and notes="15-20 reps" / "12-15 reps"

No-name WOD (DO NOT invent a benchmark name):
Input: "### Back squat for strength\\n### Then clean, push press and wall ball for time"
WRONG: name="Fran" (Fran is not present in the text)
CORRECT: name="Back Squat" for the strength piece; name="Clean / Push Press / Wall Ball" \
for the conditioning piece (or "Metcon" if movements are unclear)

Travel tier bracket syntax:
Input: "Wall Ball State\\nRX: [movements...]\\n[John Wick: Travel]\\nTravel / Hotel:\\n\
[travel movements...]"
WRONG: create a second wods entry named "John Wick: Travel" or "Travel / Hotel"
CORRECT: one wods entry named "Wall Ball State" with the travel movements in \
scaling_tiers.travel[]
"""

# Workout-related keywords — presence suggests a parseable note
_WORKOUT_KEYWORDS = re.compile(
    r"\b(amrap|emom|for time|reps|sets|rounds|deadlift|squat|pull.?up|push.?up|"
    r"thruster|snatch|clean|jerk|row|run|score|rx|wod|workout|press|swing|lunge|"
    r"box jump|burpee|muscle.?up|kettlebell|barbell|dumbbell|kb|db)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Pydantic output schema
# ---------------------------------------------------------------------------

class MovementSchema(BaseModel):
    movement: str
    reps: int | None = None
    sets: int | None = None
    weight_lbs: float | None = None
    notes: str | None = None


class ScalingTiersSchema(BaseModel):
    rx: list[MovementSchema] = Field(default_factory=list)
    intermediate: list[MovementSchema] = Field(default_factory=list)
    foundations: list[MovementSchema] = Field(default_factory=list)
    travel: list[MovementSchema] = Field(default_factory=list)
    partner: list[MovementSchema] = Field(default_factory=list)


class WodSchema(BaseModel):
    name: str
    alt_name: str | None = None
    name_source: str | None = None
    regime: str | None = None
    score_type: str | None = None
    rpe: int | None = None
    intended_stimulus: str | None = None
    time_cap_min: int | None = None
    scaling_tiers: ScalingTiersSchema = Field(default_factory=ScalingTiersSchema)

    @field_validator("rpe", mode="before")
    @classmethod
    def clamp_rpe(cls, v: Any) -> int | None:
        if v is None:
            return None
        try:
            return max(1, min(10, int(v)))
        except (TypeError, ValueError):
            return None


class ParsedNoteSchema(BaseModel):
    content_class: str  # WORKOUT | MIXED | PERFORMANCE_ONLY | SKIP
    performance_notes: str | None = None
    wods: list[WodSchema] = Field(default_factory=list)
    formatted_markdown: str | None = None


# ---------------------------------------------------------------------------
# Parser service
# ---------------------------------------------------------------------------

class NotesParser:
    """Parse a single actalog workout note via Ollama and write to staging."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._cfg: dict[str, str] = {}
        self._load_config()

    def _load_config(self) -> None:
        keys = [CONFIG_KEY_PROMPT, CONFIG_KEY_MODEL, CONFIG_KEY_URL, CONFIG_KEY_MIN_LENGTH]
        rows = self._session.query(AppConfig).filter(AppConfig.key.in_(keys)).all()
        self._cfg = {r.key: r.value for r in rows if r.value}

    def _get(self, key: str, default: str) -> str:
        return self._cfg.get(key, default)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_workout(self, workout_id: int) -> ActalogNoteParse:
        """Parse notes for one workout. Returns the staging record."""
        workout = self._session.get(ActalogWorkout, workout_id)
        if workout is None:
            raise ValueError(f"Workout {workout_id} not found")

        notes = (workout.notes or "").strip()

        # Regex pre-pass — skip without calling the LLM
        content_class, skip_reason = self._classify_trivial(notes)
        if content_class == "SKIP":
            return self._write_staging(workout, notes, content_class, None, None, skip_reason)

        # LLM call
        model = self._get(CONFIG_KEY_MODEL, DEFAULT_MODEL)
        ollama_url = self._get(CONFIG_KEY_URL, DEFAULT_OLLAMA_URL)
        system_prompt = self._get(CONFIG_KEY_PROMPT, DEFAULT_SYSTEM_PROMPT)

        raw_json, error, timing = self._call_ollama(ollama_url, model, system_prompt, notes)
        if error:
            return self._write_staging(workout, notes, "SKIP", None, None, error, model, timing)

        # Pydantic validation
        parsed, error = self._validate(raw_json)
        if error:
            return self._write_staging(workout, notes, "SKIP", raw_json, None, error, model, timing)

        # Write formatted/performance notes immediately to workout row
        workout.formatted_notes = parsed.formatted_markdown
        workout.performance_notes = parsed.performance_notes

        return self._write_staging(
            workout, notes, parsed.content_class,
            raw_json, parsed.formatted_markdown, None, model, timing,
        )

    def parse_pending(self, limit: int = 50) -> list[ActalogNoteParse]:
        """Parse all workouts whose notes have not yet been staged."""
        already_staged = {
            row.workout_id
            for row in self._session.query(ActalogNoteParse.workout_id).all()
        }
        workouts = (
            self._session.query(ActalogWorkout)
            .filter(
                ActalogWorkout.notes.isnot(None),
                ActalogWorkout.notes != "",
            )
            .limit(limit)
            .all()
        )
        results = []
        for w in workouts:
            if w.id in already_staged:
                continue
            try:
                record = self.parse_workout(w.id)
                self._session.commit()
                results.append(record)
                log.info("notes_parser.parsed", workout_id=w.id, status=record.parse_status,
                         content_class=record.content_class)
            except Exception as exc:
                self._session.rollback()
                log.error("notes_parser.error", workout_id=w.id, error=str(exc))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_trivial(self, notes: str) -> tuple[str, str | None]:
        """Return (content_class, reason) without calling the LLM."""
        min_len = int(self._get(CONFIG_KEY_MIN_LENGTH, str(DEFAULT_MIN_LENGTH)))
        if len(notes) < min_len:
            return "SKIP", f"note too short ({len(notes)} chars < {min_len})"
        if not _WORKOUT_KEYWORDS.search(notes):
            return "SKIP", "no workout keywords detected"
        return "UNKNOWN", None

    def _call_ollama(
        self, base_url: str, model: str, system_prompt: str, note: str,
    ) -> tuple[str | None, str | None, dict]:
        """Call Ollama and return (raw_json_string, error_message, timing_dict).

        timing_dict keys: parse_duration_s, llm_tokens_prompt,
                          llm_tokens_generated, llm_inference_s
        """
        t0 = time.monotonic()
        try:
            resp = httpx.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "system": system_prompt,
                    "prompt": note,
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=300,
            )
            resp.raise_for_status()
            body = resp.json()
            timing = {
                "parse_duration_s": round(time.monotonic() - t0, 3),
                "llm_tokens_prompt": body.get("prompt_eval_count"),
                "llm_tokens_generated": body.get("eval_count"),
                "llm_inference_s": round(body["eval_duration"] / 1e9, 3) if body.get("eval_duration") else None,
            }
            return body["response"], None, timing
        except httpx.TimeoutException:
            return None, "Ollama request timed out (>300s)", {"parse_duration_s": round(time.monotonic() - t0, 3)}
        except Exception as exc:
            return None, f"Ollama error: {exc}", {"parse_duration_s": round(time.monotonic() - t0, 3)}

    def _validate(self, raw: str) -> tuple[ParsedNoteSchema | None, str | None]:
        """Parse and validate LLM JSON output. Returns (schema, error)."""
        try:
            data = json.loads(raw)
            return ParsedNoteSchema.model_validate(data), None
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON: {exc}"
        except Exception as exc:
            return None, f"Validation error: {exc}"

    def _write_staging(
        self,
        workout: ActalogWorkout,
        raw_notes: str,
        content_class: str,
        parsed_json: str | None,
        formatted_markdown: str | None,
        error_message: str | None,
        llm_model: str | None = None,
        timing: dict | None = None,
    ) -> ActalogNoteParse:
        status = "pending" if not error_message and content_class != "SKIP" else "skipped"
        t = timing or {}
        record = ActalogNoteParse(
            workout_id=workout.id,
            content_class=content_class,
            raw_notes=raw_notes,
            parsed_json=parsed_json,
            parse_status=status,
            parsed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            error_message=error_message,
            llm_model=llm_model,
            parse_duration_s=t.get("parse_duration_s"),
            llm_tokens_prompt=t.get("llm_tokens_prompt"),
            llm_tokens_generated=t.get("llm_tokens_generated"),
            llm_inference_s=t.get("llm_inference_s"),
        )
        self._session.add(record)
        log.info(
            "notes_parser.timing",
            workout_id=workout.id,
            model=llm_model,
            parse_duration_s=t.get("parse_duration_s"),
            tokens_prompt=t.get("llm_tokens_prompt"),
            tokens_generated=t.get("llm_tokens_generated"),
            inference_s=t.get("llm_inference_s"),
        )
        return record


# ---------------------------------------------------------------------------
# Config seeding helper
# ---------------------------------------------------------------------------

def seed_default_config(session: Session, update_prompt: bool = False) -> None:
    """Insert default parser config keys if not already present.

    Args:
        update_prompt: If True, overwrite the stored system prompt with the
            current DEFAULT_SYSTEM_PROMPT (use after prompt revisions).
    """
    defaults = {
        CONFIG_KEY_PROMPT: DEFAULT_SYSTEM_PROMPT,
        CONFIG_KEY_MODEL: DEFAULT_MODEL,
        CONFIG_KEY_URL: DEFAULT_OLLAMA_URL,
        CONFIG_KEY_MIN_LENGTH: str(DEFAULT_MIN_LENGTH),
    }
    for key, value in defaults.items():
        row = session.get(AppConfig, key)
        if row is None:
            session.add(AppConfig(key=key, value=value, category="parser"))
        elif key == CONFIG_KEY_PROMPT and update_prompt:
            row.value = value
    session.commit()
