import json
from pathlib import Path
from datetime import date

FIXTURE = Path(__file__).parent / "fixtures" / "daily_summary_sample.json"


def test_daily_summary_adapter_parses_record():
    from garminview.ingestion.file_adapters.daily_summary import DailySummaryAdapter
    adapter = DailySummaryAdapter(data_dir=FIXTURE.parent)
    records = list(adapter._parse_file(FIXTURE))
    assert len(records) == 1
    r = records[0]
    assert r["date"] == date(2026, 1, 15)
    assert r["steps"] == 8234
    assert r["hr_resting"] == 52
