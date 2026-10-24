# Deputy review benchmark

Model `deepseek-ai/DeepSeek-V4.1-Flash-1017`, thinking `high`, lenses: correctness and logic bugs; edge cases, error handling and missing tests.

| Diffs | Reviews | Bug caught / false alarm | ...at major or critical | Two lenses agree | Findings not about a planted bug, per review | Mean cost | Mean time |
|---|---|---|---|---|---|---|---|
| Planted bug | 30 | 30/30 (100%) | 30/30 (100%) | 30/30 (100%) | 1.23 | $0.0022 | 55 s |
| Clean | 39 | 23/39 (59%) | 7/39 (18%) | 10/39 (26%) | 1.56 | $0.0067 | 245 s |

| Lens | Bugs caught | False alarms on clean diffs | ...at major or critical |
|---|---|---|---|
| correctness and logic bugs | 30/30 (100%) | 14/39 (36%) | 5/39 (13%) |
| edge cases, error handling and missing tests | 30/30 (100%) | 20/39 (51%) | 6/39 (15%) |

| Case | Diff | Reviews | Result | Findings (critical / major / minor) |
|---|---|---|---|---|
| config_merge | bug | 5 | caught 5/5 | 8 / 2 / 8 |
| config_merge | clean | 5 | flagged 5/5 | 0 / 2 / 9 |
| format_bytes | bug | 5 | caught 5/5 | 0 / 9 / 3 |
| format_bytes | clean | 5 | flagged 1/5 | 0 / 0 / 1 |
| memoize | bug | 5 | caught 5/5 | 9 / 2 / 7 |
| memoize | clean | 5 | flagged 5/5 | 0 / 9 / 22 |
| pagination | bug | 5 | caught 5/5 | 4 / 7 / 3 |
| pagination | clean | 5 | flagged 1/5 | 0 / 0 / 1 |
| rename_alias | clean | 5 | flagged 3/5 | 0 / 0 / 4 |
| retry | bug | 5 | caught 5/5 | 10 / 1 / 8 |
| retry | clean | 5 | flagged 5/5 | 0 / 0 / 9 |
| type_hints | clean | 5 | flagged 1/5 | 0 / 0 / 1 |
| upload_path | bug | 5 | caught 5/5 | 10 / 0 / 11 |
| upload_path | clean | 4 | flagged 2/4 | 0 / 0 / 3 |

## Findings on clean diffs (61)

Each is a false alarm by construction. Read them: some may be fair minor points.

