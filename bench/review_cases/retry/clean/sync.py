"""Push records to the remote inventory service."""
import time

from retry import retry


def push(record, send, sleep=time.sleep):
    """Send one record and return the service's response. `send` raises ConnectionError when
    the service is unreachable; push tries up to 3 times before giving up."""
    return retry(lambda: send(record), attempts=3, sleep=sleep)
