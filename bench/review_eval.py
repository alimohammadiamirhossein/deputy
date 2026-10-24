#!/usr/bin/env python3
"""Measure Deputy's `review` on planted bugs and on clean diffs, without Claude.

Each case in bench/review_cases is a small repo (`before/`) and a change to it: `bug/` plants a
bug, `clean/` is a correct version of the same change, and some cases only have `clean/`. Each
run copies `before/` into a fresh temporary git repo, applies one change and calls Deputy's
review on that diff with the case's `focus`, the way Claude would. Claude is not involved, so a
run costs only Deputy's tokens.

    python bench/review_eval.py --check              # check the cases themselves; no API calls
    python bench/review_eval.py                      # every change once
    python bench/review_eval.py --repeats 3 --jobs 6

A planted bug counts as caught when a finding names its file and points within 3 lines of it or
uses one of the case's keywords. On a clean diff, every finding is a false alarm.

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from deputy.agent import DEFAULT_REVIEW_LENSES, DeputyError, review
from deputy.config import load_settings
from deputy.diff import collect_diff
from deputy.server import make_client
from deputy.workspace import Workspace

BENCH = Path(__file__).resolve().parent
CASES = BENCH / "review_cases"
RESULTS = BENCH / "results"

VARIANTS = ("bug", "clean")
SLACK = 3  # a finding this many lines from the planted bug still points at it
SERIOUS = ("critical", "major")
FIELD_RE = re.compile(r"^(SEVERITY|WHERE|WHAT GOES WRONG|WHY|IMPACT|REPRO|FIX|CONFIDENCE)\s*:\s*(.*)$",
                      re.IGNORECASE)
VERDICT_RE = re.compile(r"VERDICT\s*:\s*(approve|needs-attention)", re.IGNORECASE)
# parallel_passes() heads each reviewer's answer with "=== Lens: <lens> [<status> | ...] ==="
LENS_RE = re.compile(r"^=== (?:Lens: (.*?)|General) \[(\w+) \|.*\] ===$", re.MULTILINE)
PATH_RE = re.compile(r"[\w./\\-]+\.(?:py|pyi|js|ts|json|toml|cfg|ini|ya?ml|md|txt)\b")


def git(workdir: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid",
                    "-c", "core.autocrlf=false", *args], cwd=workdir, check=True,
                   capture_output=True)


def load_cases(names: list[str] | None) -> list[tuple[Path, dict, str]]:
    """(case folder, case.json, variant) for every change to review."""
    found = []
    for case in sorted(p for p in CASES.iterdir() if (p / "case.json").exists()):
        if names and case.name not in names:
            continue
        spec = json.loads((case / "case.json").read_text(encoding="utf-8"))
        found += [(case, spec, variant) for variant in VARIANTS if (case / variant).is_dir()]
    return found


def build(case: Path, variant: str, tmp: Path) -> Path:
    """The case's starting repo, committed, with one change applied on top and left uncommitted."""
    workdir = tmp / "work"
    shutil.copytree(case / "before", workdir)
    git(workdir, "init", "-q")
    git(workdir, "add", "-A")
    git(workdir, "commit", "-q", "-m", "before")
    shutil.copytree(case / variant, workdir, dirs_exist_ok=True)
    return workdir


def bug_lines(case: Path, bug: dict) -> list[int]:
    text = (case / "bug" / bug["file"]).read_text(encoding="utf-8")
    return [n for n, line in enumerate(text.splitlines(), 1) if bug["line_contains"] in line]


def _plain(line: str) -> str:
    """Drop the markdown a model may wrap around the format: bullets, numbering, bold, code."""
    line = line.strip().replace("**", "").replace("`", "")
    return re.sub(r"^(?:[-*•>#]+\s*|\d+[.)]\s+)+", "", line).strip()


def _where(value: str) -> tuple[str, list[int]]:
    """Repo-relative path and line numbers from a WHERE field such as "pager.py:20-22"."""
    found = PATH_RE.search(value)
    if not found:
        return "", []
    path = found.group(0).replace("\\", "/").split("/work/", 1)[-1].removeprefix("./")
    rest = value[found.end():]
    following = PATH_RE.search(rest)
    if following:  # "a.py:3, b.py:9": the numbers after b.py are not about a.py
        rest = rest[:following.start()]
    return path, [int(n) for n in re.findall(r"\d+", rest)][:4]


