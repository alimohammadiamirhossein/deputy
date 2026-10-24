"""Retry calls that fail with transient errors."""
import time


def retry(fn, attempts=3, delay=0.5, retry_on=(ConnectionError,), sleep=time.sleep):
    """Call fn() until it succeeds, at most `attempts` times, and return its result.

    Waits `delay` seconds after the first failure and doubles the wait each time. Errors not
    listed in `retry_on` propagate at once. If every attempt fails, the last error is raised.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on:
            if attempt == attempts:
                raise
            sleep(delay * 2 ** (attempt - 1))
