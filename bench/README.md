# Deputy benchmark

Measures what Deputy changes on real Claude Code runs: **did the work pass tests Claude never
saw, and what did it cost?**

Each run copies a task into a fresh temporary git repo and runs `claude -p` headless with the task
prompt. Then it runs that task's hidden tests. Each task can run in these configs:

| Config | What Claude gets |
|---|---|
| `claude` | No Deputy at all (baseline) |
| `review` | Deputy in accuracy mode, and the prompt asks Claude to run Deputy's `review` before it finishes (what `/deputy:review` does) |
| `delegate` | Deputy in savings mode, and the prompt asks Claude to delegate the implementation and verify it (what `/deputy:delegate` does) |
| `accuracy`, `lean`, `balanced`, `partner`, `savings` | Deputy in that mode with the plain task prompt, so Claude decides on its own whether to call it |

The default run is `claude`, `review` and `delegate`. Unprompted, Claude often skips Deputy on
tasks this small, so the plain modes mostly measure that choice.

Costs come from the tools themselves, not estimates: Claude's from Claude Code's
`total_cost_usd`, Deputy's from the `est. cost` figure on each Deputy result.

## Tasks

| Task | Kind | What the hidden tests check |
|---|---|---|
| `rate_limiter` | implement | half-open window, rejected calls not counted, bad config, bounded speed |
| `booking_ranges` | fix bugs | touching, contained and unsorted ranges; clipping to the day |
| `expense_report` | implement | quoted amounts, BOM, case, empty rows, half-up rounding, line numbers in errors |
| `rename_refactor` | mechanical refactor | new name everywhere, deprecated alias warns, helpers don't warn |

Each task folder has `task.md` (the prompt), `repo/` (the starting code with visible tests) and
`hidden/` (the tests Claude never sees). The hidden tests were checked to fail on the starting
code and pass with a correct solution.

## Run it

You need Claude Code (`claude` on your PATH), Python with `pytest`, and a DeepInfra key. Deputy
starts from the Python that runs `run.py`, so install it there first (`pip install -e .` from the
repo root). After each run the harness stops that run's Deputy server, which on Windows can
otherwise outlive Claude Code.

```bash
export DEEPINFRA_API_KEY="sk-di-..."
python bench/run.py                              # all tasks: claude, review, delegate
python bench/run.py --configs claude accuracy --repeats 3
python bench/run.py --tasks booking_ranges --model sonnet
```

Results go to `bench/results/<timestamp>/` as `results.md` (tables), `results.json` and one
transcript per run (`*.jsonl`, not committed).

**This spends real money.** Each Opus run costs Claude Code tokens (often $0.10–$1.00), plus a
fraction of a cent for Deputy. The default run is 4 tasks × 3 configs = 12 runs.

## Results so far

[results/2026-10-24-opus](results/2026-10-24-opus/results.md): one run per task and config on
Opus 5.5. All 12 runs passed their hidden tests, so these tasks are too easy to show an accuracy
gain. Mean cost per task was $0.18 for Opus alone, $0.31 with `review` (Deputy's share $0.013)
and $0.19 with `delegate` (Deputy's share $0.0015). Review findings led Claude to harden the code
in 3 of 4 tasks. Harder tasks, where Opus sometimes fails, and more repeats are the next step.

## Deputy alone as the worker

`bench/delegate_eval.py` hands each task to Deputy's coding agent (what `delegate` runs) without
Claude, then runs the hidden tests, so it measures the worker's speed and correctness on its own:

```bash
python bench/delegate_eval.py --thinking high medium low --repeats 3
```

[results/2026-10-24-delegate-thinking](results/2026-10-24-delegate-thinking/results.md): with
thinking `high`, Deputy passed 12 of 12 runs with a median of 29 s per task, about as fast as Opus
alone. `low` (11/12, 20 s) and `medium` (8/12, 27 s) saved little time and failed more often, so
the worker keeps `high`.

## Reading the results

- Compare **pass rate** first, then **total cost** (Claude + Deputy) and time.
- Runs vary, so use `--repeats 3` or more before publishing a number, and publish the whole table,
  including the runs where Deputy didn't help.
- In `accuracy` mode Claude may decide a small task doesn't need Deputy at all. The
  "Deputy calls" column shows what was actually used.
- Your user-level Claude Code settings and `CLAUDE.md` apply to every config equally. Disable the
  Deputy plugin while benchmarking so the `claude` baseline really has no Deputy.

## Adding a task

Create `bench/tasks/<name>/` with `task.md`, `repo/` and `hidden/test_hidden.py`. Hidden tests
run with the work folder on `PYTHONPATH`, and its path in `BENCH_WORKDIR`. Check that they fail
on the starting code and pass with a correct solution before you trust a result.
