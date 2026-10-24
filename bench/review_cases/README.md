# Review benchmark

How often does Deputy's `review` catch a real bug, and how often does it raise a false alarm on a
change that has none? `bench/run.py` measures whole Claude Code runs. This benchmark checks only
the reviewers: no Claude, just Deputy's `review` on known diffs, so a full run costs cents and
can be repeated often.

## Cases

| Case | The change | Planted bug |
|---|---|---|
| `pagination` | add `page_count()` | `total // per_page + 1`: one page too many on exact multiples, and 1 page for 0 items |
| `retry` | retry `push()` on `ConnectionError` | after the last attempt it logs and returns `None` instead of raising |
| `memoize` | cache `quote()` | the cache key ignores keyword arguments |
| `config_merge` | deep-merge settings overrides | a shallow copy, so merging changes `DEFAULTS` |
| `upload_path` | block path traversal | only rejects `..`, so an absolute name escapes the folder |
| `format_bytes` | add `format_bytes()` | `<=` at the boundary: 1024 bytes shows as "1024 B" |
| `type_hints` | add type hints and docstrings | none (clean only) |
| `rename_alias` | rename with a deprecated alias | none (clean only) |

Each planted-bug case also has a **clean twin**: the same change done right, reviewed with the
same `focus`. Twins are the hard negatives. A reviewer that flags the clean twin where the bug
would be is matching a pattern, not reading the code.

Each case folder has:

- `case.json`: `focus` (what the change should do, as Claude would pass it) and, for bug cases,
  `bug`: the file, a string that finds its line, keywords that name it, and a description.
- `before/`: the starting repo, committed before the review.
- `bug/` and `clean/`: the changed files, applied on top and left uncommitted.
- `proof_test.py`: fails on `bug/` and passes on `clean/`, which proves the bug is real. The
  reviewers never see it.

## Scoring

- **Caught**: a finding names the bug's file and points within 3 lines of the bug or uses one of
  its keywords.
- **False alarm**: any finding on a clean diff. The table counts these at any severity and at
  major or critical, because a minor note about a missing test and a claim of data loss take
  Claude very different amounts of work to check.
- **Two lenses agree**: on bug diffs, both lenses caught the bug. On clean diffs, two lenses
  flagged the same spot (same file, within 3 lines). Deputy tells Claude that agreement makes a
  finding more likely to be real, and this column checks that claim.

Matching is automatic and approximate. `results.md` lists every finding on a clean diff so you can
judge them yourself, and `reviews.jsonl` (not committed) holds the raw reviews.

## Run it

You need a DeepInfra key, and Deputy installed in the Python that runs the script
(`pip install -e .` from the repo root). Claude Code is not needed.

```bash
python bench/review_eval.py --check                      # are the cases sound? (no API calls)
python bench/review_eval.py --repeats 5 --jobs 6
python bench/review_eval.py --cases upload_path --lenses "security and input handling"
```

Results go to `bench/results/review-<timestamp>/`.

## Results

The first run (October 2026, DeepSeek V4.1 Flash, thinking `high`, 5 repeats) is in
[`bench/results/2026-10-24-review`](../results/2026-10-24-review/results.md). Every planted bug
was caught; 11 of 39 clean reviews included a major or critical finding. Two things to know when
reading the clean-diff findings:

- In `memoize`, the `focus` says the cache stays small because there are few SKUs, but the cache
  key also includes `qty`. Reviewers who call the cache unbounded have a point.
- In that run, Deputy labelled new files "(untracked)" in the diff, and in `retry` some reviewers
  read that as "`retry.py` will not be committed". New files now appear as `git diff` shows an
  added file, which removes that false alarm.

## Adding a case

Create `bench/review_cases/<name>/` with the files above. Keep the change realistic: the visible
tests in `bug/` should pass, as they would when a bug slips through, and the `focus` should state
the intended behavior clearly enough that a careful reviewer can tell right from wrong. Then run
`--check`. It must report the case as sound before you trust a result.
