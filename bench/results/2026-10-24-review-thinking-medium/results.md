# Deputy review benchmark

Model `deepseek-ai/DeepSeek-V4.1-Flash-1017`, thinking `medium`, lenses: correctness and logic bugs; edge cases, error handling and missing tests.

| Diffs | Reviews | Bug caught / false alarm | ...at major or critical | Two lenses agree | Findings not about a planted bug, per review | Mean cost | Mean time |
|---|---|---|---|---|---|---|---|
| Planted bug | 26 | 26/26 (100%) | 26/26 (100%) | 26/26 (100%) | 0.92 | $0.0021 | 36 s |
| Clean | 30 | 18/30 (60%) | 6/30 (20%) | 8/30 (27%) | 1.60 | $0.0056 | 115 s |

| Lens | Bugs caught | False alarms on clean diffs | ...at major or critical |
|---|---|---|---|
| correctness and logic bugs | 26/26 (100%) | 12/30 (40%) | 3/30 (10%) |
| edge cases, error handling and missing tests | 26/26 (100%) | 14/30 (47%) | 6/30 (20%) |

| Case | Diff | Reviews | Result | Findings (critical / major / minor) |
|---|---|---|---|---|
| config_merge | bug | 5 | caught 5/5 | 6 / 6 / 6 |
| config_merge | clean | 4 | flagged 4/4 | 0 / 1 / 6 |
| format_bytes | bug | 5 | caught 5/5 | 0 / 8 / 4 |
| format_bytes | clean | 3 | flagged 0/3 | 0 / 0 / 0 |
| memoize | bug | 4 | caught 4/4 | 7 / 1 / 8 |
| memoize | clean | 4 | flagged 4/4 | 0 / 8 / 15 |
| pagination | bug | 4 | caught 4/4 | 2 / 6 / 1 |
| pagination | clean | 4 | flagged 2/4 | 0 / 0 / 1 |
| rename_alias | clean | 4 | flagged 1/4 | 0 / 0 / 1 |
| retry | bug | 4 | caught 4/4 | 8 / 3 / 4 |
| retry | clean | 4 | flagged 4/4 | 0 / 1 / 8 |
| type_hints | clean | 4 | flagged 0/4 | 0 / 0 / 0 |
| upload_path | bug | 4 | caught 4/4 | 7 / 1 / 7 |
| upload_path | clean | 3 | flagged 3/3 | 0 / 0 / 6 |

## Findings on clean diffs (48)

Each is a false alarm by construction. Read them: some may be fair minor points.

