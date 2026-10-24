"""Split result lists into pages for the API."""


def paginate(items, page, per_page=20):
    """Return the items on `page` (1-based)."""
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    start = (page - 1) * per_page
    return items[start:start + per_page]


def page_count(total, per_page=20):
    """How many pages `total` items fill. A partial last page counts; no items means 0 pages."""
    if total < 0:
        raise ValueError("total must be >= 0")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    return (total + per_page - 1) // per_page
