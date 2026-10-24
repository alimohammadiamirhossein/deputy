import os
import warnings
from pathlib import Path

import pytest

import accounts
from accounts import describe, greeting, monthly_price
from accounts.users import get_user

WORKDIR = Path(os.environ["BENCH_WORKDIR"])


def test_new_name_exported():
    assert accounts.get_user is get_user
    assert "get_user" in accounts.__all__
    assert "get_usr" not in accounts.__all__


def test_behavior_unchanged():
    assert get_user(1)["name"] == "Ada"
    get_user(1)["name"] = "changed"
    assert get_user(1)["name"] == "Ada"
    with pytest.raises(KeyError):
        get_user(99)
    assert monthly_price(1) == 12
    assert monthly_price(2) == 0
    assert greeting(2) == "Hi Lin!"
    assert describe(1) == "Ada <ada@example.com> on pro"


def test_old_name_is_deprecated_alias():
    from accounts.users import get_usr

    with pytest.warns(DeprecationWarning):
        assert get_usr(2) == get_user(2)


def test_helpers_do_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        monthly_price(1)
        greeting(1)
        describe(1)


def test_no_other_code_uses_old_name():
    # Package code only: a test that calls the deprecated alias to check it warns is fine.
    offenders = [
        str(path.relative_to(WORKDIR))
        for path in (WORKDIR / "accounts").glob("*.py")
        if path.name != "users.py" and "get_usr" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
