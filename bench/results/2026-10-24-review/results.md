# Deputy review benchmark

Model `deepseek-ai/DeepSeek-V4.1-Flash-1017`, thinking `high`, lenses: correctness and logic bugs; edge cases, error handling and missing tests.

| Diffs | Reviews | Bug caught / false alarm | ...at major or critical | Two lenses agree | Findings not about a planted bug, per review | Mean cost | Mean time |
|---|---|---|---|---|---|---|---|
| Planted bug | 30 | 30/30 (100%) | 30/30 (100%) | 30/30 (100%) | 1.40 | $0.0020 | 50 s |
| Clean | 39 | 23/39 (59%) | 11/39 (28%) | 12/39 (31%) | 1.85 | $0.0064 | 208 s |

| Lens | Bugs caught | False alarms on clean diffs | ...at major or critical |
|---|---|---|---|
| correctness and logic bugs | 30/30 (100%) | 13/39 (33%) | 6/39 (15%) |
| edge cases, error handling and missing tests | 30/30 (100%) | 22/39 (56%) | 10/39 (26%) |

| Case | Diff | Reviews | Result | Findings (critical / major / minor) |
|---|---|---|---|---|
| config_merge | bug | 5 | caught 5/5 | 10 / 0 / 8 |
| config_merge | clean | 5 | flagged 4/5 | 0 / 3 / 10 |
| format_bytes | bug | 5 | caught 5/5 | 0 / 10 / 3 |
| format_bytes | clean | 4 | flagged 1/4 | 0 / 0 / 2 |
| memoize | bug | 5 | caught 5/5 | 6 / 4 / 10 |
| memoize | clean | 5 | flagged 5/5 | 0 / 9 / 18 |
| pagination | bug | 5 | caught 5/5 | 6 / 4 / 4 |
| pagination | clean | 5 | flagged 0/5 | 0 / 0 / 0 |
| rename_alias | clean | 5 | flagged 2/5 | 0 / 0 / 4 |
| retry | bug | 5 | caught 5/5 | 10 / 2 / 9 |
| retry | clean | 5 | flagged 5/5 | 0 / 5 / 13 |
| type_hints | clean | 5 | flagged 1/5 | 0 / 0 / 1 |
| upload_path | bug | 5 | caught 5/5 | 10 / 1 / 10 |
| upload_path | clean | 5 | flagged 5/5 | 0 / 0 / 7 |

## Findings on clean diffs (72)

Each is a false alarm by construction. Read them: some may be fair minor points.

