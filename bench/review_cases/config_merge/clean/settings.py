"""Application settings: built-in defaults plus per-deployment overrides."""
import copy

DEFAULTS = {
    "debug": False,
    "db": {"host": "localhost", "port": 5432, "pool": {"min": 1, "max": 10}},
    "cache": {"ttl": 300},
}


def merge(base, overrides):
    """Return a new dict with `overrides` applied on top of `base`. Nested dicts are merged key
    by key; any other value replaces the base value. Neither argument is modified."""
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load(overrides):
    """Settings for one deployment: `overrides` merged into the defaults."""
    return merge(DEFAULTS, overrides)