def parse_lens(body: str) -> tuple[str, list[dict]]:
    """The verdict and the findings in one reviewer's answer (see MODE_PROMPTS["review"])."""
    verdict = VERDICT_RE.search(body.replace("**", "").replace("`", ""))
    findings: list[dict] = []
    current: dict | None = None
    open_field = False
    for raw in body.splitlines():
        line = _plain(raw)
        if not line:
            open_field = False  # a blank line ends a field; trailing notes are not the finding
            continue
        field = FIELD_RE.match(line)
        if field and field.group(1).upper() == "SEVERITY":
            value = field.group(2).strip().lower()
            if value in ("none", "n/a", "-"):
                current = None
                continue
            severity = re.match(r"critical|major|minor", value)
            current = {"severity": severity.group(0) if severity else "unknown", "fields": {},
                       "text": ""}
            findings.append(current)
        if current is None:
            continue
        if field:
            current["fields"][field.group(1).upper()] = field.group(2).strip()
            open_field = True
        elif not open_field:
            continue
        current["text"] += line + "\n"

    parsed = []
    for finding in findings:
        path, lines = _where(finding["fields"].get("WHERE", ""))
        parsed.append({"severity": finding["severity"], "path": path, "lines": lines,
                       "confidence": finding["fields"].get("CONFIDENCE", "").lower(),
                       "what": finding["fields"].get("WHAT GOES WRONG", ""),
                       "text": finding["text"]})
    verdict_text = verdict.group(1).lower() if verdict else ""
    if verdict_text == "needs-attention" and not parsed:
        parsed.append({"severity": "unknown", "path": "", "lines": [], "confidence": "",
                       "what": "(needs-attention, but no finding could be parsed)", "text": body})
    return verdict_text, parsed


def parse_review(text: str) -> list[dict]:
    heads = list(LENS_RE.finditer(text))
    lenses = []
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        verdict, findings = parse_lens(text[head.end():end])
        lenses.append({"lens": head.group(1) or "general", "status": head.group(2),
                       "verdict": verdict, "findings": findings})
    return lenses


def points_at(finding: dict, bug: dict, lines: list[int]) -> bool:
    """Whether a finding is about the planted bug: its file, and near its line or naming it."""
    if finding["path"] and not ("/" + finding["path"]).endswith("/" + bug["file"]):
        return False
    near = any(min(lines) - SLACK <= n <= max(lines) + SLACK for n in finding["lines"])
    text = finding["text"].lower()
    return near or any(keyword.lower() in text for keyword in bug["keywords"])


def same_spot(a: dict, b: dict) -> bool:
    return (bool(a["path"]) and a["path"] == b["path"]
            and any(abs(x - y) <= SLACK for x in a["lines"] for y in b["lines"]))


def score(row: dict, lenses: list[dict], case: Path, spec: dict) -> dict:
    bug = spec.get("bug") if row["variant"] == "bug" else None
    lines = bug_lines(case, bug) if bug else []
    for lens in lenses:
        for finding in lens["findings"]:
            finding["on_bug"] = bool(bug) and points_at(finding, bug, lines)
        lens["caught"] = any(f["on_bug"] for f in lens["findings"]) if bug else None
    findings = [f for lens in lenses for f in lens["findings"]]
    hits = [f for f in findings if f["on_bug"]]
    row.update(
        lenses=lenses,
        findings=len(findings),
        flagged=bool(findings),
        serious=any(f["severity"] in SERIOUS for f in findings),
        other_findings=len(findings) - len(hits),
    )
    if bug:
        caught_by = sum(lens["caught"] for lens in lenses)
        row.update(caught=bool(hits), caught_serious=any(f["severity"] in SERIOUS for f in hits),
                   lenses_caught=caught_by, agreed=caught_by >= 2)
    else:
        row["agreed"] = any(same_spot(a, b)
                            for i, first in enumerate(lenses) for second in lenses[i + 1:]
                            for a in first["findings"] for b in second["findings"])
    return row


def run_case(case: Path, spec: dict, variant: str, rep: int, args: argparse.Namespace) -> dict:
    row = {"case": case.name, "variant": variant, "rep": rep, "error": "", "text": ""}
    with tempfile.TemporaryDirectory(prefix=f"deputy-review-{case.name}-",
                                     ignore_cleanup_errors=True) as tmp:
        workdir = build(case, variant, Path(tmp))
        settings = load_settings({**os.environ, "DEPUTY_WORKSPACE": str(workdir)})
        row.update(model=settings.model, thinking=args.thinking or settings.effort)
        started = time.monotonic()
        try:
            text, _, cost = review(collect_diff(Workspace(workdir)), settings,
                                   lambda: make_client(settings), focus=spec["focus"],
                                   lenses=args.lenses, effort=row["thinking"])
        except DeputyError as exc:
            return {**row, "error": str(exc)}
        row.update(cost=cost, seconds=round(time.monotonic() - started, 1), text=text)
    return score(row, parse_review(text), case, spec)


