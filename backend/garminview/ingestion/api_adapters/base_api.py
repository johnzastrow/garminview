from garminconnect import Garmin
from garminview.ingestion.rate_limiter import call_with_backoff


class BaseAPIAdapter:
    def __init__(self, client: Garmin):
        self._client = client

    def _call(self, method, *args, **kwargs):
        return call_with_backoff(getattr(self._client, method), *args, **kwargs)