- **config_merge** #1, edge cases, error handling and missing tests: major at `settings.py:19`: merge now copy.deepcopys every override *value* it installs, so an override that is not deep-copyable (lock, socket, open file, DB connection, SSLContext, …) makes load() raise TypeError at startup, and objects that used to be installed by 
- **config_merge** #1, edge cases, error handling and missing tests: minor at `settings.py:16`: An override of {} for a section is now a silent no-op, so a deployment that previously cleared a section by passing an empty dict keeps the built-in values instead.
- **config_merge** #2, correctness and logic bugs: minor at `settings.py:19`: load() now deep-copies every override *value* as well as the defaults, so it raises TypeError on values that are not deep-copyable and silently returns copies of objects callers previously got by reference.
- **config_merge** #2, edge cases, error handling and missing tests: minor at `settings.py:19`: copy.deepcopy(value) on non-dict override values does not "replace the value" as the docstring claims — it substitutes a *copy*, so object-valued overrides lose identity and non-copyable overrides now make load() raise, where the old settin
- **config_merge** #3, correctness and logic bugs: minor at `settings.py:19`: Override *values* are deep-copied, so load() no longer "replaces the value" with the caller's object: non-copyable override values now raise TypeError, and every mutable override is silently detached from the object the caller passed in.
- **config_merge** #3, edge cases, error handling and missing tests: minor at `settings.py:15`: load() no longer accepts everything dict.update accepted, and now deep-copies every override value, so inputs that used to work now raise at call time.
- **config_merge** #4, correctness and logic bugs: minor at `settings.py:19`: Non-dict override values are deep-copied into the result instead of being stored as-is, so load() now returns a different object than the caller passed and raises TypeError for values that cannot be deep-copied (locks, sockets, file handles
- **config_merge** #4, edge cases, error handling and missing tests: minor at `settings.py:16`: The merge gate is isinstance(value, dict), so an override section supplied as any other Mapping (e.g. types.MappingProxyType, collections.UserDict, configparser.SectionProxy) is replaced wholesale instead of merged, silently dropping the si
- **config_merge** #4, edge cases, error handling and missing tests: minor at `settings.py:19`: copy.deepcopy(value) makes load() raise TypeError for any non-copyable object in the deployment's overrides, which the previous settings.update(overrides) accepted by reference, and silently duplicates objects that callers may expect to sha
- **config_merge** #4, edge cases, error handling and missing tests: minor at `test_settings.py:4`: The suite never tests the second half of the documented invariant ("Neither argument is modified") nor the empty-section / brand-new-section cases, so a regression to result[key] = value (no copy of override values) would pass all three tes
- **config_merge** #5, correctness and logic bugs: major at `settings.py:19`: merge now deepcopys every non-dict override value, so load() raises TypeError for overrides that hold non-copyable objects (locks, sockets, file handles, connection pools, generators) and no longer returns the same object the caller passed 
- **format_bytes** #1, correctness and logic bugs: minor at `units.py:18`: format_bytes raises OverflowError for very large non-negative ints (e.g. 10400) instead of returning a formatted string, even though the documented contract accepts any int >= 0.
- **memoize** #1, correctness and logic bugs: major at `cache.py:8`: The cache is unbounded and its key includes qty, which is a per-order value rather than one of the "small set of SKUs", so the cache size is not bounded by the small fixed dictionaries — it grows by one permanent entry per distinct (sku, qt
- **memoize** #1, correctness and logic bugs: minor at `cache.py:13`: The check-then-read sequence is not atomic, so a concurrent cache_clear() between the membership test and the final lookup makes quote raise KeyError for a key that was just present.
- **memoize** #1, correctness and logic bugs: minor at `test_pricing.py:10`: None of the new tests would fail if memoize did no caching at all, and test_cache_clear would also pass if cache_clear did nothing, so the actual behavior introduced by this change is untested.
- **memoize** #1, edge cases, error handling and missing tests: major at `cache.py:12`: The cache key is built from the raw call shape, key = (args, tuple(sorted(kwargs.items()))), so the same logical call produces different keys depending on whether arguments were passed positionally or by keyword — exactly the dedupe this ch
- **memoize** #1, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: Neither new test can distinguish a working memoizer from a decorator that caches nothing, so a regression in cache.py would ship green.
- **memoize** #1, edge cases, error handling and missing tests: minor at `cache.py:8`: The "SKUs are a small set, so unbounded is fine" premise is wrong for this key: qty is caller-supplied and included in the key, so the cache is unbounded in quantity values, not in SKUs.
- **memoize** #2, correctness and logic bugs: major at `cache.py:8`: The cache is keyed on the full argument tuple, which includes qty, so the "SKU set is small" argument does not bound the cache at all — one permanent entry is created per distinct qty ever seen, with no eviction.
- **memoize** #2, correctness and logic bugs: minor at `pricing.py:4`: Results are now frozen at first call, so any change to PRICES/CURRENCY_RATES after the first quote for a given key silently returns the old price; before this change every call re-read the dicts.
- **memoize** #2, correctness and logic bugs: minor at `cache.py:12`: Equivalent calls written positionally vs. by keyword produce different keys, so they miss each other's entries — the exact repeated-call pattern the change is meant to exploit.
- **memoize** #2, correctness and logic bugs: minor at `test_pricing.py:10`: No test asserts that memoization actually happens, and test_cache_clear passes even if caching or clearing is broken.
- **memoize** #2, edge cases, error handling and missing tests: major at `cache.py:8`: The cache is unbounded but its key is not limited to the small SKU set — qty (an unvalidated integer) and the call shape are both part of the key, so a caller can mint unlimited distinct entries and the process grows without bound.
- **memoize** #2, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: None of the new tests actually prove the memoization works — they all pass against a memoize that never caches, and the one assertion meant to exercise a cache hit (line 14) only hits when an earlier test already populated the entry.
- **memoize** #2, edge cases, error handling and missing tests: minor at `pricing.py:4`: The cached result is a function of mutable module globals (PRICES, CURRENCY_RATES) that are not part of the cache key, and the cache never expires, so any price/rate update produces permanently stale quotes with no invalidation path in pric
- **memoize** #3, correctness and logic bugs: major at `cache.py:8`: The cache is keyed on every argument, so qty — an unbounded, caller-supplied number — multiplies the key space; the "set of SKUs is small" premise bounds only sku, so the cache is not bounded and never expires.
- **memoize** #3, correctness and logic bugs: minor at `cache.py:12`: The key does not canonicalize call style, so quote("melon", 2) and quote("melon", qty=2) — the same logical call — produce two different keys and are both computed and stored.
- **memoize** #3, correctness and logic bugs: minor at `test_pricing.py:10`: The test named "depends_on_every_argument" never varies a positional argument while holding the others fixed, so it does not actually cover the arguments it claims to.
- **memoize** #3, correctness and logic bugs: minor at `test_pricing.py:17`: test_cache_clear passes whether or not cache_clear() does anything.
- **memoize** #3, edge cases, error handling and missing tests: major at `cache.py:12`: The cache is unbounded, and its key is (args, tuple(sorted(kwargs.items()))), so it is keyed on qty and currency as well as sku — the "the set of SKUs is small" justification does not bound the cache at all.
- **memoize** #3, edge cases, error handling and missing tests: minor at `cache.py:12`: The key is not normalized to the call signature, so semantically identical calls with positional vs. keyword arguments get separate entries and never share a hit.
- **memoize** #3, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: The new tests do not test that anything is cached; they all pass if @memoize is deleted or the wrapper simply calls fn(*args, kwargs) every time.
- **memoize** #4, correctness and logic bugs: minor at `cache.py:8`: The cache is keyed on the *full argument tuple*, not on SKU, so it is not bounded by "the set of SKUs is small" — it grows by one entry per distinct (sku, qty, currency) ever requested, forever, with no eviction.
- **memoize** #4, correctness and logic bugs: minor at `test_pricing.py:10`: None of the new tests would fail if memoization did nothing, so the behavior this change adds is entirely unverified.
- **memoize** #4, edge cases, error handling and missing tests: major at `cache.py:12`: The cache key includes the full argument tuple, so it is bounded only by the number of distinct qty values callers send — qty is caller-controlled and unbounded, so the "never expires" cache grows without limit.
- **memoize** #4, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: test_cache_clear passes even if cache_clear is a no-op, so the only test of the new public API verifies nothing.
- **memoize** #4, edge cases, error handling and missing tests: minor at `cache.py:12`: The key is not canonical, so logically identical calls with different calling conventions are cached as separate entries (quote("melon", 2) vs quote("melon", qty=2)), doubling the entry count and missing the dedupe the change exists for.
- **memoize** #5, correctness and logic bugs: major at `cache.py:8`: The cache is keyed on the full call arguments, so it grows with every distinct qty (and currency) a caller passes, not just with the small set of SKUs — the "SKU set is small, so unbounded is fine" justification does not bound this cache at
- **memoize** #5, correctness and logic bugs: minor at `test_pricing.py:17`: test_cache_clear cannot fail: quote("pear") returns the same 0.75 whether or not the cache was actually emptied, so it gives no coverage of cache_clear.
- **memoize** #5, correctness and logic bugs: minor at `cache.py:12`: Equivalent calls with defaults vs. explicit arguments (and keyword vs. positional form) get separate cache entries, so quote("apple"), quote("apple", 1), quote("apple", 1, "USD") and quote(sku="apple") are four misses for the same computati
- **memoize** #5, edge cases, error handling and missing tests: major at `cache.py:12`: The cache key is the full argument tuple, so qty — an unbounded numeric parameter — is part of the key; the justification "the set of SKUs is small" does not hold, and the cache grows without bound for the process lifetime.
- **memoize** #5, edge cases, error handling and missing tests: minor at `cache.py:12`: Equivalent calls that differ only in positional-vs-keyword style or in explicit-vs-default arguments get different keys, so the "same arguments" the change targets miss the cache and create duplicate entries.
- **memoize** #5, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: Neither new test asserts that caching happens, so the suite would still pass if the decorator cached nothing or if cache_clear() were a no-op.
- **pagination** #5, edge cases, error handling and missing tests: minor at `pager.py:14`: page_count accepts non-integer total/per_page and then returns a float (or an off-by-one count), instead of rejecting them the way it rejects out-of-range values.
- **rename_alias** #2, edge cases, error handling and missing tests: minor at `test_users.py:14`: The get_user(99) is None assertion was deleted from the deprecated-alias test and not replaced, so the alias's miss path — the half of "no other behavior change" that the alias must preserve — is no longer covered by any test.
- **rename_alias** #3, edge cases, error handling and missing tests: minor at `users.py:14`: DeprecationWarning is ignored by Python's default warning filters, so the "deprecated alias that warns" silently does nothing for exactly the callers it is meant to migrate — anyone calling users.get_user() from a module other than __main__
- **rename_alias** #4, edge cases, error handling and missing tests: minor at `users.py:14`: The alias warns with DeprecationWarning, which Python ignores by default unless the call originates in __main__, so most callers of get_user will never see the deprecation notice that the change is supposed to give them.
- **rename_alias** #4, edge cases, error handling and missing tests: minor at `test_users.py:14`: The rewritten alias test drops the not-found assertion the old test had, so the suite no longer checks that the deprecated path still returns None for an unknown id.
- **retry** #1, correctness and logic bugs: minor at `test_sync.py:25`: Nothing tests push itself retrying on ConnectionError or propagating other errors, so the wiring in push is unverified — attempts=1 (or a different retry_on) in sync.py:10 would leave the entire suite green.
- **retry** #1, edge cases, error handling and missing tests: minor at `test_sync.py:25`: Every new test exercises retry() directly; no test calls push with a send that fails, so the actual behavior the change adds — push retrying on ConnectionError and giving up after 3 attempts — is unverified.
- **retry** #2, edge cases, error handling and missing tests: minor at `test_sync.py:25`: Every retry assertion targets the new retry() helper directly; the only push() test uses a send that succeeds on the first call, so push()'s own wiring (attempt count, sleep forwarding, retry_on default) is never exercised.
- **retry** #3, correctness and logic bugs: minor at `test_sync.py:25`: The retry behaviour that was actually requested for push() has no test; every retry test exercises retry.retry directly, and the only push test is a first-try-success case, so the wiring in sync.py can be broken without any test failing.
- **retry** #3, edge cases, error handling and missing tests: minor at `test_sync.py:25`: Nothing tests the behavior the change actually delivers — that push() retries a ConnectionError from send three times and propagates other errors — so the wiring in sync.py is unverified.
- **retry** #4, correctness and logic bugs: minor at `test_sync.py:25`: The only test of push is a first-attempt success; nothing exercises the retry/backoff/propagation behavior that this change actually adds.
- **retry** #4, correctness and logic bugs: minor at `test_sync.py:37`: test_retry_raises_the_last_error_when_every_attempt_fails cannot distinguish the last error from the first, because flaky(5) raises an identical ConnectionError("down") on every attempt.
- **retry** #5, correctness and logic bugs: minor at `test_sync.py:25`: No test exercises push with a send that raises, so the retry behaviour that is the whole point of the change is unverified at the push level.
- **retry** #5, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The change's actual deliverable — push() retrying ConnectionError — is never tested; every new test calls retry() directly, and the only push() test is the happy path.
- **type_hints** #5, edge cases, error handling and missing tests: minor at `inventory.py:34`: The new docstrings assert that depleted SKUs are "forgotten" and therefore never listed by low_stock, but nothing tests that assertion — and it is a contract that contradicts the natural reading of "fewer than threshold units in stock" (a 0
- **upload_path** #2, edge cases, error handling and missing tests: minor at `test_uploads.py:15`: The only test that touches read_upload (the function fed by the request URL) uses a benign name, while every traversal assertion calls safe_path directly — so the suite passes with the vulnerability reintroduced.
- **upload_path** #3, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every new negative test passes even if safe_path stops resolving symlinks, so the one guarantee the docstring calls out ("or a symlink") is completely untested, and the security boundary read_upload itself is never exercised on a rejecting 
- **upload_path** #3, edge cases, error handling and missing tests: minor at `uploads.py:12`: A name that resolves to a *directory* inside the upload folder passes validation (the message says "not a file in the upload folder", but file-ness is never checked), so read_upload fails later with IsADirectoryError instead of ValueError.

## Errors (1)

- upload_path/clean #5: the provider is unavailable: Request timed out.
