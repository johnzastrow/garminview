# Parser Test Cases — Plan

**Goal:** Create test fixtures from 4 real workouts that the LLM parser failed on, write the expected output manually, and use them to improve parser reliability.

## Problem

The parser fails on these workouts due to:
1. **Malformed JSON** — LLM generates JSON with missing commas/delimiters (2 cases)
2. **Empty response** — LLM returns nothing (2 cases)
3. **Timeout** — LLM takes >300s on a complex workout (1 case)

## Approach

1. **Extract raw notes** from the 4 failing workouts into test fixture files
2. **Hand-write the expected parsed output** (JSON + Markdown) for each
3. **Add retry logic** — when the LLM returns invalid JSON, retry once with a simplified prompt
4. **Add JSON repair** — attempt to fix common JSON errors (trailing commas, missing quotes) before rejecting
5. **Use fixtures in unit tests** to validate any prompt or parsing changes

## Step 1: Create test fixtures

Create `backend/tests/fixtures/parser/` with one JSON file per workout containing `raw_notes` and `expected_output`:

### Fixture 1: `hot_quadder.json` (Jan 3, 2026)
- **Raw notes:** Bench Press 1x2 + Hot Quadder AMRAP 12 with 3 scaling tiers (RX, Intermediate, Foundations)
- **Expected:** 2 WODs — "Bench Press" (STRENGTH) + "Hot Quadder" (AMRAP)
- **Why it failed:** Invalid JSON delimiter — LLM likely struggled with the scaling tiers format

### Fixture 2: `ren_and_stompy.json` (Dec 28, 2025)
- **Raw notes:** Ren and Stompy AMRAP 25 min with renegade rows + walking lunges
- **Expected:** 1 WOD — "Ren and Stompy" (AMRAP, 25 min)
- **Why it failed:** Empty JSON response — unclear why, notes seem straightforward

### Fixture 3: `12_slays_of_fitmas.json` (Dec 24, 2025)
- **Raw notes:** 12 Slays of Fitmas — 12-day accumulating workout (like "12 Days of Christmas") with RX + Intermediate tiers, 1298 chars
- **Expected:** 1 WOD — "12 Slays of Fitmas" (FOR_TIME)
- **Why it failed:** Timeout — long notes with complex structure (12 movements × 2 tiers)

### Fixture 4: `out_of_hibernation.json` (Dec 21, 2025)
- **Raw notes:** Bench Press 1x2 + Out of Hibernation AMRAP 15 with bear crawl + burpees
- **Expected:** 2 WODs — "Bench Press" (STRENGTH) + "Out of Hibernation" (AMRAP)
- **Why it failed:** Empty JSON response

### Fixture 5: `leg_daze.json` (Dec 20, 2025)
- **Raw notes:** Leg Daze — 2 Rounds for Time with 3 tiers + partner option
- **Expected:** 1 WOD — "Leg Daze" (FOR_TIME)
- **Why it failed:** Invalid JSON delimiter — partner option and pipe characters may confuse LLM

## Step 2: Write expected output for each fixture

Each fixture file:
```json
{
  "workout_name": "Quick Log Sat, Jan 3, 2026",
  "workout_date": "2026-01-03",
  "raw_notes": "Bench Press 1x2\n\n*Start Moderate...",
  "expected": {
    "content_class": "WORKOUT",
    "wods": [
      {
        "name": "Bench Press",
        "regime": "STRENGTH",
        "score_type": "WEIGHT",
        "movements": [{"movement": "Bench Press", "sets": 1, "reps": 2}]
      },
      {
        "name": "Hot Quadder",
        "regime": "AMRAP",
        "score_type": "ROUNDS_REPS",
        "rpe": 9,
        "movements": [
          {"movement": "Bike", "reps": "6/8", "notes": "Cal"},
          {"movement": "Wall Balls", "reps": 15, "weight_lbs": "14/20"},
          {"movement": "Burpee Box Jump Overs", "reps": 10, "notes": "20/24\""}
        ],
        "scaling_tiers": {
          "intermediate": [...],
          "foundations": [...]
        }
      }
    ],
    "formatted_markdown": "## Bench Press\n1x2 — Start moderate, end heavy\n**Score:** Weight | **RPE:** 9\n\n## Hot Quadder\nAMRAP 12\n- 6/8 Cal Bike\n- 15 Wall Balls (14/20#)\n- 10 Burpee Box Jump Overs (20/24\")\n\n### Intermediate\n..."
  }
}
```

## Step 3: Improve parser resilience

### 3a: JSON repair before rejection

In `notes_parser.py`, before rejecting invalid JSON, try to fix common issues:

```python
def _repair_json(raw: str) -> str | None:
    """Attempt to fix common LLM JSON errors."""
    import re
    # Remove trailing commas before } or ]
    fixed = re.sub(r',\s*([}\]])', r'\1', raw)
    # Try parsing the fixed version
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        return None
```

### 3b: Retry on failure

When the LLM returns invalid JSON, retry once with a shorter prompt that emphasizes JSON formatting:

```python
# After first attempt fails:
retry_prompt = "Return ONLY valid JSON. No text before or after the JSON object."
raw_json2, error2, timing2 = self._call_ollama(url, model, retry_prompt, notes)
```

### 3c: Increase timeout for long notes

If notes > 800 chars, increase the Ollama timeout from 300s to 600s.

## Step 4: Unit tests

Create `backend/tests/ingestion/test_parser_fixtures.py`:

```python
import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "parser"

@pytest.fixture(params=list(FIXTURES_DIR.glob("*.json")))
def fixture(request):
    return json.loads(request.param.read_text())

def test_expected_content_class(fixture):
    """Verify the expected content_class for each fixture."""
    assert fixture["expected"]["content_class"] in ("WORKOUT", "MIXED", "PERFORMANCE_ONLY")

def test_expected_wods_have_names(fixture):
    """Every expected WOD must have a name."""
    for wod in fixture["expected"]["wods"]:
        assert wod["name"], f"WOD missing name in {fixture['workout_name']}"

def test_expected_markdown_not_empty(fixture):
    """Expected markdown must be non-empty."""
    assert fixture["expected"]["formatted_markdown"].strip()
```

These tests validate the fixture format. Actual LLM output tests would be integration tests (require Ollama running).

## Step 5: Integration test (optional, requires Ollama)

```python
@pytest.mark.integration
def test_parser_produces_valid_output(fixture):
    """Run the parser on fixture input and compare to expected output."""
    parser = NotesParser(session)
    result = parser._call_ollama(url, model, prompt, fixture["raw_notes"])
    parsed = json.loads(result)
    assert parsed["content_class"] == fixture["expected"]["content_class"]
    assert len(parsed["wods"]) == len(fixture["expected"]["wods"])
```
