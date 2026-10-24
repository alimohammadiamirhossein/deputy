from units import format_count


def test_format_count():
    assert format_count(1234567) == "1,234,567"
