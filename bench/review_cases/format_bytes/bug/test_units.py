import pytest

from units import format_bytes, format_count


def test_format_count():
    assert format_count(1234567) == "1,234,567"


@pytest.mark.parametrize("n, text", [
    (0, "0 B"), (512, "512 B"), (1536, "1.5 KiB"), (5 * 1024**3, "5.0 GiB"),
])
def test_format_bytes(n, text):
    assert format_bytes(n) == text


def test_format_bytes_rejects_negative_sizes():
    with pytest.raises(ValueError):
        format_bytes(-1)
