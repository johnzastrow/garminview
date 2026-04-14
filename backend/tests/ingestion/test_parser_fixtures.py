"""Tests using real workout fixtures that previously failed parsing."""
import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "parser"


def load_fixtures():
    """Load all fixture files."""
    fixtures = []
    for f in sorted(FIXTURES_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        data["_fixture_file"] = f.name
        fixtures.append(data)
    return fixtures


@pytest.fixture(params=load_fixtures(), ids=lambda f: f["_fixture_file"])
def fixture(request):
    return request.param


def test_fixture_has_required_fields(fixture):
    """Every fixture must have the required fields."""
    assert "workout_name" in fixture
    assert "workout_date" in fixture
    assert "raw_notes" in fixture
    assert "expected" in fixture
    assert fixture["raw_notes"].strip(), f"Empty raw_notes in {fixture['_fixture_file']}"


def test_expected_has_content_class(fixture):
    """Expected output must have a content_class."""
    assert fixture["expected"]["content_class"] in (
        "WORKOUT", "MIXED", "PERFORMANCE_ONLY", "SKIP"
    )


def test_expected_wods_have_names(fixture):
    """Every expected WOD must have a name."""
    for wod in fixture["expected"]["wods"]:
        assert wod.get("name"), f"WOD missing name in {fixture['_fixture_file']}"


def test_expected_wods_have_regime(fixture):
    """Every expected WOD should have a regime."""
    for wod in fixture["expected"]["wods"]:
        assert wod.get("regime"), f"WOD missing regime in {fixture['_fixture_file']}"


def test_expected_markdown_keywords(fixture):
    """Expected markdown should contain key terms from the workout."""
    keywords = fixture["expected"].get("formatted_markdown_contains", [])
    # This validates the fixture itself — the keywords should be reasonable
    assert len(keywords) >= 2, f"Need at least 2 markdown keywords in {fixture['_fixture_file']}"


def test_json_repair_trailing_comma():
    """Test that _repair_json fixes trailing commas."""
    from garminview.ingestion.notes_parser import NotesParser
    bad_json = '{"wods": [{"name": "Fran", "regime": "FOR_TIME",}]}'
    result = NotesParser._repair_json(bad_json)
    assert result is not None
    parsed = json.loads(result)
    assert parsed["wods"][0]["name"] == "Fran"


def test_json_repair_markdown_wrapper():
    """Test that _repair_json extracts JSON from markdown code block."""
    from garminview.ingestion.notes_parser import NotesParser
    wrapped = '```json\n{"content_class": "WORKOUT", "wods": []}\n```'
    result = NotesParser._repair_json(wrapped)
    assert result is not None
    parsed = json.loads(result)
    assert parsed["content_class"] == "WORKOUT"


def test_json_repair_returns_none_for_garbage():
    """Test that _repair_json returns None for unparseable input."""
    from garminview.ingestion.notes_parser import NotesParser
    assert NotesParser._repair_json("this is not json at all") is None
    assert NotesParser._repair_json("") is None
