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
      "scaling_tiers": {
        "rx": [{"movement": "<name>", "reps": <int or null>, "sets": <int or null>, \
"weight_lbs": <float or null>, "notes": "<text or null>"}],
        "intermediate": [...],
        "foundations": [...]
      }
    }
  ],
  "formatted_markdown": "<full Markdown formatted version of the workout>"
}

Rules:
- If trivially short or no workout content: content_class=SKIP, empty wods array.
- If only personal feelings/performance with no workout description: \
content_class=PERFORMANCE_ONLY.
- IMPORTANT — Multiple segments: A note often contains two SEPARATE workout pieces. \
A strength/lifting piece (Score is Weight, sets x reps of one movement) is ALWAYS a \
separate WOD entry from a conditioning piece (AMRAP, For Time, EMOM). Create one wods \
entry per distinct segment, not one per scaling tier.
- Scaling tiers (RX / INTERMEDIATE / FOUNDATIONS) are variants of the SAME WOD — they \
go inside scaling_tiers, NOT as separate wods entries.
- Always populate all three scaling tiers. If only RX is described, copy it to \
intermediate and foundations with notes field set to "same as RX".
- Personal performance observations go in performance_notes only.
- Some WODs have two names: a PRVN programming name and a local gym name. Extract both \
if present — primary in name, secondary in alt_name.

Few-shot example of multi-segment detection:
Input: "Back Squat 5x5 (Score is Weight) RPE: 7\\n\\nFran\\nFor Time 21-15-9\\n\
Thrusters (95/135#)\\nPull-Ups\\n(Score is Time)"
Output wods: two entries — one STRENGTH wod named "Back Squat" and one FOR_TIME wod \
named "Fran"
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


class WodSchema(BaseModel):
    name: str
    alt_name: str | None = None
    name_source: str | None = None
    regime: str | None = None
    score_type: str | None = None
    rpe: int | None = None
    intended_stimulus: str | None = None
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

        raw_json, error = self._call_ollama(ollama_url, model, system_prompt, notes)
        if error:
            return self._write_staging(workout, notes, "SKIP", None, None, error, model)

        # Pydantic validation
        parsed, error = self._validate(raw_json)
        if error:
            return self._write_staging(workout, notes, "SKIP", raw_json, None, error, model)

        # Write formatted/performance notes immediately to workout row
        workout.formatted_notes = parsed.formatted_markdown
        workout.performance_notes = parsed.performance_notes

        return self._write_staging(
            workout, notes, parsed.content_class,
            raw_json, parsed.formatted_markdown, None, model,
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
    ) -> tuple[str | None, str | None]:
        """Call Ollama and return (raw_json_string, error_message)."""
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
            return resp.json()["response"], None
        except httpx.TimeoutException:
            return None, "Ollama request timed out (>300s)"
        except Exception as exc:
            return None, f"Ollama error: {exc}"

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
    ) -> ActalogNoteParse:
        status = "pending" if not error_message and content_class != "SKIP" else "skipped"
        record = ActalogNoteParse(
            workout_id=workout.id,
            content_class=content_class,
            raw_notes=raw_notes,
            parsed_json=parsed_json,
            parse_status=status,
            parsed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            error_message=error_message,
            llm_model=llm_model,
        )
        self._session.add(record)
        return record


# ---------------------------------------------------------------------------
# Config seeding helper
# ---------------------------------------------------------------------------

def seed_default_config(session: Session) -> None:
    """Insert default parser config keys if not already present."""
    defaults = {
        CONFIG_KEY_PROMPT: DEFAULT_SYSTEM_PROMPT,
        CONFIG_KEY_MODEL: DEFAULT_MODEL,
        CONFIG_KEY_URL: DEFAULT_OLLAMA_URL,
        CONFIG_KEY_MIN_LENGTH: str(DEFAULT_MIN_LENGTH),
    }
    for key, value in defaults.items():
        if not session.get(AppConfig, key):
            session.add(AppConfig(key=key, value=value, category="parser"))
    session.commit()
