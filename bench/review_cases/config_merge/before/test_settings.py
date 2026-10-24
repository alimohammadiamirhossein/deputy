from settings import load


def test_load_applies_overrides():
    settings = load({"debug": True})
    assert settings["debug"] is True
    assert settings["db"]["port"] == 5432
