# Deputy review benchmark

Model `deepseek-ai/DeepSeek-V4.1-Flash-1017`, thinking `low`, lenses: correctness and logic bugs; edge cases, error handling and missing tests.

| Diffs | Reviews | Bug caught / false alarm | ...at major or critical | Two lenses agree | Findings not about a planted bug, per review | Mean cost | Mean time |
|---|---|---|---|---|---|---|---|
| Planted bug | 30 | 30/30 (100%) | 29/30 (97%) | 30/30 (100%) | 0.83 | $0.0017 | 24 s |
| Clean | 40 | 24/40 (60%) | 9/40 (22%) | 10/40 (25%) | 1.27 | $0.0045 | 95 s |

| Lens | Bugs caught | False alarms on clean diffs | ...at major or critical |
|---|---|---|---|
| correctness and logic bugs | 30/30 (100%) | 12/40 (30%) | 5/40 (12%) |
| edge cases, error handling and missing tests | 30/30 (100%) | 22/40 (55%) | 7/40 (18%) |

| Case | Diff | Reviews | Result | Findings (critical / major / minor) |
|---|---|---|---|---|
| config_merge | bug | 5 | caught 5/5 | 9 / 1 / 9 |
| config_merge | clean | 5 | flagged 5/5 | 0 / 4 / 5 |
| format_bytes | bug | 5 | caught 5/5 | 0 / 6 / 5 |
| format_bytes | clean | 5 | flagged 3/5 | 0 / 0 / 3 |
| memoize | bug | 5 | caught 5/5 | 6 / 4 / 6 |
| memoize | clean | 5 | flagged 5/5 | 0 / 8 / 14 |
| pagination | bug | 5 | caught 5/5 | 6 / 4 / 0 |
| pagination | clean | 5 | flagged 1/5 | 0 / 0 / 1 |
| rename_alias | clean | 5 | flagged 1/5 | 0 / 0 / 1 |
| retry | bug | 5 | caught 5/5 | 10 / 3 / 3 |
| retry | clean | 5 | flagged 5/5 | 0 / 0 / 8 |
| type_hints | clean | 5 | flagged 0/5 | 0 / 0 / 0 |
| upload_path | bug | 5 | caught 5/5 | 10 / 0 / 6 |
| upload_path | clean | 5 | flagged 4/5 | 0 / 0 / 7 |

## Findings on clean diffs (51)

Each is a false alarm by construction. Read them: some may be fair minor points.

