import json
from unittest.mock import MagicMock, patch

from garminview.ingestion.notes_parser import (
    NotesParser,
    ParsedNoteSchema,
    _maybe_url_decode,
    seed_default_config,
)
from garminview.models.actalog import ActalogWorkout, ActalogNoteParse


def _make_session(workout_notes: str = "", config: dict | None = None):
    """Build a minimal mock session."""
    workout = ActalogWorkout(id=1, workout_name="Test", notes=workout_notes)
    session = MagicMock()
    session.get.side_effect = lambda model, key: (
        workout if model is ActalogWorkout else None
    )
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
    session, _ = _make_session(
        "Not good. Took a lot of time off and felt terrible today."
    )
    parser = NotesParser(session)
    with patch.object(parser, "_call_ollama") as mock_llm:
        record = parser.parse_workout(1)
        mock_llm.assert_not_called()
    assert record.parse_status == "skipped"


def test_keyword_gate_matches_plural_and_gerund_bodyweight_terms():
    # Real bodyweight session (WID 309) — plurals/gerund must not slip the gate.
    from garminview.ingestion.notes_parser import _WORKOUT_KEYWORDS

    assert _WORKOUT_KEYWORDS.search("Running, pull ups, push ups, air squats")
    assert _WORKOUT_KEYWORDS.search("50 double unders, 30 sit-ups, wall balls")
    # Genuinely non-workout notes still fall through to SKIP.
    assert not _WORKOUT_KEYWORDS.search("Felt tired, slept poorly, work was stressful.")
    assert not _WORKOUT_KEYWORDS.search("rest day, walked the dog and read a book")


def test_maybe_url_decode_decodes_fully_encoded_note():
    # No literal whitespace, dense with %XX -> unambiguously encoded, decode it.
    encoded = "strength:%20Deadlift%20Conditioning%0A%0AFor%20Time%3A"
    assert _maybe_url_decode(encoded) == "strength: Deadlift Conditioning\n\nFor Time:"


def test_maybe_url_decode_leaves_literal_percent_untouched():
    # A normal note has whitespace and may contain a literal '%'; never alter it.
    for plain in (
        "Back Squat 5x5 at 75% of 1RM",
        "AMRAP 11: 4 DB Front Squats (35/50#)",
        "Row 20/16+ Cals per minute",
        "",
    ):
        assert _maybe_url_decode(plain) == plain


def test_maybe_url_decode_ignores_coincidental_escape_without_whitespace():
    # A spaceless token that decodes but yields no whitespace stays as-is.
    assert (
        _maybe_url_decode("A%42C") == "A%42C"
    )  # would be "ABC" — no whitespace, reject


def test_url_encoded_workout_note_passes_gate_and_calls_llm_decoded():
    encoded = (
        "strength:%20Pause%20Front%20Squat%0A%0A15%3A00%20EMOM%3A%0A"
        "Minute%201%3A%206%20Pause%20Front%20Squats"
    )
    session, _ = _make_session(encoded)
    parser = NotesParser(session)
    llm_response = json.dumps(
        {
            "content_class": "WORKOUT",
            "performance_notes": None,
            "wods": [
                {
                    "name": "Pause Front Squat",
                    "alt_name": None,
                    "name_source": "UNKNOWN",
                    "regime": "EMOM",
                    "score_type": "TIME",
                    "rpe": None,
                    "intended_stimulus": None,
                    "scaling_tiers": {
                        "rx": [
                            {
                                "movement": "Pause Front Squats",
                                "reps": "6",
                                "sets": None,
                                "weight_lbs": None,
                                "notes": "Minute 1",
                            }
                        ],
                        "intermediate": [],
                        "foundations": [],
                    },
                }
            ],
            "formatted_markdown": "## Pause Front Squat",
        }
    )
    with patch.object(
        parser,
        "_call_ollama",
        return_value=(llm_response, None, {"parse_duration_s": 1.0}),
    ) as mock_llm:
        record = parser.parse_workout(1)
        mock_llm.assert_called_once()
        # The note handed to the LLM must be decoded, not the raw %XX form.
        note_arg = mock_llm.call_args.args[3]
        assert "%20" not in note_arg
        assert "15:00 EMOM:" in note_arg
    assert record.parse_status == "pending"
    assert record.content_class == "WORKOUT"


