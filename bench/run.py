#!/usr/bin/env python3
"""Measure Claude Code with and without Deputy on the tasks in bench/tasks.

Each run copies a task into a fresh temporary git repo, runs `claude -p` headless on the task
prompt, then runs hidden tests that Claude never saw. Claude's cost is Claude Code's own
`total_cost_usd`; Deputy's cost is the sum of the `est. cost $X` figures in its tool results.

    python bench/run.py                       # every task: claude, review, delegate, once
    python bench/run.py --configs claude review --repeats 3
    python bench/run.py --tasks booking_ranges --model sonnet

Deputy runs from the Python that runs this script, so install it there first (`pip install -e .`).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

BENCH = Path(__file__).resolve().parent
REPO = BENCH.parent
TASKS = BENCH / "tasks"
RESULTS = BENCH / "results"

# config name -> (DEPUTY_MODE or None for Claude alone, text appended to the task prompt).
# Unprompted, Claude often skips Deputy on small tasks, so `review` and `delegate` add the same
# request a user makes with /deputy:review or /deputy:delegate.
CONFIGS = {
    "claude": (None, ""),
    "accuracy": ("accuracy", ""),
    "balanced": ("balanced", ""),
    "savings": ("savings", ""),
    "review": ("accuracy", "\n\nBefore you say you're done, call Deputy's `review` tool on your "
                           "change and verify each finding against the code."),
    "delegate": ("savings", "\n\nDelegate the implementation to Deputy with its `delegate` tool, "
                            "then verify the result yourself: read the diff and run the tests."),
}
# PowerShell is Claude Code's shell tool on Windows; Bash elsewhere. Runs happen in a temp copy.
ALLOWED_TOOLS = "Read,Edit,MultiEdit,Write,Glob,Grep,Bash,PowerShell,mcp__deputy"
# Deputy's per-run stats line: "... | 12 turns | 30s | ... | est. cost $0.0011"
COST_RE = re.compile(r"\|\s*\d+ turns \|.*?est\. cost \$([0-9]+(?:\.[0-9]+)?)")
KEY_ERRORS = ("has no API key", "rejected the API key")


def mcp_config(mode: str | None, workdir: Path, marker: str) -> dict:
    if mode is None:
        return {"mcpServers": {}}
    # The marker is ignored by Deputy; it only makes this run's server findable by stop_server.
    serve = "import sys; from deputy.cli import main; sys.exit(main(['serve']))"
    return {"mcpServers": {"deputy": {
        "command": sys.executable,
        "args": ["-c", serve, marker],
        "env": {
            "DEPUTY_MODE": mode,
            "DEPUTY_WORKSPACE": str(workdir),
            "DEEPINFRA_API_KEY": "${DEEPINFRA_API_KEY}",
        },
    }}}


def stop_server(marker: str) -> None:
    """Stop a Deputy server that outlived Claude Code. On Windows, killing the launcher process
    can leave the Python child running, which also keeps the temp folder locked."""
    if os.name == "nt":
        script = (f"Get-CimInstance Win32_Process | Where-Object {{ $_.ProcessId -ne $PID -and "
                  f"$_.CommandLine -like '*{marker}*' }} | ForEach-Object {{ "
                  "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
        subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", marker], capture_output=True)


def git(workdir: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid",
                    *args], cwd=workdir, check=True, capture_output=True)


def parse_stream(lines: list[str]) -> dict:
    """Pull cost, turns and Deputy tool use out of Claude Code's stream-json output."""
    tool_names: dict[str, str] = {}
    deputy_calls: dict[str, int] = {}
    deputy_cost = 0.0
    key_error = False
    denied = 0
    final: dict = {}
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            final = event
            continue
        if event.get("subtype") == "permission_denied":
            denied += 1
            continue
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                tool_names[block.get("id", "")] = block.get("name", "")
            elif block.get("type") == "tool_result":
                name = tool_names.get(block.get("tool_use_id", ""), "")
                if not name.startswith("mcp__deputy__"):
                    continue
                tool = name.removeprefix("mcp__deputy__")
                deputy_calls[tool] = deputy_calls.get(tool, 0) + 1
                body = block.get("content")
                if isinstance(body, list):
                    body = "\n".join(part.get("text", "") for part in body if isinstance(part, dict))
                text = str(body or "")
                deputy_cost += sum(float(cost) for cost in COST_RE.findall(text))
                key_error = key_error or any(error in text for error in KEY_ERRORS)
    return {
        "claude_cost": final.get("total_cost_usd"),
        "turns": final.get("num_turns"),
        "claude_error": final.get("is_error", not final),
        "deputy_cost": round(deputy_cost, 6),
        "deputy_calls": deputy_calls,
        "deputy_key_error": key_error,
        "permission_denials": denied,
    }


def hidden_tests(task: Path, workdir: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="deputy-hidden-") as tmp:
        hidden = Path(tmp) / "hidden"
        shutil.copytree(task / "hidden", hidden)
        env = {**os.environ, "PYTHONPATH": str(workdir), "BENCH_WORKDIR": str(workdir)}
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                               str(hidden)], cwd=workdir, env=env, capture_output=True,
                              text=True, timeout=300)
    summary = (proc.stdout.strip().splitlines() or [""])[-1]
    return proc.returncode == 0, summary


