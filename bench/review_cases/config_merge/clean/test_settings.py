from settings import DEFAULTS, load


def test_load_merges_nested_settings():
    settings = load({"debug": True, "db": {"host": "db.internal", "pool": {"max": 50}}})
    assert settings["debug"] is True
    assert settings["db"] == {"host": "db.internal", "port": 5432, "pool": {"min": 1, "max": 50}}
    assert settings["cache"] == {"ttl": 300}


def test_non_dict_override_replaces_the_value():
    assert load({"cache": None})["cache"] is None


def test_load_leaves_the_defaults_alone():
    load({"db": {"host": "db.internal", "pool": {"max": 50}}})
    settings = load({})
    assert settings["db"] == {"host": "localhost", "port": 5432, "pool": {"min": 1, "max": 10}}
    settings["cache"]["ttl"] = 1
    assert DEFAULTS["cache"]["ttl"] == 300