- **config_merge** #1, edge cases, error handling and missing tests: minor at `settings.py:19`: load() now deep-copies every override value, so an override carrying a non-deep-copyable object (lock, open file, socket, generator, many C-backed handles) raises TypeError where the old settings.update(overrides) accepted it, and the retur
- **config_merge** #2, correctness and logic bugs: major at `settings.py:19`: Override values are now copy.deepcopy-ed instead of inserted as-is, so load() raises TypeError for any non-deepcopyable override value and no longer preserves object identity for the ones it can copy.
- **config_merge** #2, correctness and logic bugs: minor at `settings.py:17`: When the base value and the override value are both dicts, merge returns a plain dict built from the base, so a dict-subclass override (e.g. defaultdict, OrderedDict ordering metadata, an attrs/__slots__-carrying subclass) loses its type an
- **config_merge** #3, edge cases, error handling and missing tests: major at `settings.py:19`: Every non-dict override value is now copy.deepcopy'd, so overrides no longer carry the caller's object through unchanged and values that cannot be deep-copied (locks, loggers, sockets/connections, open files, generators, types.MappingProxyT
- **config_merge** #4, edge cases, error handling and missing tests: major at `settings.py:14`: Overrides are no longer used as-is; they are copy.deepcopyd, so any override value that cannot be deep-copied (or whose identity matters) now fails or is silently cloned at load() time.
- **config_merge** #4, edge cases, error handling and missing tests: minor at `test_settings.py:4`: The untested paths are exactly the ones the change newly defines: adding a section that does not exist in DEFAULTS (the result.get(key) is None half of line 16), and a non-dict override sitting where the default is a dict (e.g. {"db": "sqli
- **config_merge** #5, correctness and logic bugs: minor at `settings.py:18`: Override values are now copy.deepcopy-ed, so load() no longer tolerates non-copyable override values and no longer preserves the identity of objects passed in — both worked with the old settings.update(overrides) shallow copy.
- **config_merge** #5, edge cases, error handling and missing tests: major at `settings.py:19`: Every non-dict override value is now copy.deepcopy-ed, so load() raises TypeError for any non-copyable object in the overrides and silently hands back a *copy* (not the same object) for everything else — both are behavior changes versus the
- **config_merge** #5, edge cases, error handling and missing tests: minor at `test_settings.py:15`: The "defaults are never changed" test only guards one leaf (cache.ttl) and never checks the new failure mode above, nor that merge results don't alias the caller's override dict.
- **format_bytes** #2, edge cases, error handling and missing tests: minor at `units.py:18`: size = n / 1024 raises OverflowError for large-but-valid int inputs (n > ~1.8e308), so the documented contract "n is a byte count (an int >= 0), negative sizes raise ValueError" breaks with an unexpected exception type instead of a clean re
- **format_bytes** #3, correctness and logic bugs: minor at `units.py:18`: size = n / 1024 raises OverflowError for any valid int >= 0 larger than roughly 1.8e311, so format_bytes crashes instead of returning the documented "stay in PiB" result.
- **format_bytes** #4, edge cases, error handling and missing tests: minor at `units.py:14`: The only input guard is if n < 0; anything that is not an int (float, bool, NaN, ±inf) is silently formatted, producing values that are not valid byte counts — e.g. format_bytes(float('nan')) == "nan PiB", format_bytes(float('inf')) == "inf
- **memoize** #1, correctness and logic bugs: minor at `cache.py:12`: The cache is keyed on the raw call shape rather than the logical arguments, so the key space is SKUs × every distinct qty × every currency × call style and grows without bound — the justification "the set of SKUs is small" does not hold.
- **memoize** #1, correctness and logic bugs: minor at `test_pricing.py:17`: No test asserts that caching actually happens, so the suite passes unchanged if memoize is a no-op or if cache_clear never clears anything.
- **memoize** #1, edge cases, error handling and missing tests: major at `cache.py:12`: The cache key is the raw call spelling ((args, tuple(sorted(kwargs.items())))) rather than the bound arguments, so calls that mean exactly the same thing (quote("melon", 2), quote("melon", qty=2), quote("melon", 2, "USD"), quote("melon", 2,
- **memoize** #1, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: No test ever observes a cache *hit*; a memoize that stores nothing at all, or one that stores stale values forever, passes the entire new test suite.
- **memoize** #2, correctness and logic bugs: major at `pricing.py:8`: The cache size is unbounded in the number of distinct qty and currency values, not just SKUs, so repeated checkouts with new quantities grow it indefinitely.
- **memoize** #2, correctness and logic bugs: minor at `cache.py:12`: Equivalent calls that differ only in positional-vs-keyword form get separate cache entries and always miss each other.
- **memoize** #2, edge cases, error handling and missing tests: major at `cache.py:8`: the cache is keyed on *all* arguments, so qty — a number that varies per cart and is effectively unbounded — becomes part of the key, giving a permanent dict entry per distinct quantity rather than per SKU.
- **memoize** #2, edge cases, error handling and missing tests: minor at `pricing.py:8`: the cached result depends on module globals (PRICES, CURRENCY_RATES) that are not in the key, so any later change to a price or rate keeps returning the old quote until someone manually calls quote.cache_clear().
- **memoize** #2, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: neither new test would fail if @memoize were removed entirely, so the change's actual behaviour (serving a stored result, and serving a *fresh* one after a data change) is untested.
- **memoize** #3, correctness and logic bugs: major at `cache.py:12`: The cache is keyed on the full argument tuple, and one of those arguments is qty — caller-supplied user input — so the cache is not bounded by "the set of SKUs is small"; it is bounded only by the number of distinct (sku, qty, currency) tri
- **memoize** #3, edge cases, error handling and missing tests: major at `cache.py:8`: The cache is keyed on the full argument tuple, so its cardinality is bounded by the number of distinct (sku, qty, currency) combinations, not by the number of SKUs — qty is an unbounded integer, and nothing ever evicts entries.
- **memoize** #3, edge cases, error handling and missing tests: minor at `cache.py:12`: Calls that are logically identical but use different argument spellings get different cache keys, so the memoization does not deduplicate the repeated calls it was introduced for.
- **memoize** #4, correctness and logic bugs: major at `cache.py:12`: The cache is keyed on the raw call arguments, which include the caller-supplied qty, so the number of live entries is not "the small set of SKUs" — it is skus × every distinct quantity × every distinct currency, and the entry is kept foreve
- **memoize** #4, correctness and logic bugs: minor at `test_pricing.py:10`: The new tests only assert correct return values, so they pass even if memoization never hits (or if cache were rebuilt per call); nothing verifies that a repeated call actually returns the cached result or that the key includes each argumen
- **memoize** #4, edge cases, error handling and missing tests: major at `cache.py:13`: The cache is bounded by the number of distinct qty values, not by the SKU set, so the "small fixed key space" justification for an eviction-free cache does not hold; every distinct quantity permanently adds an entry.
- **memoize** #4, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: None of the new tests would fail if memoize were replaced by a no-op decorator, so the behavior the change exists to add (results are actually reused) is untested.
- **memoize** #4, edge cases, error handling and missing tests: minor at `pricing.py:4`: The "constants never change" premise is asserted, not enforced: PRICES and CURRENCY_RATES are ordinary public mutable dicts, and any runtime update (price change, rate refresh, test monkeypatching) silently yields stale quotes forever.
- **memoize** #5, correctness and logic bugs: major at `cache.py:8`: The cache is unbounded and its key includes qty, which is caller-supplied and has no fixed domain, so a long-lived process accumulates one entry per distinct (sku, qty, currency) ever requested.
- **memoize** #5, correctness and logic bugs: minor at `pricing.py:4`: PRICES and CURRENCY_RATES are plain mutable module globals, and memoizing quote permanently freezes the first computed total, so any later mutation is silently ignored.
- **memoize** #5, correctness and logic bugs: minor at `test_pricing.py:17`: Neither new test would fail if the cache never hit or cache_clear were a no-op, so the memoization behaviour is effectively untested.
- **memoize** #5, edge cases, error handling and missing tests: minor at `cache.py:12`: The cache key is the raw call spelling, not the bound arguments, so quote("melon"), quote("melon", 1), quote("melon", qty=1) and quote("melon", qty=1, currency="USD") are four separate entries — and since qty is part of the key, the number 
- **memoize** #5, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: test_cache_clear cannot fail for the behaviour it names — with cache_clear implemented as lambda: None (or removed entirely) the test would still pass, because it only re-checks a value that is correct whether or not the cache was emptied.
- **pagination** #2, edge cases, error handling and missing tests: minor at `pager.py:14`: page_count validates only the sign of its arguments, so non-integer values silently produce a non-integer (or NaN) page count instead of an error, unlike paginate which fails loudly on non-integer input.
- **rename_alias** #2, edge cases, error handling and missing tests: minor at `greet.py:2`: The rename silently removes the greet.get_user module attribute, so any caller doing from greet import get_user / greet.get_user(...) now fails with ImportError/AttributeError instead of getting the deprecated alias the change is supposed t
- **retry** #1, edge cases, error handling and missing tests: minor at `test_sync.py:25`: Nothing tests the behavior the change actually claims to add — no test drives push with a failing send, so push's retry count, its backoff, and its give-up-and-propagate path are entirely unverified.
- **retry** #2, correctness and logic bugs: minor at `test_sync.py:25`: The change's actual subject — that push() retries 3 times with backoff and only retries ConnectionError — has no test; every retry test exercises the retry module directly, so push's wiring can regress silently.
- **retry** #2, edge cases, error handling and missing tests: minor at `test_sync.py:25`: Nothing tests that push itself retries — all retry behaviour is tested against the retry helper directly, and the only push test uses a send that never raises.
- **retry** #3, correctness and logic bugs: minor at `test_sync.py:25`: The behavior this change exists to add — push() retrying ConnectionError three times with backoff — is never exercised through push(); every retry test calls retry() directly.
- **retry** #3, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The behavior the change exists to deliver — push() retrying on ConnectionError, backing off, and propagating other errors / the final error — is never exercised through push(); the new tests only call the generic helper retry() directly.
- **retry** #4, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The behavior the change exists to provide — push() retrying ConnectionError up to 3 times, propagating other errors immediately, and re-raising after all attempts fail — is never exercised through push(); every new test calls retry() direct
- **retry** #5, correctness and logic bugs: minor at `test_sync.py:25`: None of the tests exercise push's retry behaviour — they only test the retry helper directly, so the contract the change exists to deliver is unverified.
- **retry** #5, edge cases, error handling and missing tests: minor at `test_sync.py:25`: Nothing tests push() with a failing send, so the feature the diff exists to deliver (push retrying, and push propagating the error after exhaustion) is entirely unverified.
- **upload_path** #1, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection test calls the new helper safe_path directly; not one test calls read_upload with a traversal name, so the request-facing function the change is actually meant to harden is unguarded by the suite.
- **upload_path** #2, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: The security fix is only tested at the helper level; no test proves that read_upload — the function that actually takes the request-supplied name — rejects an escaping name, and the symlink case the docstring advertises is not tested at all
- **upload_path** #3, correctness and logic bugs: minor at `test_uploads.py:19`: All three traversal tests call safe_path directly; none exercise read_upload, the function that actually contained the vulnerability.
- **upload_path** #3, edge cases, error handling and missing tests: minor at `uploads.py:19`: safe_path only rejects paths that are outside base or equal to it, so a request-supplied name that resolves to a *directory inside* the upload folder passes validation and read_upload then raises IsADirectoryError instead of ValueError.
- **upload_path** #3, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection test calls safe_path directly, so the tests would still pass if read_upload (the documented request-URL entry point named in the task) stopped calling it.
- **upload_path** #5, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection case tests safe_path directly, so the fix's actual contract (read_upload must raise ValueError for escaping names) is not pinned by any test — only the happy path calls read_upload (line 16).
- **upload_path** #5, edge cases, error handling and missing tests: minor at `uploads.py:12`: A name that resolves to a subdirectory inside base (e.g. "sub") passes the check and is returned, then read_upload raises IsADirectoryError/NotADirectoryError instead of the documented ValueError.
