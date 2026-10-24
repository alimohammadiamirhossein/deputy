"""Stock levels for the warehouse."""


class Inventory:
    def __init__(self):
        self._stock = {}

    def add(self, sku, qty):
        if qty <= 0:
            raise ValueError("qty must be positive")
        self._stock[sku] = self._stock.get(sku, 0) + qty

    def remove(self, sku, qty):
        if qty <= 0:
            raise ValueError("qty must be positive")
        have = self._stock.get(sku, 0)
        if qty > have:
            raise ValueError(f"only {have} of {sku} in stock")
        if qty == have:
            del self._stock[sku]
        else:
            self._stock[sku] = have - qty

    def count(self, sku):
        return self._stock.get(sku, 0)

    def low_stock(self, threshold):
        return sorted(sku for sku, qty in self._stock.items() if qty < threshold)
