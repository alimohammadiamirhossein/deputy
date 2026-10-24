from greet import greeting
from users import get_user


def test_get_user():
    assert get_user(1)["name"] == "Ada"
    assert get_user(99) is None


def test_greeting():
    assert greeting(2) == "Hello, Linus!"
    assert greeting(99) == "Hello, stranger!"