def run_pytest(target: Path, workdir: Path) -> int:
    env = {**os.environ, "PYTHONPATH": str(workdir)}
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           str(target)], cwd=workdir, env=env, capture_output=True,
                          text=True, timeout=300).returncode


def check(changes: list[tuple[Path, dict, str]]) -> int:
    """Each change's own tests pass; each bug is real (the proof test fails on it and passes on
    the clean version); each bug's line is found."""
    bad = 0
    for case, spec, variant in changes:
        with tempfile.TemporaryDirectory(prefix="deputy-review-check-",
                                         ignore_cleanup_errors=True) as tmp:
            workdir = build(case, variant, Path(tmp))
            ok = run_pytest(workdir, workdir) == 0
            notes = ["own tests pass" if ok else "own tests FAIL"]
            proof = case / "proof_test.py"
            if proof.exists():
                (Path(tmp) / "proof").mkdir()
                shutil.copy(proof, Path(tmp) / "proof" / proof.name)
                code = run_pytest(Path(tmp) / "proof", workdir)
                ok = ok and code == (1 if variant == "bug" else 0)
                notes.append({0: "proof passes", 1: "proof fails"}.get(code, f"proof errors ({code})"))
            elif variant == "bug":
                ok = False
                notes.append("no proof_test.py")
            if variant == "bug":
                lines = bug_lines(case, spec["bug"])
                ok = ok and len(lines) == 1
                notes.append(f"bug at {spec['bug']['file']}:{','.join(map(str, lines)) or '?'}")
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {case.name}/{variant}: {', '.join(notes)}")
    print(f"\n{len(changes) - bad}/{len(changes)} changes are sound.")
    return 1 if bad else 0


def pct(part: int, whole: int) -> str:
    return f"{part}/{whole} ({part / whole:.0%})" if whole else "-"


def mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def report(rows: list[dict], lenses: list[str]) -> str:
    done = [r for r in rows if not r["error"]]
    bugs = [r for r in done if r["variant"] == "bug"]
    clean = [r for r in done if r["variant"] == "clean"]
    model = done[0]["model"] if done else "?"
    thinking = done[0]["thinking"] if done else "?"
    out = [f"Model `{model}`, thinking `{thinking}`, lenses: {'; '.join(lenses)}.", "",
           "| Diffs | Reviews | Bug caught / false alarm | ...at major or critical | "
           "Two lenses agree | Findings not about a planted bug, per review | Mean cost | Mean time |",
           "|---|---|---|---|---|---|---|---|"]
    for label, group, hit, serious in (("Planted bug", bugs, "caught", "caught_serious"),
                                       ("Clean", clean, "flagged", "serious")):
        out.append(f"| {label} | {len(group)} | {pct(sum(r[hit] for r in group), len(group))} | "
                   f"{pct(sum(r[serious] for r in group), len(group))} | "
                   f"{pct(sum(r['agreed'] for r in group), len(group))} | "
                   f"{mean([r['other_findings'] for r in group]):.2f} | "
                   f"${mean([r['cost'] or 0.0 for r in group]):.4f} | "
                   f"{mean([r['seconds'] for r in group]):.0f} s |")

    out += ["", "| Lens | Bugs caught | False alarms on clean diffs | ...at major or critical |",
            "|---|---|---|---|"]
    for name in dict.fromkeys(lens["lens"] for r in done for lens in r["lenses"]):
        on_bugs = [lens for r in bugs for lens in r["lenses"] if lens["lens"] == name]
        on_clean = [lens for r in clean for lens in r["lenses"] if lens["lens"] == name]
        serious = sum(any(f["severity"] in SERIOUS for f in lens["findings"]) for lens in on_clean)
        out.append(f"| {name} | {pct(sum(lens['caught'] for lens in on_bugs), len(on_bugs))} | "
                   f"{pct(sum(bool(lens['findings']) for lens in on_clean), len(on_clean))} | "
                   f"{pct(serious, len(on_clean))} |")

    out += ["", "| Case | Diff | Reviews | Result | Findings (critical / major / minor) |",
            "|---|---|---|---|---|"]
    for case, variant in dict.fromkeys((r["case"], r["variant"]) for r in done):
        group = [r for r in done if r["case"] == case and r["variant"] == variant]
        found = [f for r in group for lens in r["lenses"] for f in lens["findings"]]
        result = (f"caught {sum(r['caught'] for r in group)}/{len(group)}" if variant == "bug"
                  else f"flagged {sum(r['flagged'] for r in group)}/{len(group)}")
        counts = " / ".join(str(sum(f["severity"] == s for f in found))
                            for s in ("critical", "major", "minor"))
        out.append(f"| {case} | {variant} | {len(group)} | {result} | {counts} |")

    alarms = [(r, lens, f) for r in clean for lens in r["lenses"] for f in lens["findings"]]
    out += ["", f"## Findings on clean diffs ({len(alarms)})", "",
            "Each is a false alarm by construction. Read them: some may be fair minor points.", ""]
    for r, lens, f in alarms:
        where = f["path"] + (f":{f['lines'][0]}" if f["lines"] else "")
        out.append(f"- **{r['case']}** #{r['rep']}, {lens['lens']}: {f['severity']} at "
                   f"`{where or '?'}`: {f['what'][:240] or '(no summary)'}")
    missed = [r for r in bugs if not r["caught"]]
    if missed:
        out += ["", f"## Missed bugs ({len(missed)})", ""]
        out += [f"- **{r['case']}** #{r['rep']}" for r in missed]
    errors = [r for r in rows if r["error"]]
    if errors:
        out += ["", f"## Errors ({len(errors)})", ""]
        out += [f"- {r['case']}/{r['variant']} #{r['rep']}: {r['error']}" for r in errors]
    return "\n".join(out)


