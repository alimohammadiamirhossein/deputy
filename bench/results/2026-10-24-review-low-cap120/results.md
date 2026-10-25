# Deputy review benchmark

Model `deepseek-ai/DeepSeek-V4.1-Flash-1017`, thinking `low`, lenses: correctness and logic bugs; edge cases, error handling and missing tests.

| Diffs | Reviews | Bug caught / false alarm | ...at major or critical | Two lenses agree | Findings not about a planted bug, per review | Mean cost | Mean time |
|---|---|---|---|---|---|---|---|
| Planted bug | 30 | 30/30 (100%) | 30/30 (100%) | 30/30 (100%) | 0.73 | $0.0016 | 29 s |
| Clean | 40 | 22/40 (55%) | 9/40 (22%) | 8/40 (20%) | 1.35 | $0.0037 | 98 s |

| Lens | Bugs caught | False alarms on clean diffs | ...at major or critical |
|---|---|---|---|
| correctness and logic bugs | 30/30 (100%) | 13/40 (32%) | 5/40 (12%) |
| edge cases, error handling and missing tests | 30/30 (100%) | 18/40 (45%) | 7/40 (18%) |

| Case | Diff | Reviews | Result | Findings (critical / major / minor) |
|---|---|---|---|---|
| config_merge | bug | 5 | caught 5/5 | 7 / 3 / 5 |
| config_merge | clean | 5 | flagged 4/5 | 0 / 1 / 7 |
| format_bytes | bug | 5 | caught 5/5 | 0 / 8 / 2 |
| format_bytes | clean | 5 | flagged 3/5 | 0 / 2 / 3 |
| memoize | bug | 5 | caught 5/5 | 8 / 3 / 6 |
| memoize | clean | 5 | flagged 5/5 | 0 / 8 / 17 |
| pagination | bug | 5 | caught 5/5 | 7 / 3 / 2 |
| pagination | clean | 5 | flagged 0/5 | 0 / 0 / 0 |
| rename_alias | clean | 5 | flagged 0/5 | 0 / 0 / 0 |
| retry | bug | 5 | caught 5/5 | 10 / 0 / 4 |
| retry | clean | 5 | flagged 5/5 | 0 / 1 / 6 |
| type_hints | clean | 5 | flagged 0/5 | 0 / 0 / 0 |
| upload_path | bug | 5 | caught 5/5 | 10 / 0 / 6 |
| upload_path | clean | 5 | flagged 5/5 | 0 / 0 / 9 |

## Findings on clean diffs (54)

Each is a false alarm by construction. Read them: some may be fair minor points.

