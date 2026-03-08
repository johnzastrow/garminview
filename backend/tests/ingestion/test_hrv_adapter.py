def test_hrv_adapter_parses_response():
    from unittest.mock import MagicMock, patch
    from datetime import date
    from garminview.ingestion.api_adapters.hrv import HRVAdapter

    mock_client = MagicMock()
    mock_client.get_hrv_data.return_value = {
        "hrvSummary": {
            "rmssd": 42.5,
            "highFrequency": 38.0,
            "lowFrequency": 12.0,
            "baselineLowUpper": 35.0,
            "baselineBalancedUpper": 55.0,
            "status": "BALANCED",
        }
    }

    adapter = HRVAdapter(client=mock_client)
    with patch("time.sleep"):
        records = list(adapter.fetch(date(2026, 1, 1), date(2026, 1, 1)))

    assert len(records) == 1
    r = records[0]
    assert r["hrv_rmssd"] == 42.5
    assert r["status"] == "BALANCED"
