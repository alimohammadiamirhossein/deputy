"""Application settings: built-in defaults plus per-deployment overrides."""

DEFAULTS = {
    "debug": False,
    "db": {"host": "localhost", "port": 5432, "pool": {"min": 1, "max": 10}},
    "cache": {"ttl": 300},
}


def load(overrides):
    """Settings for one deployment. Overrides replace top-level keys."""
    settings = dict(DEFAULTS)
    settings.update(overrides)
    return settings