def save(rows: list[dict], lenses: list[str], log_dir: Path) -> None:
    """Write the results after every review, so a crash or Ctrl-C keeps what finished."""
    rows = sorted(rows, key=lambda r: (r["case"], r["variant"], r["rep"]))
    public = [{k: v for k, v in r.items() if k != "text"} for r in rows]
    for r in public:
        for lens in r.get("lenses", []):
            lens["findings"] = [{k: v for k, v in f.items() if k != "text"}
                                for f in lens["findings"]]
    (log_dir / "results.json").write_text(json.dumps(public, indent=2), encoding="utf-8")
    (log_dir / "results.md").write_text("# Deputy review benchmark\n\n" + report(rows, lenses)
                                        + "\n", encoding="utf-8")
    (log_dir / "reviews.jsonl").write_text(
        "\n".join(json.dumps({k: r[k] for k in ("case", "variant", "rep", "text")}) for r in rows),
        encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", nargs="*", help="case folder names (default: all)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=4, help="reviews at once (default: 4)")
    parser.add_argument("--lenses", nargs="*",
                        help=f"review lenses (default: Deputy's {DEFAULT_REVIEW_LENSES})")
    parser.add_argument("--thinking", choices=["high", "max"],
                        help="default: DEPUTY_THINKING, else high")
    parser.add_argument("--check", action="store_true",
                        help="only check that the cases are sound; no API calls")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")  # the report quotes the model; keep cp1252 consoles alive

    changes = load_cases(args.cases)
    if not changes:
        sys.exit("No cases matched.")
    if args.check:
        return check(changes)
    if not load_settings().api_key:
        sys.exit("Set DEEPINFRA_API_KEY first.")
    lenses = args.lenses or DEFAULT_REVIEW_LENSES
    log_dir = RESULTS / f"review-{datetime.now():%Y%m%d-%H%M%S}"
    log_dir.mkdir(parents=True, exist_ok=True)

    runs = [(*change, rep) for rep in range(1, args.repeats + 1) for change in changes]
    print(f"{len(runs)} reviews ({len(changes)} changes x {args.repeats}), {args.jobs} at a time",
          flush=True)
    rows: list[dict] = []
    pool = ThreadPoolExecutor(max_workers=max(1, args.jobs))
    try:
        futures = [pool.submit(run_case, *run, args) for run in runs]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            save(rows, lenses, log_dir)
            if row["error"]:
                outcome = f"ERROR: {row['error']}"
            elif row["variant"] == "bug":
                outcome = (f"{'caught' if row['caught'] else 'MISSED'} "
                           f"({row['lenses_caught']} lenses), {row['other_findings']} other findings")
            else:
                outcome = f"{row['findings']} findings" if row["flagged"] else "approved"
            cost = f"${row['cost']:.4f}" if row.get("cost") is not None else "n/a"
            print(f"[{len(rows)}/{len(runs)}] {row['case']}/{row['variant']} #{row['rep']}: "
                  f"{outcome} | {cost} | {row.get('seconds', 0):.0f} s", flush=True)
            if "API key" in row["error"]:
                sys.exit("Deputy could not use the API key. Check DEEPINFRA_API_KEY.")
    finally:
        pool.shutdown(wait=True, cancel_futures=True)

    print("\n" + report(rows, lenses) + f"\n\nSaved to {log_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
