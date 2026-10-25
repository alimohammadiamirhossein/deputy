# Deputy review benchmark

Model `deepseek-ai/DeepSeek-V4.1-Flash-1017`, thinking `low`, lenses: correctness and logic bugs; edge cases, error handling and missing tests.

| Diffs | Reviews | Bug caught / false alarm | ...at major or critical | Two lenses agree | Findings not about a planted bug, per review | Mean cost | Mean time |
|---|---|---|---|---|---|---|---|
| Planted bug | 30 | 30/30 (100%) | 30/30 (100%) | 30/30 (100%) | 0.97 | $0.0016 | 29 s |
| Clean | 40 | 22/40 (55%) | 10/40 (25%) | 8/40 (20%) | 1.25 | $0.0039 | 107 s |

| Lens | Bugs caught | False alarms on clean diffs | ...at major or critical |
|---|---|---|---|
| correctness and logic bugs | 30/30 (100%) | 8/40 (20%) | 4/40 (10%) |
| edge cases, error handling and missing tests | 30/30 (100%) | 22/40 (55%) | 10/40 (25%) |

| Case | Diff | Reviews | Result | Findings (critical / major / minor) |
|---|---|---|---|---|
| config_merge | bug | 5 | caught 5/5 | 7 / 3 / 8 |
| config_merge | clean | 5 | flagged 4/5 | 0 / 2 / 6 |
| format_bytes | bug | 5 | caught 5/5 | 0 / 6 / 7 |
| format_bytes | clean | 5 | flagged 3/5 | 0 / 1 / 3 |
| memoize | bug | 5 | caught 5/5 | 8 / 2 / 3 |
| memoize | clean | 5 | flagged 5/5 | 0 / 9 / 13 |
| pagination | bug | 5 | caught 5/5 | 8 / 5 / 3 |
| pagination | clean | 5 | flagged 0/5 | 0 / 0 / 0 |
| rename_alias | clean | 5 | flagged 1/5 | 0 / 0 / 2 |
| retry | bug | 5 | caught 5/5 | 10 / 0 / 8 |
| retry | clean | 5 | flagged 5/5 | 0 / 1 / 8 |
| type_hints | clean | 5 | flagged 1/5 | 0 / 0 / 1 |
| upload_path | bug | 5 | caught 5/5 | 9 / 1 / 7 |
| upload_path | clean | 5 | flagged 3/5 | 0 / 1 / 3 |

## Findings on clean diffs (50)

Each is a false alarm by construction. Read them: some may be fair minor points.