- **config_merge** #1, edge cases, error handling and missing tests: major at `settings.py:19`: merge now copy.deepcopys every override value, so live runtime objects passed by a deployment are no longer stored by reference — they are either duplicated (silently creating a second copy of stateful state) or raise TypeError at startup.
- **config_merge** #1, edge cases, error handling and missing tests: minor at `settings.py:16`: an override that supplies an empty dict for a section is a silent no-op, so a deployment cannot clear or empty a section — load({"cache": {}}) returns {"ttl": 300}, and the exact bug class this change is meant to prevent (dropped/reported k
- **config_merge** #2, correctness and logic bugs: minor at `settings.py:19`: The new code deep-copies override *values*, so load() now raises for any non-deep-copyable override and returns clones instead of the caller's objects, where the old settings.update(overrides) stored the references as-is.
- **config_merge** #3, edge cases, error handling and missing tests: minor at `settings.py:19`: Every override value is now copy.deepcopy'd, which makes load() fail on any non-deep-copyable value and silently changes object identity for callers — neither limitation is stated in the new docstring, and the previous implementation accept
- **config_merge** #4, correctness and logic bugs: minor at `settings.py:19`: Non-dict override values are no longer passed through by reference — they are copy.deepcopy'd, so load({"x": obj})["x"] is a different object than obj, and any non-deep-copyable value (lock, socket, DB connection, file handle, generator, ob
- **config_merge** #4, edge cases, error handling and missing tests: minor at `settings.py:19`: Override *values* are now deep-copied, so load() no longer returns the caller's own objects: values that cannot be deep-copied make load() raise, and identity of every override value is silently lost.
- **config_merge** #4, edge cases, error handling and missing tests: minor at `settings.py:16`: An override that is an empty dict (or whose nested dict matches the base key) is now a silent no-op, so a caller can no longer reset or clear a section with {}.
- **memoize** #1, correctness and logic bugs: major at `cache.py:12`: The cache is unbounded and its key space is not "small set of SKUs" — the key is (args, kwargs), so every distinct qty (and every distinct call shape) creates a permanent entry; qty is an unvalidated, caller-supplied checkout value.
- **memoize** #1, correctness and logic bugs: minor at `cache.py:12`: Logically identical calls produce different keys, so the cache misses exactly where call sites differ in style and each variant occupies its own slot.
- **memoize** #1, correctness and logic bugs: minor at `test_pricing.py:10`: The new tests never assert that anything was cached, so they pass unchanged if memoize is replaced by a no-op decorator — the change's entire behavior is untested.
- **memoize** #1, edge cases, error handling and missing tests: major at `cache.py:12`: The cache is unbounded and keyed on qty, an unvalidated caller-supplied quantity, so every distinct quantity requested on the checkout page permanently adds a new dict entry — the "small set of SKUs" argument does not bound the key space.
- **memoize** #1, edge cases, error handling and missing tests: minor at `cache.py:12`: The same logical quote is cached under different keys depending on whether arguments are passed positionally or by keyword, so the cache multiplies entries and misses exactly the repeats it was added to catch.
- **memoize** #1, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: The new tests only assert returned values, so they pass unchanged if the decorator memoizes nothing at all — the actual behaviour the change introduces (caching, cache_clear, cache growth) is untested.
- **memoize** #2, correctness and logic bugs: minor at `cache.py:12`: The cache key is the raw (args, sorted(kwargs)) pair, not a canonical binding of the call to the function signature, so the same logical request written positionally, by keyword, or with an explicit default creates separate cache entries.
- **memoize** #2, correctness and logic bugs: minor at `test_pricing.py:10`: No test exercises the decorator’s only new behavior — reusing a cached result — so a broken or no-op cache still passes the whole suite, and the test named for argument-dependence does not actually compare the keyword-form entry against a f
- **memoize** #2, edge cases, error handling and missing tests: major at `pricing.py:8`: The justification for an unbounded, never-evicting cache only counts SKUs, but the cache key also includes qty and currency, so the entry count grows with every distinct quantity requested, not with the size of PRICES.
- **memoize** #2, edge cases, error handling and missing tests: major at `test_pricing.py:10`: None of the new tests actually exercises caching, so the entire new behavior is untested — deleting @memoize (or making cache_clear a no-op) leaves the suite green.
- **memoize** #2, edge cases, error handling and missing tests: minor at `cache.py:12`: Semantically identical calls with different call styles get different cache keys, so quote("melon", 2) and quote("melon", qty=2) each compute and each store an entry.
- **memoize** #3, correctness and logic bugs: major at `cache.py:8`: The cache is an unbounded dict keyed on every argument, including qty, so any caller that passes a varying quantity permanently adds a new entry that is never evicted — and quote() does no validation of qty.
- **memoize** #3, correctness and logic bugs: minor at `cache.py:12`: The key does not normalize positional vs. keyword arguments, so quote("melon", 2) and quote("melon", qty=2) are two different entries with identical values, and the same happens for quote("pear", 4, "EUR") vs quote("pear", 4, currency="EUR"
- **memoize** #3, correctness and logic bugs: minor at `test_pricing.py:10`: None of the added tests can detect whether caching happens at all, and none exercise the sorted(kwargs.items()) logic — delete @memoize (or delete the sorted() call) and the whole suite still passes.
- **memoize** #3, edge cases, error handling and missing tests: major at `cache.py:12`: The cache key is the full call signature — including qty, which is an unrestricted integer supplied by the caller — so the number of entries is not bounded by "a small set of SKUs" and the cache never shrinks.
- **memoize** #3, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: No test verifies that results are actually cached or that cache_clear() clears anything, so the whole feature can regress to a no-op and the suite stays green.
- **memoize** #4, correctness and logic bugs: major at `cache.py:12`: The cache never expires while PRICES/CURRENCY_RATES are plain mutable module-level dicts, so any runtime update to a price or rate is silently ignored forever after the first quote for that key.
- **memoize** #4, correctness and logic bugs: minor at `cache.py:12`: The key treats positional and keyword spellings of the same call as different arguments, so logically identical quotes are computed and stored separately instead of hitting the cache.
- **memoize** #4, correctness and logic bugs: minor at `cache.py:8`: The cache is unbounded and, per the justification, keyed only by "a small set of SKUs", but the actual key includes the free-form qty and the call spelling, so the key space is not small and entries are never evicted.
- **memoize** #4, correctness and logic bugs: minor at `test_pricing.py:10`: Neither new test can detect a broken or absent cache, so the memoization this change adds is untested.
- **memoize** #4, edge cases, error handling and missing tests: major at `cache.py:8`: The "cache never expires / SKU set is small" premise only bounds sku; the cache key also contains qty (and currency), and qty is an arbitrary caller-supplied number, so the cache grows without bound over the life of the process.
- **memoize** #4, edge cases, error handling and missing tests: minor at `cache.py:12`: Equivalent calls with the same arguments produce different cache keys depending on whether an argument is passed positionally or by keyword, so the same quote is computed and stored twice (or more).
- **memoize** #4, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: None of the new tests would fail if @memoize were removed, and none cover the failure modes above (unbounded growth, invalidation of PRICES/CURRENCY_RATES, positional-vs-keyword identity).
- **pagination** #3, correctness and logic bugs: unknown at `?`: (no summary)
- **pagination** #4, correctness and logic bugs: minor at `pager.py:20`: page_count silently accepts non-integer total/per_page and returns a float instead of an int page count.
- **rename_alias** #3, edge cases, error handling and missing tests: minor at `test_users.py:14`: The diff deletes assert get_user(99) is None and the replacement alias test only exercises the found-user path, so the deprecated wrapper's behavior for unknown ids is now completely untested.
- **retry** #1, correctness and logic bugs: minor at `test_sync.py:25`: Nothing in the suite exercises push's retry behaviour, so the feature the change exists to add could be deleted or mis-wired and all tests still pass.
- **retry** #1, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The behavior the change exists to deliver — push() retrying ConnectionError up to 3 times — is never exercised through push(); every retry test calls retry() directly, so a broken wiring in sync.py:10 would still pass the suite.
- **retry** #2, edge cases, error handling and missing tests: major at `test_sync.py:25`: The retry behaviour that is the entire point of this diff is never exercised through push; test_push_returns_the_response only covers a send that succeeds on the first call, so the push → retry wiring (attempts=3, sleep=sleep, error propaga
- **retry** #2, edge cases, error handling and missing tests: minor at `retry.py:5`: Only ConnectionError and its subclasses are retried; TimeoutError (which is socket.timeout since Python 3.10) is a *sibling* of ConnectionError under OSError, so a send that hangs and times out — the most common form of "briefly unreachable
- **retry** #3, edge cases, error handling and missing tests: minor at `test_sync.py:25`: Nothing tests that push() — the function whose behavior this change actually changes — retries, so a regression that silently disables retries in push still passes the whole suite.
- **retry** #3, edge cases, error handling and missing tests: minor at `test_sync.py:37`: The test named "raises the last error" cannot detect if the *wrong* (e.g. first) error is raised, because every attempt raises an indistinguishable ConnectionError("down").
- **retry** #4, correctness and logic bugs: minor at `test_sync.py:25`: Nothing in the suite exercises push's retry path, so the feature the change delivers is untested end-to-end.
- **retry** #4, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The production change — push() retrying — has no test that drives a failure through push, so every new behavior (3 attempts, exponential backoff, non-retryable errors propagating) can regress without the suite going red.
- **retry** #4, edge cases, error handling and missing tests: minor at `test_sync.py:37`: test_retry_raises_the_last_error_when_every_attempt_fails only asserts the exception *type* (pytest.raises(ConnectionError)) and the call count, so it passes even if the implementation raises the *first* failure instead of the last.
- **upload_path** #1, correctness and logic bugs: minor at `test_uploads.py:19`: The new regression tests call safe_path directly and never exercise read_upload, so the exact vulnerability being fixed (read_upload joining the raw request name onto base) can be reintroduced without any test failing.
- **upload_path** #1, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection test calls the new helper safe_path(base, name) directly; there is no test that the function the change actually modified — read_upload — raises ValueError for an escaping name (the only read_upload test, line 15-16, is the 
- **upload_path** #2, correctness and logic bugs: minor at `test_uploads.py:19`: Every rejection test calls the helper safe_path directly; no test ever calls read_upload — the function that actually serves request-supplied names — with a traversal name, so the suite does not pin the fix at the public entry point.
- **upload_path** #3, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection test calls the internal helper safe_path(...), never read_upload(...), so nothing in the suite proves the request-facing function rejects traversal.
- **upload_path** #3, edge cases, error handling and missing tests: minor at `uploads.py:8`: The docstring promises symlink rejection and rejection of "an absolute path", but no test covers a symlink, and an absolute path that resolves inside base is accepted (the check is purely "outside root", not "absolute").
- **upload_path** #3, edge cases, error handling and missing tests: minor at `uploads.py:11`: The check and the read are two separate path lookups, so a component swapped for a symlink between resolve() (line 11) and read_bytes() (line 19) escapes the check.

## Errors (14)

- config_merge/clean #5: the provider is unavailable: Connection error.
- format_bytes/clean #4: the provider is unavailable: Connection error.
- format_bytes/clean #5: the provider is unavailable: Connection error.
- memoize/bug #5: the provider is unavailable: Connection error.
- memoize/clean #5: the provider is unavailable: Connection error.
- pagination/bug #5: the provider is unavailable: Connection error.
- pagination/clean #5: the provider is unavailable: Connection error.
- rename_alias/clean #5: the provider is unavailable: Connection error.
- retry/bug #5: the provider is unavailable: Connection error.
- retry/clean #5: the provider is unavailable: Connection error.
- type_hints/clean #5: the provider is unavailable: Connection error.
- upload_path/bug #5: the provider is unavailable: Connection error.
- upload_path/clean #4: the provider is unavailable: Connection error.
- upload_path/clean #5: the provider is unavailable: Connection error.
