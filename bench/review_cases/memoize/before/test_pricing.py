from pricing import quote


def test_quote():
    assert quote("apple") == 0.5
    assert quote("melon", 2) == 6.0
    assert quote("pear", 4, "EUR") == 2.76
