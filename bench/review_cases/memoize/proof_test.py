from pricing import quote


def test_keyword_arguments_are_part_of_the_cache_key():
    assert quote("apple") == 0.5
    assert quote("apple", qty=4) == 2.0
