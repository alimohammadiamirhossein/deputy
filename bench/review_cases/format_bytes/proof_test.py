from units import format_bytes


def test_exactly_one_kib():
    assert format_bytes(1024) == "1.0 KiB"
