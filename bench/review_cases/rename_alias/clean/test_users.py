import warnings

import pytest

from greet import greeting
from users import find_user, get_user


def test_find_user():
    assert find_user(1)["name"] == "Ada"
    assert find_user(99) is None


def test_get_user_still_works_but_warns():
    with pytest.warns(DeprecationWarning, match="find_user"):
        assert get_user(1)["name"] == "Ada"


def test_greeting_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert greeting(2) == "Hello, Linus!"
        assert greeting(99) == "Hello, stranger!"
