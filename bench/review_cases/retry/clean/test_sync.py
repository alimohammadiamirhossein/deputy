import pytest

from retry import retry
from sync import push


def no_sleep(seconds):
    pass


def flaky(failures, result="ok"):
    """A callable that raises ConnectionError `failures` times, then returns `result`."""
    calls = []

    def fn():
        calls.append(1)
        if len(calls) <= failures:
            raise ConnectionError("down")
        return result

    fn.calls = calls
    return fn


def test_push_returns_the_response():
    assert push({"id": 1}, lambda record: {"ok": True, "id": record["id"]},
                sleep=no_sleep) == {"ok": True, "id": 1}


def test_retry_recovers_from_transient_errors():
    waits = []
    fn = flaky(2)
    assert retry(fn, attempts=3, delay=0.5, sleep=waits.append) == "ok"
    assert len(fn.calls) == 3 and waits == [0.5, 1.0]


def test_retry_raises_the_last_error_when_every_attempt_fails():
    fn = flaky(5)
    with pytest.raises(ConnectionError):
        retry(fn, attempts=3, sleep=no_sleep)
    assert len(fn.calls) == 3


def test_retry_does_not_retry_other_errors():
    calls = []

    def fn():
        calls.append(1)
        raise KeyError("bad record")

    with pytest.raises(KeyError):
        retry(fn, sleep=no_sleep)
    assert len(calls) == 1


def test_retry_rejects_zero_attempts():
    with pytest.raises(ValueError):
        retry(lambda: "ok", attempts=0)
