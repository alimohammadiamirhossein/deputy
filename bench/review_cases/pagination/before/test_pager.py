import pytest

from pager import paginate


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
