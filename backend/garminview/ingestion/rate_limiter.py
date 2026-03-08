from tenacity import (
    retry, retry_if_exception_type, wait_exponential,
    stop_after_attempt, before_sleep_log
)
import logging
from garminconnect import GarminConnectTooManyRequestsError

logger = logging.getLogger(__name__)

_retry = retry(
    retry=retry_if_exception_type(GarminConnectTooManyRequestsError),
    wait=wait_exponential(multiplier=1, min=30, max=300),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def call_with_backoff(fn, *args, **kwargs):
    return _retry(fn)(*args, **kwargs)
