import pytest

from inventory import Inventory


def test_add_remove_and_count():
    stock = Inventory()
    stock.add("bolt", 5)
    stock.add("bolt", 3)
    stock.remove("bolt", 2)
    assert stock.count("bolt") == 6
    stock.remove("bolt", 6)
    assert stock.count("bolt") == 0


def test_remove_more_than_in_stock():
    stock = Inventory()
    stock.add("nut", 1)
    with pytest.raises(ValueError, match="only 1 of nut"):
        stock.remove("nut", 2)


def test_quantities_must_be_positive():
    stock = Inventory()
    with pytest.raises(ValueError):
        stock.add("nut", 0)
    with pytest.raises(ValueError):
        stock.remove("nut", -1)


def test_low_stock():
    stock = Inventory()
    stock.add("bolt", 50)
    stock.add("nut", 3)
    stock.add("washer", 1)
    assert stock.low_stock(5) == ["nut", "washer"]
