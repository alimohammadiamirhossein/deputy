"""User lookups."""
import warnings

_USERS = {1: {"id": 1, "name": "Ada"}, 2: {"id": 2, "name": "Linus"}}


def find_user(user_id):
    """Return the user with `user_id`, or None if there is none."""
    return _USERS.get(user_id)


def get_user(user_id):
    """Deprecated alias of find_user, kept until 2.0."""
    warnings.warn("get_user() is deprecated; use find_user()", DeprecationWarning, stacklevel=2)
    return find_user(user_id)