- **config_merge** #1, correctness and logic bugs: minor at `settings.py:19`: Override *values* are now deep-copied, so load() raises TypeError for any override value that cannot be pickled/copied (locks, sockets, DB connections, open files), where the previous settings.update(overrides) accepted it by reference.
- **config_merge** #1, edge cases, error handling and missing tests: minor at `settings.py:16`: An empty-dict section override ({"db": {}}) is now a silent no-op that yields the full default section, and there is no way at all to clear a section's keys.
- **config_merge** #1, edge cases, error handling and missing tests: minor at `test_settings.py:11`: The tests never exercise the isinstance(result.get(key), dict) half of the guard on settings.py:16 (a dict override over a non-dict or absent default), nor that the returned settings are independent of the caller's override dicts.
- **config_merge** #3, correctness and logic bugs: minor at `settings.py:19`: The change deep-copies *override* values, so load() now raises on any override value that is not deep-copyable and silently returns a different object than the caller passed, where the old settings.update(overrides) accepted the value as-is
- **config_merge** #3, edge cases, error handling and missing tests: major at `settings.py:19`: Every override value is now copy.deepcopyd, so load() no longer "replaces the value" with the caller's object — it stores a copy, and it raises TypeError for any override value that cannot be deep-copied.
- **config_merge** #3, edge cases, error handling and missing tests: minor at `settings.py:16`: isinstance(value, dict) and isinstance(result.get(key), dict) only recognize dict subclasses, so an override built from any other mapping (e.g. types.MappingProxyType, an omegaconf/attrs-style config object) silently replaces the whole sect
- **config_merge** #3, edge cases, error handling and missing tests: minor at `test_settings.py:15`: No test pins the "neither argument is modified / result does not alias the overrides" half of merge's contract, so a regression to a shallow merge would still pass the whole suite.
- **config_merge** #4, correctness and logic bugs: minor at `settings.py:19`: The change now deep-copies every override value, which the old code never did and the task spec does not require ("any non-dict override still replaces the value"), so override objects are no longer passed through as-is and non-copyable obj
- **config_merge** #4, edge cases, error handling and missing tests: major at `settings.py:19`: load() now deep-copies every non-dict override value, so overrides that are objects rather than primitives either crash load() (non-copyable objects) or come back as a different, duplicated object instead of the one the caller passed.
- **config_merge** #4, edge cases, error handling and missing tests: minor at `settings.py:16`: an empty-dict override no longer clears a section, and there is now no way to remove a key that exists in DEFAULTS — load({"db": {}}) returns the full default db instead of {}, which is what it returned before the change.
- **config_merge** #5, edge cases, error handling and missing tests: major at `settings.py:19`: Non-dict overrides are no longer stored as-is — they are copy.deepcopy'd, so object-valued overrides lose identity and can crash load() outright.
- **config_merge** #5, edge cases, error handling and missing tests: minor at `settings.py:16`: isinstance(value, dict) treats any non-dict mapping as a scalar, so a Mapping override silently replaces the whole section — reintroducing exactly the data loss this change is meant to fix.
- **config_merge** #5, edge cases, error handling and missing tests: minor at `test_settings.py:15`: The tests never check the two isolation properties this change actually introduces a risk to: that load does not mutate the caller's overrides mapping, and that two successive load() results do not share nested objects.
- **format_bytes** #2, correctness and logic bugs: minor at `units.py:20`: The promotion test uses the *rounded* size, so any byte count in the top ~0.05 of a unit is relabeled in the next unit — e.g. 1,048,575 B (1 MiB − 1) is reported as "1.0 MiB", and 1,073,741,823 B as "1.0 GiB".
- **format_bytes** #2, correctness and logic bugs: minor at `units.py:18`: Any int above the float range (≈1.8e308) raises OverflowError instead of returning a PiB string, although the contract is "an int >= 0".
- **memoize** #1, correctness and logic bugs: major at `pricing.py:8`: The cache is keyed on *all* arguments including qty, which is caller-controlled on a checkout page, so the entry count is not bounded by the small SKU set and the dict grows forever with no eviction.
- **memoize** #1, correctness and logic bugs: minor at `test_pricing.py:17`: test_cache_clear cannot fail: it asserts the same value the cached call already returned, so it passes even if cache_clear does nothing.
- **memoize** #1, correctness and logic bugs: minor at `cache.py:12`: The key is built before the wrapped function runs, so any unhashable argument raises TypeError from the decorator instead of reaching quote's body, and semantically identical calls with positional vs keyword arguments never share a cache en
- **memoize** #1, edge cases, error handling and missing tests: major at `cache.py:8`: The cache is unbounded and its key space is *not* limited by the SKU set — key = (args, tuple(sorted(kwargs.items()))) includes qty, which is an arbitrary caller-supplied number, so every distinct quantity creates a new permanent entry.
- **memoize** #1, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: test_cache_clear cannot fail: it asserts quote("pear") == 0.75 after clearing, but 0.75 is also exactly what the *cached* value is, so the test passes even if cache_clear is a no-op.
- **memoize** #2, correctness and logic bugs: major at `cache.py:8`: The cache is unbounded but its key is not limited to the small SKU set — it includes qty (and currency), so every distinct quantity produces a permanent new entry, turning the decorator into a memory leak in a long-lived checkout process.
- **memoize** #2, correctness and logic bugs: minor at `cache.py:12`: quote("melon", 2) and quote("melon", qty=2) are logically the same call but produce different keys, so the second form always recomputes and stores a duplicate entry instead of hitting the cache.
- **memoize** #2, correctness and logic bugs: minor at `test_pricing.py:17`: test_cache_clear cannot fail — it asserts a value that is identical whether or not cache_clear() does anything, so a broken/no-op cache_clear passes the suite.
- **memoize** #2, edge cases, error handling and missing tests: major at `cache.py:8`: The cache never expires and is keyed only on arguments, so any change to PRICES or CURRENCY_RATES after the first call is silently ignored for the life of the process.
- **memoize** #2, edge cases, error handling and missing tests: minor at `cache.py:12`: The cache is unbounded and its key space is not bounded by the SKU set — qty and currency are part of the key, so every distinct quantity (including float quantities) adds a permanent entry.
- **memoize** #2, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: test_cache_clear cannot fail — it would pass even if cache_clear were a no-op.
- **memoize** #3, correctness and logic bugs: major at `cache.py:8`: The cache is unbounded but its key includes qty, so the "SKU set is small" argument does not bound the cache — every distinct quantity ever quoted becomes a permanent entry.
- **memoize** #3, correctness and logic bugs: minor at `cache.py:12`: Semantically identical calls made with positional vs keyword arguments hash to different keys, so they never share a cache entry.
- **memoize** #3, correctness and logic bugs: minor at `test_pricing.py:10`: Neither new test can distinguish a cache hit from a cache miss, so the added coverage does not test the feature being added.
- **memoize** #3, correctness and logic bugs: minor at `pricing.py:8`: The decorator makes quote depend on a snapshot of the mutable module globals PRICES/CURRENCY_RATES, so any later mutation of those dicts yields stale prices for previously quoted arguments.
- **memoize** #3, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: The new tests cannot detect the cache being broken — test_cache_clear passes whether or not anything is cleared, and no test fails if @memoize is deleted entirely.
- **memoize** #3, edge cases, error handling and missing tests: minor at `cache.py:12`: The cache key is not a normalized form of the call, so equivalent calls miss and the cache is not bounded by the small SKU set as the change's rationale assumes.
- **memoize** #4, correctness and logic bugs: major at `cache.py:12`: The memo cache is keyed on every argument value, including qty, which is not part of the "small SKU set" the lead's rationale relies on, so the cache is unbounded in practice and grows by one entry per distinct (sku, qty, currency) seen on 
- **memoize** #4, correctness and logic bugs: minor at `test_pricing.py:10`: No test demonstrates that caching actually happens, so the change's stated purpose is untested and the tests would pass unchanged if @memoize were removed.
- **memoize** #4, edge cases, error handling and missing tests: major at `cache.py:12`: The cache is unbounded, but its key includes qty, so the key space is sku × qty × currency, not "the small set of SKUs" — distinct quantities each create a permanent entry.
- **memoize** #4, edge cases, error handling and missing tests: minor at `test_pricing.py:17`: test_cache_clear cannot fail: after quote.cache_clear() the recomputed value is identical to the cached one, so the assertion passes even if cache_clear is a no-op.
- **memoize** #4, edge cases, error handling and missing tests: minor at `cache.py:12`: The cache key is argument-only, so the cached result silently outlives any change to PRICES/CURRENCY_RATES; the "fixed at module load" assumption is not enforced anywhere.
- **memoize** #5, correctness and logic bugs: major at `cache.py:8`: The cache is keyed on the full argument tuple, so its size is bounded by the number of distinct (sku, qty, currency) triples ever requested — not by the number of SKUs — and qty is an unbounded, caller-supplied number.
- **memoize** #5, correctness and logic bugs: minor at `test_pricing.py:10`: The new tests cannot detect the failure modes of this decorator — they assert only return values, which are identical with and without memoization.
- **memoize** #5, edge cases, error handling and missing tests: major at `cache.py:12`: The cache is keyed on *every* argument, including qty, so the entry count is #skus × #distinct qty × #currencies — not "one entry per SKU" — and the cache never expires.
- **memoize** #5, edge cases, error handling and missing tests: minor at `cache.py:12`: The same logical call caches under two different keys depending on call style, so the cache misses on exactly the repeated calls it was added to serve.
- **memoize** #5, edge cases, error handling and missing tests: minor at `test_pricing.py:10`: No test asserts that a cache *hit* happens, so a memoize that never caches (or caches wrongly by object identity) passes the whole suite.
- **rename_alias** #1, edge cases, error handling and missing tests: minor at `greet.py:2`: Replacing from users import get_user with from users import find_user silently deletes the greet.get_user name that the old import created, so callers that imported the deprecated alias via greet now fail immediately instead of getting the 
- **rename_alias** #1, edge cases, error handling and missing tests: minor at `test_users.py:14`: The diff deletes the existing assert get_user(99) is None assertion, leaving the deprecated alias's "not found" path completely untested, so a mutation of the alias body that changes the miss result would pass the whole suite.
- **rename_alias** #2, edge cases, error handling and missing tests: minor at `greet.py:2`: The change silently removes the greet.get_user attribute, which the old from users import get_user had bound as a re-export, so any caller or test that did from greet import get_user or monkeypatch.setattr(greet, "get_user", ...) now fails 
- **rename_alias** #2, edge cases, error handling and missing tests: minor at `test_users.py:14`: The diff deletes the only assertion that get_user returns None for a missing id (get_user(99) is None from the old test_get_user) and replaces it with find_user(99) is None, so the deprecated alias's not-found path — the whole point of "the
- **retry** #1, correctness and logic bugs: major at `sync.py:4`: push now depends on a top-level module retry that the change does not add to version control, so committing only the tracked edits leaves the import broken or silently bound to the third-party retry package, whose retry() has a different si
- **retry** #1, correctness and logic bugs: minor at `test_sync.py:25`: No test exercises push's retry path; every retry assertion calls retry directly, so the actual change to push is unverified.
- **retry** #1, edge cases, error handling and missing tests: major at `sync.py:4`: The commit only modifies sync.py and test_sync.py; the new retry.py module that from retry import retry requires is untracked, so a clean checkout of this change cannot import sync at all.
- **retry** #1, edge cases, error handling and missing tests: major at `test_sync.py:30`: Every retry test exercises retry() directly; nothing tests that push() actually retries on ConnectionError, gives up after 3 attempts, or lets other errors through, so the wiring the task is about is unverified.
- **retry** #1, edge cases, error handling and missing tests: minor at `retry.py:5`: retry_on=(ConnectionError,) matches only the builtin ConnectionError (plus its OSError subclasses such as ConnectionResetError); a client library's own ConnectionError (e.g. requests.exceptions.ConnectionError, which derives from RequestExc
- **retry** #2, correctness and logic bugs: minor at `test_sync.py:25`: The feature's three stated guarantees are only tested on the retry() helper; nothing goes through push() to prove it actually retries, propagates other errors, or surfaces the final error.
- **retry** #2, correctness and logic bugs: minor at `sync.py:4`: sync.py now depends on a module the change set labels as untracked, so if only the tracked diff is committed, import sync fails outright.
- **retry** #2, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The only test touching push exercises the happy path; the behavior the change actually delivers — push retrying ConnectionError up to 3 times and surfacing the error when all attempts fail — is never tested through push, only through the re
- **retry** #2, edge cases, error handling and missing tests: minor at `sync.py:7`: sleep=time.sleep (and retry.py:5 likewise) binds the real time.sleep at import time, so any later replacement of time.sleep is ignored by push/retry.
- **retry** #3, correctness and logic bugs: minor at `test_sync.py:25`: The tests exercise the new retry() helper directly but never exercise push() with a failing send, so the behavior the change was actually made for (push retries ConnectionError, gives up after 3 attempts, propagates other errors immediately
- **retry** #3, correctness and logic bugs: minor at `retry.py:1`: sync.py:4 now hard-depends on a brand-new top-level module retry.py that the diff shows as untracked, so if only tracked files are committed, importing sync fails.
- **retry** #3, edge cases, error handling and missing tests: minor at `test_sync.py:25`: None of the new tests ever drives push() through a failure, so the behavior the change exists to provide — push retrying ConnectionError up to 3 times and propagating other errors immediately — is untested; every retry assertion is made aga
- **retry** #3, edge cases, error handling and missing tests: minor at `retry.py:1`: sync.py now imports a module that the diff annotates as untracked, so the change is not self-contained: if retry.py is not committed alongside it, import sync fails outright.
- **retry** #4, edge cases, error handling and missing tests: major at `test_sync.py:25`: The behaviour the change is actually for — push retrying a ConnectionError up to 3 times with backoff, propagating other errors, and surfacing the error when all attempts fail — is never exercised; the new tests call retry() directly and on
- **retry** #4, edge cases, error handling and missing tests: minor at `test_sync.py:37`: test_retry_raises_the_last_error_when_every_attempt_fails cannot detect the property its name asserts: flaky(5) raises a brand-new ConnectionError("down") on every call, so raising the *first* error instead of the last would pass this test 
- **retry** #5, edge cases, error handling and missing tests: major at `sync.py:4`: sync.py now hard-depends on a new module retry.py that is not part of the change, so the feature is not actually shipped by the commit.
- **retry** #5, edge cases, error handling and missing tests: minor at `test_sync.py:25`: The new behaviour is only tested through the helper; no test exercises push retrying, so the wiring in push is unverified.
- **retry** #5, edge cases, error handling and missing tests: minor at `test_sync.py:37`: The test named "raises the last error" only asserts the exception type, so it cannot detect raising an earlier exception instead.
- **type_hints** #1, edge cases, error handling and missing tests: minor at `inventory.py:34`: The new docstring locks in that a fully depleted SKU can never appear in low_stock, and nothing in the test suite pins that (or the strict < threshold boundary) down.
- **upload_path** #1, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every security test calls safe_path directly; read_upload — the function the change is supposed to harden — is never exercised with a malicious name, so reverting read_upload to the unsafe join leaves the whole suite green.
- **upload_path** #2, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection assertion calls the helper safe_path directly; the only test of the actual request-facing entry point read_upload is the happy path, so the traversal guard in read_upload is not covered by any test.
- **upload_path** #3, correctness and logic bugs: minor at `test_uploads.py:19`: Every rejection test asserts on the internal helper safe_path, so the function the change is actually about — read_upload, the one that receives URL-supplied names — is never tested with a traversal name, and the symlink rejection promised 
- **upload_path** #3, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every traversal test calls the new helper safe_path directly; no test ever passes a malicious name to read_upload, so the function the change claims to harden is not covered by any negative test.
- **upload_path** #4, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: The rejection tests only call the new helper safe_path; nothing tests that read_upload — the function the request URL actually feeds — rejects traversal, so the security property the change exists to add is not pinned by any test.
- **upload_path** #4, edge cases, error handling and missing tests: minor at `uploads.py:12`: A name that resolves to a *directory* inside the upload folder passes the check (target != root and it is relative to root), so read_bytes() raises IsADirectoryError, not the ValueError the error message and the "not a file" wording imply.
- **upload_path** #5, edge cases, error handling and missing tests: minor at `test_uploads.py:19`: Every rejection test calls safe_path directly, so the actual request-reachable function read_upload is only ever tested on the happy path, and the symlink escape that the docstring explicitly promises to block has no test at all.

## Errors (1)

- format_bytes/clean #4: the provider is unavailable: Request timed out.