- **config_merge** #1, correctness and logic bugs: minor at `settings.py:19`: load() now deep-copies every override value, so override values that are not deep-copyable raise TypeError, and values that are copied lose their identity, where the old settings.update(overrides) passed them through by reference.
- **config_merge** #1, correctness and logic bugs: minor at `settings.py:16`: an override of {} for a section no longer clears it — load({"db": {}}) now returns the full default db mapping instead of an empty one, and there is no way to remove keys from a nested section.
- **config_merge** #1, edge cases, error handling and missing tests: major at `settings.py:19`: Every override value is now copy.deepcopy-ed, so any config value that is not deep-copyable (locks, sockets, DB connections, open files, modules, thread locals, event loops) makes load() raise instead of being stored as before.
- **config_merge** #2, correctness and logic bugs: minor at `settings.py:19`: Every non-dict override value is now copy.deepcopy-ed, so load() raises TypeError for override values that are not deep-copyable, and callers no longer get back the same object they passed in.
- **config_merge** #2, edge cases, error handling and missing tests: major at `settings.py:19`: Non-dict override values are now copy.deepcopy'd instead of being used as given, so load() breaks caller-provided objects: object identity is lost, resources are silently cloned, and values that cannot be deep-copied make load() raise TypeE
- **config_merge** #2, edge cases, error handling and missing tests: minor at `settings.py:16`: A nested section can no longer be emptied or have a key removed: load({"cache": {}}) silently keeps {"ttl": 300}, and the only alternative ({"cache": None}) changes the section's type, which will break any code doing settings["cache"]["ttl"
- **config_merge** #4, edge cases, error handling and missing tests: minor at `settings.py:19`: load() now deep-copies every override value, so overrides containing objects that cannot be deep-copied (locks, sockets, DB connections, memoryview, file handlers, sqlite3.Connection, generators) raise TypeError instead of being stored as-i
- **config_merge** #5, edge cases, error handling and missing tests: minor at `settings.py:19`: load() now deep-copies every override value, which the old dict.update(overrides) did not; deployment overrides that carry non-deep-copyable objects now raise TypeError at startup, and overrides that carry live objects silently lose identit
- **format_bytes** #1, edge cases, error handling and missing tests: major at `units.py:19`: Sizes just below the TiB boundary are reported in PiB — format_bytes(10245 - 1) returns "1.0 PiB" instead of "1.0 TiB" (or "1024.0 TiB").
- **format_bytes** #2, edge cases, error handling and missing tests: minor at `units.py:20`: Unit promotion is decided on the *rounded* value (round(size, 1) < 1024), so any size in the top ~0.05% of a unit is reported as 1.0 of the next unit — e.g. 10243 - 1 bytes (1 GiB minus one byte) prints "1.0 GiB", and the new test asserts t
- **format_bytes** #3, edge cases, error handling and missing tests: minor at `units.py:18`: For any int above the float range (spec-legal input, since the contract is only "an int >= 0"), n / 1024 raises OverflowError instead of returning a PiB string.
- **format_bytes** #3, edge cases, error handling and missing tests: minor at `test_units.py:10`: The only behaviour the loop's tricky round(size, 1) < 1024 promotion rule actually controls — values in [1023.95, 1024) of a unit being re-expressed in the next unit — is never tested at that threshold, and exact unit boundaries are unteste
- **memoize** #1, correctness and logic bugs: major at `cache.py:12`: The cache is keyed on the raw call arguments, so its key space is not the small set of SKUs but (sku, qty, currency) — including unbounded qty — and it is never evicted, so it grows without limit on a per-checkout-page hot path.
- **memoize** #1, correctness and logic bugs: minor at `cache.py:12`: Arguments are not canonicalized, so quote("melon", 2), quote("melon", qty=2) and quote("melon", 2, "USD") produce three separate entries for the same computation, multiplying cache growth and making the "same arguments" hit rate depend on c
- **memoize** #1, edge cases, error handling and missing tests: major at `cache.py:8`: The cache is keyed on the raw call arguments rather than bound parameter values, so its size is not bounded by the SKU set as the change assumes — every distinct qty, currency, and positional/keyword spelling of the same logical call create
- **memoize** #1, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: No test verifies that memoization actually happens or that cache_clear() does anything, so the tests pass unchanged if memoize is a pass-through decorator and if cache_clear is a no-op.
- **memoize** #2, correctness and logic bugs: major at `cache.py:8`: The cache is unbounded and its key is (args, kwargs), so it grows with every distinct qty and currency value, not just with the small set of SKUs — the premise "the set of SKUs is small, so an unbounded cache is fine" is false.
- **memoize** #2, correctness and logic bugs: minor at `cache.py:12`: Equivalent calls with different argument-passing styles get different keys, so the cache does not actually dedupe the repeated calls it was added for, and it multiplies the unbounded-key problem above.
- **memoize** #2, correctness and logic bugs: minor at `pricing.py:4`: PRICES and CURRENCY_RATES are mutable module-level dicts, but the memoized results are never invalidated when they change, so a price update is silently ignored forever.
- **memoize** #2, edge cases, error handling and missing tests: major at `cache.py:8`: The cache is keyed on the full argument tuple, so qty — an unbounded, caller-supplied integer — is part of every key; the "the set of SKUs is small, so unbounded is fine" rationale does not hold, and the process accumulates one dict entry p
- **memoize** #2, edge cases, error handling and missing tests: minor at `cache.py:12`: quote("melon", 2) and quote("melon", qty=2) are different keys for identical results, so the same quote is computed and stored twice.
- **memoize** #2, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: Neither new test would fail if memoization were removed entirely or if cache_clear() were a no-op, so the two behaviours the change actually introduces (a hit, and a clear) are untested.
- **memoize** #3, correctness and logic bugs: minor at `cache.py:12`: The cache key is the raw (args, sorted(kwargs)) pair, so logically identical calls — defaults not passed, or the same values passed positionally vs. by keyword — land in different cache entries and are recomputed and stored separately.
- **memoize** #3, edge cases, error handling and missing tests: major at `cache.py:8`: The cache key includes every argument, including qty, so the cache is not bounded by "small set of SKUs" — it grows one entry per distinct (sku, qty, currency) triple and never expires.
- **memoize** #3, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: test_cache_clear asserts nothing that fails if cache_clear() is a no-op, so the one non-obvious branch of the decorator (cache.py:17) is effectively untested.
- **memoize** #4, correctness and logic bugs: major at `cache.py:12`: The cache key is not call-signature aware, so logically identical calls like quote("pear"), quote("pear", 1), quote("pear", qty=1), quote("pear", 1, "USD") and quote("pear", 1, currency="USD") are five separate entries — every spelling of a
- **memoize** #4, correctness and logic bugs: minor at `cache.py:8`: The cache is unbounded and its key includes qty, so distinct quantity values keep accumulating entries for the process lifetime; the "SKUs are few" justification only bounds the SKU dimension and ignores that qty/currency multiply the key s
- **memoize** #4, edge cases, error handling and missing tests: major at `cache.py:8`: The cache is unbounded but its key space is not "a small set of SKUs" — the key includes qty and currency, and qty is an unvalidated caller-supplied number, so distinct cart quantities (and float quantities) mint new cache entries forever.
- **memoize** #4, edge cases, error handling and missing tests: minor at `cache.py:14`: Memoizing quote changes behaviour for existing callers that mutate the module-level PRICES / CURRENCY_RATES tables: the first result for a key is now frozen for the process lifetime, so later edits to the tables are silently ignored.
- **memoize** #4, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: None of the new tests can distinguish a working cache from no cache, and test_cache_clear is vacuous — it would pass with cache_clear() deleted entirely.
- **memoize** #5, correctness and logic bugs: major at `cache.py:8`: The "unbounded, never-expiring" cache is keyed on qty, which is a per-request checkout value, not a small fixed domain — so the cache grows without bound on a long-lived checkout process, contradicting the justification that "the set of SKU
- **memoize** #5, correctness and logic bugs: minor at `test_pricing.py:17`: test_cache_clear cannot fail even if cache_clear is a no-op, because the asserted value is identical whether quote("pear") is recomputed or served from the stale cache.
- **memoize** #5, edge cases, error handling and missing tests: major at `cache.py:12`: The cache is keyed on the raw call arguments, and quote's second argument qty comes from the cart/checkout request and is unbounded and unvalidated, so the "never expires, never bounded" cache grows one permanent entry per distinct (sku, qt
- **memoize** #5, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: The new tests do not actually verify memoization or the properties the cache relies on; they only compare return values, which pass identically with the decorator removed (the pre-existing test_quote already covers those numbers).
- **rename_alias** #3, edge cases, error handling and missing tests: minor at `users.py:14`: The deprecation notice is emitted as DeprecationWarning, which Python's default warning filters ignore outside __main__, so the alias is silent for real callers — the change ships a "warns" deprecation that in practice never warns anyone.
- **rename_alias** #3, edge cases, error handling and missing tests: minor at `test_users.py:14`: Coverage regressed: the deleted test_get_user asserted get_user(99) is None, but the replacement deprecated-alias test only checks the hit case, so nothing tests that the alias still forwards the miss/None result.
- **retry** #1, correctness and logic bugs: minor at `test_sync.py:25`: No test exercises push()'s new retry path — the only push test uses a send that always succeeds, so the retry-on-ConnectionError behavior that push is being changed to provide is never actually verified through push.
- **retry** #1, edge cases, error handling and missing tests: minor at `test_sync.py:25`: No test exercises push's retry behavior — the only push test uses a send that always succeeds, so the actual change ("push retries up to 3 times and still raises after 3 failures") is untested.
- **retry** #2, edge cases, error handling and missing tests: major at `test_sync.py:25`: The change's headline behavior — push() itself retrying ConnectionError and propagating other errors — is never exercised by any test; every retry test calls retry() directly, bypassing sync.push.
- **retry** #2, edge cases, error handling and missing tests: minor at `test_sync.py:37`: The test named "raises_the_last_error" only asserts that *some* ConnectionError escapes, so an implementation that re-raised the first attempt's exception (or a synthesized one) would pass unchanged.
- **retry** #3, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The new behavior lives entirely in push, but no test ever makes push fail and retry — so push's 3-attempt limit, its error propagation, and even the fact that it forwards the injected sleep are all unverified.
- **retry** #4, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The behavior actually being added to push() — retry on ConnectionError, propagate other errors immediately, re-raise when all 3 attempts fail — has no test at all; every new test calls retry() directly instead, so the push() wiring is unver
- **retry** #4, edge cases, error handling and missing tests: minor at `retry.py:11`: retry() validates only attempts < 1; a delay that makes sleep raise (e.g. negative) aborts the loop with the sleep error, so the caller never receives the last ConnectionError the docstring promises.
- **retry** #5, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The change's headline behavior — push() retrying a ConnectionError and giving up after 3 attempts — is never exercised; every retry test calls retry() directly, so nothing would fail if push stopped retrying.
- **retry** #5, edge cases, error handling and missing tests: minor at `test_sync.py:37`: test_retry_raises_the_last_error_when_every_attempt_fails cannot actually tell the last error from an earlier one, so the documented "the last error is raised" contract is unverified.
- **type_hints** #1, edge cases, error handling and missing tests: minor at `inventory.py:6`: The change newly documents "A SKU whose stock drops to zero is forgotten" and "SKUs with no stock are forgotten, so they are not listed" as class contract, but no test pins that behaviour — the existing test after a full removal only assert
- **upload_path** #1, edge cases, error handling and missing tests: major at `test_uploads.py:19`: Every rejection case is asserted against the helper safe_path directly; no test asserts that the security-relevant entry point read_upload rejects a traversal name, so the tests pass even if the fix in read_upload is reverted.
- **upload_path** #2, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: The suite never exercises the symlink-escape path, even though safe_path's docstring (uploads.py:8-9) explicitly promises it and it is the one property the existing tests cannot pin down.
- **upload_path** #4, edge cases, error handling and missing tests: minor at `uploads.py:12`: safe_path only rejects paths outside base and base itself; a name resolving to a *directory* (or other non-regular file) inside base is accepted, and read_bytes() then raises IsADirectoryError, not the ValueError the function promises.
- **upload_path** #4, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection test calls safe_path directly; none exercises read_upload, which is the only function whose body this diff changed, and the docstring's symlink guarantee has no test at all.
