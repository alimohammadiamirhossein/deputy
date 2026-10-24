"""Split result lists into pages for the API."""


def paginate(items, page, per_page=20):
    """Return the items on `page` (1-based)."""
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    start = (page - 1) * per_page
    return items[start:start + per_page]
