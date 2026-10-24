import pytest

from sync import push


def test_push_raises_when_every_attempt_fails():
    def send(record):
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        push({"id": 1}, send, sleep=lambda seconds: None)
