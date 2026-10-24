"""Greetings shown on the home page."""
from users import find_user


def greeting(user_id):
    user = find_user(user_id)
    return f"Hello, {user['name']}!" if user else "Hello, stranger!"