- **config_merge** #1, correctness and logic bugs: minor at `settings.py:19`: Override *values* are now deep-copied, so an override containing any non-copyable object (lock, socket, open file, connection) makes load() raise instead of storing the object.
- **config_merge** #1, correctness and logic bugs: minor at `settings.py:16`: An empty-dict override, load({"db": {}}), no longer clears the section — it silently returns the full defaults, whereas the old code produced {"db": {}}.
- **config_merge** #3, correctness and logic bugs: minor at `settings.py:19`: load() now deep-copies every non-mergeable override value, so callers that put a non-copyable object or an identity-sensitive sentinel in overrides either get a TypeError or a different object than they passed in; the old code stored the ca
- **config_merge** #3, edge cases, error handling and missing tests: minor at `settings.py:19`: The change deep-copies every non-dict override value into the result, so load() now raises TypeError for override values that are not deep-copyable (locks, sockets, open files, modules, DB/connection objects) — values the previous settings.
- **config_merge** #4, correctness and logic bugs: minor at `settings.py:19`: copy.deepcopy(value) on override values makes load() raise for any non-copyable object, where the previous settings.update(overrides) accepted arbitrary objects.
- **config_merge** #4, edge cases, error handling and missing tests: major at `settings.py:19`: merge now copy.deepcopys every override value, so load() no longer returns the caller's objects — it returns copies, and it raises TypeError for override values that are not deep-copyable (locks, sockets, open files, live clients/pools), wh
- **config_merge** #4, edge cases, error handling and missing tests: minor at `settings.py:16`: An empty-dict override ({"db": {}}) is now a silent no-op that keeps every default, whereas it used to clear the section; there is no longer any way to drop a default key, and no test pins either behavior.
- **config_merge** #5, correctness and logic bugs: minor at `settings.py:19`: A non-dict override is no longer stored as given — it is replaced by copy.deepcopy(value), so objects that are not copyable (locks, sockets, logging.Logger, thread-bound clients) make load() raise, and copyable live objects are silently dup
- **format_bytes** #1, correctness and logic bugs: major at `units.py:19`: The final return f"{size:.1f} {UNITS[-1]}" runs after the TiB→PiB division, so any size at or above 1 EiB is divided one time too many and reported in PiB at 1/1024 of its true value.
- **format_bytes** #1, edge cases, error handling and missing tests: minor at `units.py:18`: format_bytes(n) raises OverflowError instead of returning a size for sufficiently large non-negative ints (e.g. 10400), so it does not honour its contract for "an int >= 0".
- **format_bytes** #2, correctness and logic bugs: minor at `units.py:20`: The unit is chosen by comparing round(size, 1) < 1024, so sizes just below a unit boundary are promoted to the next unit and printed as 1.0 X, hiding up to ~1024 bytes of missing size (e.g. 1048575 bytes and 1048576 bytes both render as 1.0
- **format_bytes** #2, correctness and logic bugs: minor at `test_units.py:10`: The tests never exercise the non-int / zero-boundary contract and never exercise a value that reaches the final return f"{size:.1f} {UNITS[-1]}" through the loop-under-1024 path (only the fall-through huge case is covered), so the boundary 
- **format_bytes** #4, edge cases, error handling and missing tests: major at `units.py:19`: The loop bound UNITS[1:-1] plus the round(size, 1) < 1024 test makes the formatter escalate past the last computed unit and then the final size can be reported in the wrong unit for inputs just below a 1024 boundary — specifically format_by
- **memoize** #1, correctness and logic bugs: major at `cache.py:12`: The cache key is the full argument tuple, so the key space is sku × qty × currency, not just the handful of SKUs — the change's stated justification for a permanent unbounded cache ("the set of SKUs is small") does not hold, because qty is 
- **memoize** #1, correctness and logic bugs: minor at `cache.py:12`: Equivalent calls with different argument styles produce different keys, so quote("melon", 2) and quote("melon", qty=2) are cached separately and the function is recomputed for each spelling; the new test does not detect this because it exer
- **memoize** #1, correctness and logic bugs: minor at `test_pricing.py:17`: test_cache_clear passes even if cache_clear is a no-op, because re-quoting "pear" returns 0.75 whether or not the entry was evicted.
- **memoize** #1, edge cases, error handling and missing tests: major at `cache.py:12`: The cache key is the full argument tuple, so qty — which is not validated or bounded anywhere in quote — is part of the key, and the cache never evicts; a caller-supplied quantity therefore creates an unbounded number of permanent entries.
- **memoize** #1, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: No test in the change actually asserts that caching happens; test_cache_clear is vacuous — it calls quote("pear"), clears, and asserts 0.75, which passes even if @memoize is deleted entirely, and the "depend on every argument" test only che
- **memoize** #1, edge cases, error handling and missing tests: minor at `pricing.py:4`: The "PRICES/CURRENCY_RATES are fixed" invariant is only documentation; both are plain mutable module-level dicts, and once results are memoized, any later mutation (rate refresh, admin price edit, test monkeypatch) is ignored forever becaus
- **memoize** #2, correctness and logic bugs: major at `cache.py:8`: The cache is unbounded not just over the small SKU set but over the whole argument tuple, and qty is an unrestricted integer, so the cache grows with every distinct quantity (and any future parameter) seen for the lifetime of the process.
- **memoize** #2, correctness and logic bugs: minor at `cache.py:12`: Equivalent calls get different cache keys, so the memoization the change claims to add silently misses whenever callers mix positional and keyword style or rely on defaults — quote("melon"), quote("melon", 1) and quote("melon", qty=1) are t
- **memoize** #2, edge cases, error handling and missing tests: major at `cache.py:12`: The cache key is the raw call signature (args, tuple(sorted(kwargs.items()))), so the number of distinct keys is not bounded by the number of SKUs — it grows with every distinct qty the caller passes, and the cache is never bounded or expir
- **memoize** #2, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: test_cache_clear passes even if cache_clear is a no-op, because the value it reads after clearing is the same correct value already stored in the cache.
- **memoize** #3, correctness and logic bugs: minor at `test_pricing.py:10`: The new tests do not test the cache at all — every one of them passes unchanged if @memoize is deleted from pricing.py, so the change's actual behavior (hits, keying, clearing) is unverified.
- **memoize** #3, correctness and logic bugs: minor at `cache.py:8`: The cache never expires and its key includes qty, which on a checkout page is caller/user-controlled, so the key space is not "the small set of SKUs" the design assumes.
- **memoize** #3, edge cases, error handling and missing tests: major at `cache.py:8`: The cache is keyed on the raw call arguments, so it is unbounded in the one dimension the code does not control — qty — and the stated justification ("the set of SKUs is small") does not bound it.
- **memoize** #3, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: test_cache_clear cannot fail — it asserts a value that is correct whether or not the cache was actually cleared, and no test asserts that a repeat call is served from the cache at all.
- **memoize** #3, edge cases, error handling and missing tests: minor at `pricing.py:4`: The "PRICES/CURRENCY_RATES are fixed" premise is not enforced — they are ordinary mutable module-level dicts, and after this change any in-process mutation of them is silently ignored forever by already-cached quotes.
- **memoize** #4, correctness and logic bugs: major at `cache.py:8`: The cache is keyed on the full argument tuple, so its size is bounded by the number of *distinct (sku, qty, currency) triples ever requested*, not by the number of SKUs — and since qty comes from the checkout request, that is unbounded. Eve
- **memoize** #4, correctness and logic bugs: minor at `test_pricing.py:9`: The new tests never assert that the cache is actually hit, and nothing tests that semantically identical calls made positionally vs. by keyword coalesce — they do not: quote("melon", 2) and quote("melon", qty=2) produce different keys, so b
- **memoize** #4, edge cases, error handling and missing tests: major at `cache.py:12`: The cache key is the full argument tuple, so the number of entries is bounded by the number of distinct qty (and currency) values, not by the number of SKUs — the stated justification ("PRICES and CURRENCY_RATES are fixed and the set of SKU
- **memoize** #4, edge cases, error handling and missing tests: minor at `cache.py:12`: Positional and keyword spellings of the same call are cached as different keys, so quote("melon", 2) and quote("melon", qty=2) both execute the function once and occupy two entries, and the same applies to currency; the hit rate on a page t
- **memoize** #4, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: The new tests do not test the change: every assertion would still pass with @memoize deleted, so there is no regression test proving the cache is actually used, and no test covers the failure modes that matter (unbounded growth, positional/
- **memoize** #5, correctness and logic bugs: minor at `cache.py:8`: The cache's cardinality is not "the small set of SKUs" as the change's rationale claims — the key contains every argument, so each distinct qty (and currency) creates a permanent entry that is never evicted.
- **memoize** #5, correctness and logic bugs: minor at `cache.py:12`: The key is not canonical across calling conventions, so quote("melon", 2) and quote("melon", qty=2) get different keys, producing duplicate entries and cache misses for logically identical calls.
- **memoize** #5, edge cases, error handling and missing tests: major at `cache.py:12`: The cache key is built from *all* arguments, not just sku, so it is not bounded by the "small set of SKUs" the lead relies on — qty (and currency) are part of the key and there is no size cap or eviction.
- **memoize** #5, edge cases, error handling and missing tests: minor at `cache.py:12`: Equivalent calls written with positional vs keyword arguments (or with defaults omitted vs. passed explicitly) get different keys and are cached separately, so the memoization mostly misses for precisely the "same arguments" case the PR is 
- **memoize** #5, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: The two new tests pass unchanged if @memoize is deleted, so nothing verifies the behaviour the change introduces (cache hit reuse, or cache_clear actually emptying a populated cache).
- **retry** #1, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The diff's stated deliverable — that push() itself retries ConnectionError up to 3 times with backoff and still surfaces the error — has zero test coverage; every retry test calls retry() directly, bypassing push()'s wiring.
- **retry** #2, edge cases, error handling and missing tests: minor at `test_sync.py:25`: Every new test drives retry() directly; no test exercises push() on an error path, so the actual feature claimed by the change (push retries transient errors) is never tested.
- **retry** #3, correctness and logic bugs: minor at `test_sync.py:25`: The only test that exercises push uses a send that never raises, so the retry behaviour the change is actually adding to push (3 attempts, retry only on ConnectionError, error surfaced after exhaustion) has zero coverage.
- **retry** #3, correctness and logic bugs: minor at `sync.py:7`: sleep=time.sleep is bound at function-definition time, so patching time.sleep after import has no effect on push/retry and the retries sleep for real.
- **retry** #4, edge cases, error handling and missing tests: minor at `test_sync.py:25`: push()'s retry wiring is never exercised — the only push test is the success path, and all retry behaviour is verified against retry() called directly.
- **retry** #5, correctness and logic bugs: major at `test_sync.py:25`: The behavior the change exists to deliver — that push() itself retries with exponential backoff — is never asserted by any test; the new tests exercise the retry.py helper directly and push only on its success path.
- **retry** #5, edge cases, error handling and missing tests: minor at `test_sync.py:30`: Every retry test exercises the helper retry(...) directly; no test ever passes a failing send to push, so the behavior the change was actually made for — push retrying a ConnectionError, stopping after exactly 3 attempts, surfacing the fina
- **upload_path** #1, edge cases, error handling and missing tests: minor at `uploads.py:11`: safe_path only checks containment, never that the target is a regular file, so a name that resolves to a directory *inside* the upload folder passes the check and then blows up in read_bytes() with IsADirectoryError instead of the promised 
- **upload_path** #1, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: No test exercises the actual fixed entry point read_upload with a hostile name; all four rejection tests call safe_path directly, and the fixture contains no subdirectory and no symlink, so the docstring's symlink claim and the "read_upload
- **upload_path** #2, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection test calls safe_path directly, so nothing verifies that the untrusted entry point read_upload actually enforces the check, and the symlink escape the new docstring promises to stop is never exercised.
- **upload_path** #3, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: The suite never exercises a symlink escape and never calls read_upload for any rejected name, so the security property the change exists to provide is not actually pinned by any test.
- **upload_path** #3, edge cases, error handling and missing tests: minor at `uploads.py:11`: The path is validated with resolve() and then re-opened by name with read_bytes(), so the file that is checked is not necessarily the file that is read.
- **upload_path** #4, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection test calls safe_path directly; no test ever asserts that read_upload — the request-facing function named in the requirement — raises ValueError.
- **upload_path** #4, edge cases, error handling and missing tests: minor at `test_uploads.py:25`: test_rejects_absolute_paths cannot distinguish absolute-path handling from the general containment check, and the docstring's claim that an "absolute path" is rejected is false when the absolute path is inside base.
- **upload_path** #5, edge cases, error handling and missing tests: minor at `uploads.py:12`: safe_path only checks containment, never that the resolved target is a file, so a name that resolves to a directory inside the upload folder (e.g. a subdirectory) is returned and read_bytes() then raises IsADirectoryError, an OSError — not 
- **upload_path** #5, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: All rejection tests call safe_path directly, never read_upload, so nothing pins the traversal guarantee on the public entry point the request handler actually uses; a regression that re-introduces (Path(base) / name).read_bytes() in read_up