def test_note_with_workout_keywords_calls_llm():
    session, _ = _make_session(
        "For Time: 21-15-9 Thrusters and Pull-Ups. Score is Time."
    )
    parser = NotesParser(session)
    llm_response = json.dumps(
        {
            "content_class": "WORKOUT",
            "performance_notes": None,
            "wods": [
                {
                    "name": "Fran",
                    "alt_name": None,
                    "name_source": "UNKNOWN",
                    "regime": "FOR_TIME",
                    "score_type": "TIME",
                    "rpe": None,
                    "intended_stimulus": None,
                    "scaling_tiers": {
                        "rx": [
                            {
                                "movement": "Thrusters",
                                "reps": "21",
                                "sets": None,
                                "weight_lbs": "95",
                                "notes": None,
                            }
                        ],
                        "intermediate": [],
                        "foundations": [],
                    },
                }
            ],
            "formatted_markdown": "## Fran\n**For Time**\n- Thrusters\n- Pull-Ups",
        }
    )
    with patch.object(
        parser,
        "_call_ollama",
        return_value=(llm_response, None, {"parse_duration_s": 1.2}),
    ):
        record = parser.parse_workout(1)
    assert record.parse_status == "pending"
    assert record.content_class == "WORKOUT"
    assert record.parsed_json == llm_response


def test_invalid_json_from_llm_sets_error():
    session, _ = _make_session("AMRAP 20 min: 5 pull-ups, 10 push-ups, 15 squats")
    parser = NotesParser(session)
    with patch.object(
        parser,
        "_call_ollama",
        return_value=("not valid json {{{", None, {"parse_duration_s": 0.5}),
    ):
        record = parser.parse_workout(1)
    assert record.parse_status == "skipped"
    assert record.error_message is not None
    assert "JSON" in record.error_message


def test_llm_timeout_sets_error():
    session, _ = _make_session("AMRAP 20 min: 5 pull-ups, 10 push-ups, 15 squats")
    parser = NotesParser(session)
    with patch.object(
        parser,
        "_call_ollama",
        return_value=(
            None,
            "Ollama request timed out (>300s)",
            {"parse_duration_s": 300.1},
        ),
    ):
        record = parser.parse_workout(1)
    assert record.parse_status == "skipped"
    assert "timed out" in record.error_message


def test_formatted_notes_written_to_workout_on_success():
    session, workout = _make_session("AMRAP 20 min: 5 pull-ups, 10 push-ups, 15 squats")
    parser = NotesParser(session)
    markdown = "## AMRAP 20\n- 5 Pull-Ups\n- 10 Push-Ups\n- 15 Squats"
    llm_response = json.dumps(
        {
            "content_class": "WORKOUT",
            "performance_notes": "Felt good",
            "wods": [
                {
                    "name": "AMRAP 20",
                    "alt_name": None,
                    "name_source": "UNKNOWN",
                    "regime": "AMRAP",
                    "score_type": "ROUNDS_REPS",
                    "rpe": 7,
                    "intended_stimulus": None,
                    "scaling_tiers": {"rx": [], "intermediate": [], "foundations": []},
                }
            ],
            "formatted_markdown": markdown,
        }
    )
    with patch.object(
        parser,
        "_call_ollama",
        return_value=(
            llm_response,
            None,
            {
                "parse_duration_s": 2.1,
                "llm_tokens_prompt": 300,
                "llm_tokens_generated": 150,
                "llm_inference_s": 1.9,
            },
        ),
    ):
        parser.parse_workout(1)
    assert workout.formatted_notes == markdown
    assert workout.performance_notes == "Felt good"


def test_rpe_clamped_to_valid_range():
    data = {
        "content_class": "WORKOUT",
        "wods": [
            {
                "name": "Test",
                "regime": "FOR_TIME",
                "score_type": "TIME",
                "rpe": 99,
                "scaling_tiers": {"rx": [], "intermediate": [], "foundations": []},
            }
        ],
    }
    parsed = ParsedNoteSchema.model_validate(data)
    assert parsed.wods[0].rpe == 10


def test_seed_default_config_inserts_missing_keys():
    session = MagicMock()
    session.get.return_value = None  # nothing exists yet
    seed_default_config(session)
    assert session.add.call_count == 5  # 5 config keys (incl. parser.backend)
    session.commit.assert_called_once()


def test_seed_default_config_skips_existing_keys():
    existing = MagicMock()
    session = MagicMock()
    session.get.return_value = existing  # all keys already present
    seed_default_config(session)
    session.add.assert_not_called()


def test_call_ollama_uses_constrained_decoding():
    """_call_ollama must send the ParsedNoteSchema as Ollama's `format` so the
    reply is grammar-constrained (no dropped fields / prose / invalid JSON)."""
    session, _ = _make_session("x")
    parser = NotesParser(session)
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "response": "{}",
                "prompt_eval_count": 5,
                "eval_count": 3,
                "eval_duration": 1_000_000_000,
            }

    def _fake_post(url, json=None, timeout=None):
        captured["json"] = json
        return _Resp()

    with patch("garminview.ingestion.notes_parser.httpx.post", side_effect=_fake_post):
        parser._call_ollama("http://x:11434", "qwen2.5:7b", "sys prompt", "note text")

    assert captured["json"]["format"] == ParsedNoteSchema.model_json_schema()
    assert captured["json"]["model"] == "qwen2.5:7b"


