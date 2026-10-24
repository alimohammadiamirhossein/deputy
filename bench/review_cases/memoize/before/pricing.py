"""Price quotes for the checkout page."""

PRICES = {"apple": 0.5, "pear": 0.75, "melon": 3.0}
CURRENCY_RATES = {"USD": 1.0, "EUR": 0.92, "CAD": 1.37}


def quote(sku, qty=1, currency="USD"):
    """Total price for `qty` units of `sku`, converted to `currency` and rounded to cents."""
    return round(PRICES[sku] * qty * CURRENCY_RATES[currency], 2)
