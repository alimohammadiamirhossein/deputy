#!/usr/bin/env python3
"""Measure Deputy as a worker, without Claude: how fast `delegate` is, and whether its work passes.

Each run copies a task from bench/tasks into a fresh temporary git repo, hands `task.md` to
Deputy's coding agent (what the `delegate` tool runs), then runs the task's hidden tests.

    python bench/delegate_eval.py                                  # thinking high, once
    python bench/delegate_eval.py --thinking high medium low --repeats 3

Deputy runs from the Python that runs this script, so install it there first (`pip install -e .`).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from deputy.agent import DeputyError, run_agent
from deputy.config import EFFORTS, load_settings
from deputy.server import make_client

from run import RESULTS, TASKS, git, hidden_tests


def run_task(task: Path, thinking: str, rep: int) -> dict:
    row = {"task": task.name, "thinking": thinking, "rep": rep, "error": ""}
    with tempfile.TemporaryDirectory(prefix=f"deputy-worker-{task.name}-",
                                     ignore_cleanup_errors=True) as tmp:
        workdir = Path(tmp) / "work"
        shutil.copytree(task / "repo", workdir)
        git(workdir, "init", "-q")
        git(workdir, "add", "-A")
        git(workdir, "commit", "-q", "-m", "task start")
        settings = load_settings({**os.environ, "DEPUTY_WORKSPACE": str(workdir)})
        started = time.monotonic()
        try:
            result = run_agent((task / "task.md").read_text(encoding="utf-8"), settings,
                               make_client(settings), mode="code", effort=thinking)
        except DeputyError as exc:
            return {**row, "error": str(exc)}
        seconds = time.monotonic() - started
        passed, summary = hidden_tests(task, workdir)
    return {**row, "passed": passed, "hidden_tests": summary, "seconds": round(seconds, 1),
            "status": result.status, "turns": result.turns, "out": result.usage.completion,
            "thinking_tokens": result.usage.reasoning, "cost": result.cost}


def report(rows: list[dict]) -> str:
    done = [r for r in rows if not r["error"]]
    out = ["| Thinking | Runs | Hidden tests passed | Median time | Max time | Mean output tokens "
           "(thinking) | Mean cost |", "|---|---|---|---|---|---|---|"]
    for level in dict.fromkeys(r["thinking"] for r in done):
        group = [r for r in done if r["thinking"] == level]
        out.append(f"| {level} | {len(group)} | {sum(r['passed'] for r in group)}/{len(group)} | "
                   f"{statistics.median(r['seconds'] for r in group):.0f} s | "
                   f"{max(r['seconds'] for r in group):.0f} s | "
                   f"{statistics.mean(r['out'] for r in group):,.0f} "
                   f"({statistics.mean(r['thinking_tokens'] for r in group):,.0f}) | "
                   f"${statistics.mean(r['cost'] or 0.0 for r in group):.4f} |")
    out += ["", "| Task | Thinking | Passed | Times |", "|---|---|---|---|"]
    for task, level in dict.fromkeys((r["task"], r["thinking"]) for r in done):
        group = [r for r in done if r["task"] == task and r["thinking"] == level]
        times = ", ".join(f"{r['seconds']:.0f} s" for r in group)
        out.append(f"| {task} | {level} | {sum(r['passed'] for r in group)}/{len(group)} | {times} |")
    errors = [r for r in rows if r["error"]]
    if errors:
        out += ["", f"## Errors ({len(errors)})", ""]
        out += [f"- {r['task']} / {r['thinking']} #{r['rep']}: {r['error']}" for r in errors]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", nargs="*", help="task folder names (default: all)")
    parser.add_argument("--thinking", nargs="*", choices=EFFORTS, default=["high"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=4, help="runs at once (default: 4)")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")

    if not load_settings().api_key:
        sys.exit("Set DEEPINFRA_API_KEY first.")
    tasks = sorted(p for p in TASKS.iterdir() if (p / "task.md").exists())
    if args.tasks:
        tasks = [t for t in tasks if t.name in args.tasks]
    log_dir = RESULTS / f"delegate-{datetime.now():%Y%m%d-%H%M%S}"
    log_dir.mkdir(parents=True, exist_ok=True)

    runs = [(task, level, rep) for rep in range(1, args.repeats + 1) for level in args.thinking
            for task in tasks]
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for future in as_completed([pool.submit(run_task, *run) for run in runs]):
            row = future.result()
            rows.append(row)
            rows.sort(key=lambda r: (r["thinking"], r["task"], r["rep"]))
            (log_dir / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
            (log_dir / "results.md").write_text(report(rows) + "\n", encoding="utf-8")
            outcome = row["error"] or (f"{'pass' if row['passed'] else 'FAIL'} | "
                                       f"{row['seconds']:.0f} s | {row['out']:,} out")
            print(f"[{len(rows)}/{len(runs)}] {row['task']} / {row['thinking']} #{row['rep']}: "
                  f"{outcome}", flush=True)

    print("\n" + report(rows) + f"\n\nSaved to {log_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
