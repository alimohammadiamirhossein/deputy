"""User lookups."""

_USERS = {1: {"id": 1, "name": "Ada"}, 2: {"id": 2, "name": "Linus"}}


def get_user(user_id):
    """Return the user with `user_id`, or None if there is none."""
    return _USERS.get(user_id)
