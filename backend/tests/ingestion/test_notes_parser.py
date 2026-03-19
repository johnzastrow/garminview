import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from garminview.ingestion.notes_parser import NotesParser, ParsedNoteSchema, seed_default_config
from garminview.models.actalog import ActalogWorkout, ActalogNoteParse
from garminview.models.config import AppConfig


def _make_session(workout_notes: str = "", config: dict | None = None):
    """Build a minimal mock session."""
    workout = ActalogWorkout(id=1, workout_name="Test", notes=workout_notes)
    session = MagicMock()
    session.get.side_effect = lambda model, key: workout if model is ActalogWorkout else None
    cfg_rows = []
    for k, v in (config or {}).items():
        row = MagicMock()
        row.key = k
        row.value = v
        cfg_rows.append(row)
    session.query.return_value.filter.return_value.all.return_value = cfg_rows
    session.add = MagicMock()
    return session, workout


def test_trivial_note_skipped_without_llm():
    session, _ = _make_session("great!")
    parser = NotesParser(session)
    with patch.object(parser, "_call_ollama") as mock_llm:
        record = parser.parse_workout(1)
        mock_llm.assert_not_called()
    assert record.parse_status == "skipped"
    assert record.content_class == "SKIP"


def test_note_with_no_keywords_skipped():
    session, _ = _make_session("Not good. Took a lot of time off and felt terrible today.")
    parser = NotesParser(session)
    with patch.object(parser, "_call_ollama") as mock_llm:
        record = parser.parse_workout(1)
        mock_llm.assert_not_called()
    assert record.parse_status == "skipped"


def test_note_with_workout_keywords_calls_llm():
    session, _ = _make_session("For Time: 21-15-9 Thrusters and Pull-Ups. Score is Time.")
    parser = NotesParser(session)
    llm_response = json.dumps({
        "content_class": "WORKOUT",
        "performance_notes": None,
        "wods": [{
            "name": "Fran",
            "alt_name": None,
            "name_source": "UNKNOWN",
            "regime": "FOR_TIME",
            "score_type": "TIME",
            "rpe": None,
            "intended_stimulus": None,
            "scaling_tiers": {
                "rx": [{"movement": "Thrusters", "reps": 21, "sets": None, "weight_lbs": 95.0, "notes": None}],
                "intermediate": [],
                "foundations": [],
            },
        }],
        "formatted_markdown": "## Fran\n**For Time**\n- Thrusters\n- Pull-Ups",
    })
    with patch.object(parser, "_call_ollama", return_value=(llm_response, None, {"parse_duration_s": 1.2})):
        record = parser.parse_workout(1)
    assert record.parse_status == "pending"
    assert record.content_class == "WORKOUT"
    assert record.parsed_json == llm_response


def test_invalid_json_from_llm_sets_error():
    session, _ = _make_session("AMRAP 20 min: 5 pull-ups, 10 push-ups, 15 squats")
    parser = NotesParser(session)
    with patch.object(parser, "_call_ollama", return_value=("not valid json {{{", None, {"parse_duration_s": 0.5})):
        record = parser.parse_workout(1)
    assert record.parse_status == "skipped"
    assert record.error_message is not None
    assert "JSON" in record.error_message


def test_llm_timeout_sets_error():
    session, _ = _make_session("AMRAP 20 min: 5 pull-ups, 10 push-ups, 15 squats")
    parser = NotesParser(session)
    with patch.object(parser, "_call_ollama", return_value=(None, "Ollama request timed out (>300s)", {"parse_duration_s": 300.1})):
        record = parser.parse_workout(1)
    assert record.parse_status == "skipped"
    assert "timed out" in record.error_message


def test_formatted_notes_written_to_workout_on_success():
    session, workout = _make_session("AMRAP 20 min: 5 pull-ups, 10 push-ups, 15 squats")
    parser = NotesParser(session)
    markdown = "## AMRAP 20\n- 5 Pull-Ups\n- 10 Push-Ups\n- 15 Squats"
    llm_response = json.dumps({
        "content_class": "WORKOUT",
        "performance_notes": "Felt good",
        "wods": [{
            "name": "AMRAP 20",
            "alt_name": None,
            "name_source": "UNKNOWN",
            "regime": "AMRAP",
            "score_type": "ROUNDS_REPS",
            "rpe": 7,
            "intended_stimulus": None,
            "scaling_tiers": {"rx": [], "intermediate": [], "foundations": []},
        }],
        "formatted_markdown": markdown,
    })
    with patch.object(parser, "_call_ollama", return_value=(llm_response, None, {"parse_duration_s": 2.1, "llm_tokens_prompt": 300, "llm_tokens_generated": 150, "llm_inference_s": 1.9})):
        parser.parse_workout(1)
    assert workout.formatted_notes == markdown
    assert workout.performance_notes == "Felt good"


def test_rpe_clamped_to_valid_range():
    data = {
        "content_class": "WORKOUT",
        "wods": [{
            "name": "Test",
            "regime": "FOR_TIME",
            "score_type": "TIME",
            "rpe": 99,
            "scaling_tiers": {"rx": [], "intermediate": [], "foundations": []},
        }],
    }
    parsed = ParsedNoteSchema.model_validate(data)
    assert parsed.wods[0].rpe == 10


def test_seed_default_config_inserts_missing_keys():
    session = MagicMock()
    session.get.return_value = None  # nothing exists yet
    seed_default_config(session)
    assert session.add.call_count == 4  # 4 config keys
    session.commit.assert_called_once()


def test_seed_default_config_skips_existing_keys():
    existing = MagicMock()
    session = MagicMock()
    session.get.return_value = existing  # all keys already present
    seed_default_config(session)
    session.add.assert_not_called()
