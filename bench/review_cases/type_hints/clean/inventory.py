"""Stock levels for the warehouse."""
from __future__ import annotations


class Inventory:
    """Units in stock per SKU. A SKU whose stock drops to zero is forgotten."""

    def __init__(self) -> None:
        self._stock: dict[str, int] = {}

    def add(self, sku: str, qty: int) -> None:
        """Add `qty` units of `sku`. Raise ValueError unless qty is positive."""
        if qty <= 0:
            raise ValueError("qty must be positive")
        self._stock[sku] = self._stock.get(sku, 0) + qty

    def remove(self, sku: str, qty: int) -> None:
        """Take `qty` units of `sku` out of stock. Raise ValueError unless qty is positive and
        at most what is in stock."""
        if qty <= 0:
            raise ValueError("qty must be positive")
        have = self._stock.get(sku, 0)
        if qty > have:
            raise ValueError(f"only {have} of {sku} in stock")
        if qty == have:
            del self._stock[sku]
        else:
            self._stock[sku] = have - qty

    def count(self, sku: str) -> int:
        """Units of `sku` in stock, 0 if there are none."""
        return self._stock.get(sku, 0)

    def low_stock(self, threshold: int) -> list[str]:
        """SKUs with fewer than `threshold` units in stock, sorted. SKUs with no stock are
        forgotten, so they are not listed."""
        return sorted(sku for sku, qty in self._stock.items() if qty < threshold)
