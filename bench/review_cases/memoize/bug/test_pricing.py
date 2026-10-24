from pricing import quote


def test_quote():
    assert quote("apple") == 0.5
    assert quote("melon", 2) == 6.0
    assert quote("pear", 4, "EUR") == 2.76


def test_cached_results_depend_on_the_arguments():
    assert quote("melon", 2) == 6.0
    assert quote("melon", 3) == 9.0
    assert quote("melon", 2) == 6.0


def test_cache_clear():
    quote("pear")
    quote.cache_clear()
    assert quote("pear") == 0.75
