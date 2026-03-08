def test_retry_on_too_many_requests():
    from unittest.mock import patch
    from garminconnect import GarminConnectTooManyRequestsError
    from garminview.ingestion.rate_limiter import call_with_backoff

    call_count = 0

    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise GarminConnectTooManyRequestsError("rate limited")
        return "ok"

    with patch("time.sleep"):  # prevent tenacity from actually waiting
        result = call_with_backoff(flaky)

    assert result == "ok"
    assert call_count == 3
