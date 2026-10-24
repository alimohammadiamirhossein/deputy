import pytest

from pager import page_count, paginate


def test_paginate():
    items = list(range(45))
    assert paginate(items, 1) == list(range(20))
    assert paginate(items, 3) == list(range(40, 45))
    assert paginate(items, 4) == []


def test_paginate_rejects_bad_arguments():
    with pytest.raises(ValueError):
        paginate([], 0)
    with pytest.raises(ValueError):
        paginate([], 1, per_page=0)


def test_page_count():
    assert page_count(0) == 0
    assert page_count(1) == 1
    assert page_count(20) == 1
    assert page_count(21) == 2
    assert page_count(45, per_page=20) == 3


def test_page_count_rejects_bad_arguments():
    with pytest.raises(ValueError):
        page_count(-1)
    with pytest.raises(ValueError):
        page_count(10, per_page=0)