def run_one(task: Path, config: str, args: argparse.Namespace, log_dir: Path, rep: int) -> dict:
    claude = shutil.which("claude")
    if not claude:
        sys.exit("`claude` is not on PATH. Install Claude Code first.")
    marker = f"deputy-bench-{uuid.uuid4().hex[:12]}"
    with tempfile.TemporaryDirectory(prefix=f"deputy-bench-{task.name}-",
                                     ignore_cleanup_errors=True) as tmp:
        workdir = Path(tmp) / "work"
        shutil.copytree(task / "repo", workdir)
        git(workdir, "init", "-q")
        git(workdir, "add", "-A")
        git(workdir, "commit", "-q", "-m", "task start")
        config_path = Path(tmp) / "mcp.json"
        mode, suffix = CONFIGS[config]
        config_path.write_text(json.dumps(mcp_config(mode, workdir, marker)), encoding="utf-8")
        cmd = [claude, "-p", (task / "task.md").read_text(encoding="utf-8") + suffix,
               "--output-format", "stream-json", "--verbose", "--model", args.model,
               "--max-turns", str(args.max_turns), "--permission-mode", "acceptEdits",
               "--allowedTools", ALLOWED_TOOLS,
               "--strict-mcp-config", "--mcp-config", str(config_path)]
        started = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=args.timeout)
            lines = proc.stdout.splitlines()
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout or ""
            lines = (out.decode("utf-8", "replace") if isinstance(out, bytes) else out).splitlines()
        seconds = time.monotonic() - started
        stop_server(marker)
        (log_dir / f"{task.name}-{config}-{rep}.jsonl").write_text("\n".join(lines),
                                                                    encoding="utf-8")
        result = parse_stream(lines)
        passed, summary = hidden_tests(task, workdir)
    claude_cost = result["claude_cost"] or 0.0
    return {"task": task.name, "config": config, "rep": rep, "model": args.model,
            "passed": passed, "hidden_tests": summary, "seconds": round(seconds, 1),
            "total_cost": round(claude_cost + result["deputy_cost"], 6), **result}


def money(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.4f}"


def report(rows: list[dict]) -> str:
    lines = ["| Task | Config | Hidden tests | Claude | Deputy | Total | Time | Deputy calls |",
             "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        calls = ", ".join(f"{tool} {count}" for tool, count in row["deputy_calls"].items()) or "-"
        lines.append(f"| {row['task']} | {row['config']} | "
                     f"{'pass' if row['passed'] else 'FAIL'} ({row['hidden_tests']}) | "
                     f"{money(row['claude_cost'])} | {money(row['deputy_cost'])} | "
                     f"{money(row['total_cost'])} | {row['seconds']:.0f} s | {calls} |")
    lines += ["", "| Config | Runs | Pass rate | Mean total cost | Mean time |",
              "|---|---|---|---|---|"]
    for config in dict.fromkeys(row["config"] for row in rows):
        group = [row for row in rows if row["config"] == config]
        lines.append(f"| {config} | {len(group)} | "
                     f"{sum(row['passed'] for row in group)}/{len(group)} | "
                     f"{money(statistics.mean(row['total_cost'] for row in group))} | "
                     f"{statistics.mean(row['seconds'] for row in group):.0f} s |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", nargs="*", help="task folder names (default: all)")
    parser.add_argument("--configs", nargs="*", choices=list(CONFIGS),
                        default=["claude", "review", "delegate"])
    parser.add_argument("--model", default="opus", help="Claude model alias or id (default: opus)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per run")
    args = parser.parse_args()

    if any(CONFIGS[c][0] for c in args.configs) and not (
            os.environ.get("DEEPINFRA_API_KEY") or os.environ.get("DEPUTY_API_KEY")):
        sys.exit("Set DEEPINFRA_API_KEY first; the Deputy configs need it.")
    tasks = sorted(p for p in TASKS.iterdir() if (p / "task.md").exists())
    if args.tasks:
        tasks = [t for t in tasks if t.name in args.tasks]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dir = RESULTS / stamp
    log_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for rep in range(1, args.repeats + 1):
        for task in tasks:
            for config in args.configs:
                print(f"[{rep}/{args.repeats}] {task.name} / {config} ...", flush=True)
                row = run_one(task, config, args, log_dir, rep)
                rows.append(row)
                save(rows, log_dir)
                print(f"    {'pass' if row['passed'] else 'FAIL'} | claude "
                      f"{money(row['claude_cost'])} | deputy {money(row['deputy_cost'])} | "
                      f"{row['seconds']:.0f} s | {row['deputy_calls'] or 'no Deputy calls'}"
                      + (f" | {row['permission_denials']} tool calls denied"
                         if row["permission_denials"] else ""), flush=True)
                if row["deputy_key_error"]:
                    sys.exit("Deputy could not use the API key. Check DEEPINFRA_API_KEY.")

    print("\n" + report(rows) + f"\n\nSaved to {log_dir}")
    return 0


def save(rows: list[dict], log_dir: Path) -> None:
    """Write the results after every run, so a crash or Ctrl-C keeps what finished."""
    (log_dir / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (log_dir / "results.md").write_text(report(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
