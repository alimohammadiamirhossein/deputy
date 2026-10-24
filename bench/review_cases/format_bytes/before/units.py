"""Formatting helpers for the storage dashboard."""


def format_count(n):
    """Thousands separators: 1234567 -> '1,234,567'."""
    return f"{n:,}"
