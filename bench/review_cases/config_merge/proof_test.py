from settings import DEFAULTS, load


def test_load_does_not_change_the_defaults():
    load({"db": {"host": "db.internal", "pool": {"max": 50}}})
    assert DEFAULTS["db"] == {"host": "localhost", "port": 5432, "pool": {"min": 1, "max": 10}}
