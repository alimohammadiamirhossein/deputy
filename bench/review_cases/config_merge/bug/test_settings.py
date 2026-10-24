from settings import load


def test_load_merges_nested_settings():
    settings = load({"debug": True, "db": {"host": "db.internal", "pool": {"max": 50}}})
    assert settings["debug"] is True
    assert settings["db"] == {"host": "db.internal", "port": 5432, "pool": {"min": 1, "max": 50}}
    assert settings["cache"] == {"ttl": 300}


def test_non_dict_override_replaces_the_value():
    assert load({"cache": None})["cache"] is None
