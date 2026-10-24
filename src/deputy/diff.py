"""Collect the current change (git diff plus new files) for the review tool."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .workspace import Workspace, WorkspaceError

MAX_DIFF_CHARS = 150_000
MAX_NEW_FILES = 20
MAX_NEW_FILE_BYTES = 50_000


class DiffError(RuntimeError):
    """The change could not be collected; the caller should pass the diff explicitly."""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.quotepath=off", *args], cwd=root, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60, stdin=subprocess.DEVNULL,
    )


def _new_file_diff(name: str, text: str) -> str:
    """A new file the way `git diff` shows one. Git does not track it yet, but it is part of the
    change; labelling it "untracked" made reviewers report that it would be left out."""
    lines = text.splitlines()
    header = f"diff --git a/{name} b/{name}\nnew file mode 100644\n--- /dev/null\n+++ b/{name}"
    if not lines:
        return header
    count = "" if len(lines) == 1 else f",{len(lines)}"
    return f"{header}\n@@ -0,0 +1{count} @@\n" + "\n".join(f"+{line}" for line in lines)


def collect_diff(workspace: Workspace, base: str = "", paths: list[str] | None = None) -> str:
    """Uncommitted changes (staged and unstaged) against `base` (default HEAD), plus new files."""
    if shutil.which("git") is None:
        raise DiffError("git is not installed; pass the change as `diff` instead")
    root = workspace.root
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        raise DiffError("the workspace is not a git repository; pass the change as `diff` instead")
    base = base.strip()
    if base.startswith("-") or any(ch.isspace() for ch in base):
        raise DiffError(f"invalid base revision: {base!r}")
    try:
        scope = [workspace.rel(workspace.resolve(p)) for p in (paths or [])]
    except WorkspaceError as exc:
        raise DiffError(str(exc)) from None

    has_head = _git(root, "rev-parse", "--verify", "--quiet", "HEAD").returncode == 0
    args = ["diff", "--no-color", "--no-ext-diff", "--no-textconv"]
    if base:
        args.append(base)
    elif has_head:
        args.append("HEAD")
    else:
        args.append("--cached")
    result = _git(root, *args, "--", *scope)
    if result.returncode != 0:
        raise DiffError(f"git diff failed: {result.stderr.strip()[:300]}")
    parts = [result.stdout] if result.stdout.strip() else []

    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "--", *scope).stdout.split("\n")
    for name in [n for n in untracked if n.strip()][:MAX_NEW_FILES]:
        path = root / name
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > MAX_NEW_FILE_BYTES or b"\x00" in data[:8192]:
            parts.append(f"new file {name}: (skipped, binary or larger than {MAX_NEW_FILE_BYTES} bytes)")
            continue
        parts.append(_new_file_diff(name, data.decode("utf-8", errors="replace")))

    text = "\n".join(parts).strip()
    if not text:
        raise DiffError("no uncommitted changes found; pass `base` (for example main) or `diff`")
    if len(text) > MAX_DIFF_CHARS:
        text = (text[:MAX_DIFF_CHARS] + f"\n... [diff truncated at {MAX_DIFF_CHARS} characters; "
                "review the rest by passing `paths`]")
    return text
