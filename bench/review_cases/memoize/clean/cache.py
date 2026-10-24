"""A small memoization decorator."""
import functools


def memoize(fn):
    """Cache fn's results by its arguments, which must be hashable. The cache never expires;
    call `cache_clear()` on the decorated function to empty it."""
    cache = {}

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = fn(*args, **kwargs)
        return cache[key]

    wrapper.cache_clear = cache.clear
    return wrapper
