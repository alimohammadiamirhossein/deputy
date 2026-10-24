"""Formatting helpers for the storage dashboard."""

UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]


def format_count(n):
    """Thousands separators: 1234567 -> '1,234,567'."""
    return f"{n:,}"


def format_bytes(n):
    """Size with binary units and one decimal: 1023 -> '1023 B', 1024 -> '1.0 KiB',
    1536 -> '1.5 KiB'. Sizes past the largest unit stay in PiB."""
    if n < 0:
        raise ValueError("size must be >= 0")
    if n < 1024:
        return f"{n} B"
    size = n / 1024
    for unit in UNITS[1:-1]:
        if round(size, 1) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} {UNITS[-1]}"
