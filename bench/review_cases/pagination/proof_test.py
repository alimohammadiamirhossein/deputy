from pager import page_count


def test_exact_multiples_and_zero():
    assert page_count(0) == 0
    assert page_count(40, per_page=20) == 2