def test_parse_pending_drains_unstaged_not_just_first_n(session):
    """Regression: the unstaged filter must be applied before the limit. With the
    limit applied first, an already-staged head of the table would starve the
    backlog and parse 0 new workouts."""
    note = "Did Fran: 21-15-9 thrusters and pull-ups. Felt great."
    for i in (1, 2, 3):
        session.add(ActalogWorkout(id=i, workout_name=f"W{i}", notes=note))
    for i in (1, 2):  # first two already staged
        session.add(
            ActalogNoteParse(workout_id=i, parse_status="sent", content_class="WORKOUT")
        )
    session.commit()

    parser = NotesParser(session)
    called = []

    def _stub(workout_id, force=False):
        called.append(workout_id)
        rec = ActalogNoteParse(
            workout_id=workout_id, parse_status="pending", content_class="WORKOUT"
        )
        session.add(rec)
        return rec

    with patch.object(parser, "parse_workout", side_effect=_stub):
        results = parser.parse_pending(limit=2)

    # Only the unstaged workout (3) is parsed; the pre-fix code would return [].
    assert called == [3]
    assert len(results) == 1
    assert results[0].workout_id == 3


def test_call_openai_uses_schema_and_disables_thinking():
    """The OpenAI-compatible backend must send response_format=json_schema
    (constrained decoding) AND disable thinking (or qwen3.5 models hang)."""
    session, _ = _make_session("x")
    parser = NotesParser(session)
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

    def _fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    with patch("garminview.ingestion.notes_parser.httpx.post", side_effect=_fake_post):
        raw, err, timing = parser._call_openai(
            "http://gpu:8080", "qwen3.5-35b-a3b", "sys", "note"
        )

    assert err is None and raw == "{}"
    assert captured["url"].endswith("/v1/chat/completions")
    body = captured["json"]
    assert body["model"] == "qwen3.5-35b-a3b"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["max_tokens"] == 8192
    assert body["response_format"]["type"] == "json_schema"
    assert (
        body["response_format"]["json_schema"]["schema"]
        == ParsedNoteSchema.model_json_schema()
    )
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert timing["llm_tokens_prompt"] == 10


def test_call_llm_dispatches_by_backend_config():
    """_call_llm routes to the OpenAI backend when parser.backend == 'openai',
    otherwise to Ollama."""
    session, _ = _make_session("x")
    parser = NotesParser(session)
    with (
        patch.object(parser, "_call_openai", return_value=("o", None, {})) as mo,
        patch.object(parser, "_call_ollama", return_value=("l", None, {})) as ml,
    ):
        # default backend -> ollama
        parser._cfg.pop("parser.backend", None)
        parser._call_llm("u", "m", "s", "n")
        ml.assert_called_once()
        mo.assert_not_called()
        # backend=openai -> openai
        parser._cfg["parser.backend"] = "openai"
        parser._call_llm("u", "m", "s", "n")
        mo.assert_called_once()


def test_movement_schema_has_cardio_fields():
    """distance_m / calories / duration_s exist so cardio quantities (metres,
    calories, timed holds) get their own fields instead of being crammed into
    reps -- the top pattern from the parse-triage report."""
    from garminview.ingestion.notes_parser import MovementSchema

    props = set(MovementSchema.model_json_schema()["properties"])
    assert {"distance_m", "calories", "duration_s"} <= props
    m = MovementSchema.model_validate({"movement": "Run", "distance_m": "800"})
    assert m.distance_m == "800" and m.reps is None
    # male/female slash preserved verbatim
    assert (
        MovementSchema.model_validate(
            {"movement": "Bike", "calories": "50/60"}
        ).calories
        == "50/60"
    )


def test_mixed_without_notes_demoted_to_workout():
    """MIXED with empty performance_notes is deterministically demoted to WORKOUT."""
    from garminview.ingestion.notes_parser import ParsedNoteSchema as P

    assert P(content_class="MIXED", performance_notes=None).content_class == "WORKOUT"
    assert P(content_class="MIXED", performance_notes="   ").content_class == "WORKOUT"
    # real commentary keeps MIXED; other classes untouched
    assert (
        P(content_class="MIXED", performance_notes="felt strong").content_class
        == "MIXED"
    )
    assert P(content_class="WORKOUT").content_class == "WORKOUT"


def test_wod_schema_has_rounds_and_generic_timecap():
    """rounds captures '6 Rounds' at WOD level (not sets per movement); time_cap_min
    is generic (not AMRAP-only)."""
    from garminview.ingestion.notes_parser import WodSchema

    w = WodSchema.model_validate(
        {
            "name": "Dual It'll Dance",
            "regime": "FOR_TIME",
            "rounds": "6",
            "time_cap_min": 15,
        }
    )
    assert w.rounds == "6" and w.time_cap_min == 15
    assert "rounds" in WodSchema.model_json_schema()["properties"]
