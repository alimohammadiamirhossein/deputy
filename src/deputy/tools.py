"""Tools the deputy model can call inside the workspace.

Every tool returns a string. Errors are returned as text starting with
"ERROR:" so the model can read them and recover, instead of crashing the run.
"""
from __future__ import annotations

import difflib
import fnmatch
import json
import os
import re
import shutil
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .workspace import Workspace, WorkspaceError

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".idea", ".next",
    "dist", "build", ".gradle", "target", ".terraform",
}
MAX_OUTPUT_CHARS = 30_000
MAX_READ_BYTES = 2_000_000
MAX_SEARCH_FILE_BYTES = 1_000_000
MAX_LIST = 400
MAX_MATCHES = 200

# Environment variables whose names look like secrets are removed before a
# command runs, so the deputy model cannot read your keys through the shell.
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSW|CREDENTIAL|AUTH(?!OR)|COOKIE)", re.I)
SECRET_PREFIXES = ("DEPUTY_", "DEEPINFRA_", "XAI_", "ANTHROPIC_", "OPENAI_", "CLAUDE_CODE_OAUTH")


@dataclass
class FileChange:
    before: str | None  # None when the file did not exist


@dataclass
class ToolContext:
    workspace: Workspace
    command_timeout: int
    allow_writes: bool
    changes: dict[str, FileChange] = field(default_factory=dict)
    commands: list[dict] = field(default_factory=list)


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    head, tail = text[: limit * 2 // 3], text[-limit // 3 :]
    return f"{head}\n... [{len(text) - len(head) - len(tail)} characters omitted] ...\n{tail}"


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > MAX_READ_BYTES:
        raise WorkspaceError(f"file is too large to read ({len(data)} bytes)")
    if b"\x00" in data[:8192]:
        raise WorkspaceError("file looks binary")
    return data.decode("utf-8", errors="replace")


def _walk_files(root: Path):
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            yield Path(current) / name


# ----------------------------------------------------------------- read tools

def _glob_match(rel: str, name: str, pattern: str) -> bool:
    patterns = [pattern]
    # fnmatch has no "**": treat a leading "**/" as "any folder, including none".
    while patterns[-1].startswith("**/"):
        patterns.append(patterns[-1][3:])
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in patterns if p)


def list_files(ctx: ToolContext, pattern: str = "**/*", path: str = ".") -> str:
    base = ctx.workspace.resolve(path)
    if not base.is_dir():
        return f"ERROR: not a directory: {path}"
    pattern = pattern.replace("\\", "/")
    rows = []
    for file in _walk_files(base):
        rel = Path(os.path.relpath(file, base)).as_posix()
        if _glob_match(rel, file.name, pattern):
            try:
                size = file.stat().st_size
            except OSError:
                continue
            rows.append(f"{ctx.workspace.rel(file)}  ({size} bytes)")
            if len(rows) >= MAX_LIST:
                rows.append(f"... stopped at {MAX_LIST} files; use a narrower pattern")
                break
    return "\n".join(rows) if rows else "No files matched."


def read_file(ctx: ToolContext, path: str, offset: int = 1, limit: int = 400) -> str:
    target = ctx.workspace.resolve(path)
    if not target.is_file():
        return f"ERROR: file not found: {path}"
    lines = _read_text(target).splitlines()
    offset = max(1, int(offset))
    limit = max(1, min(int(limit), 2000))
    chunk = lines[offset - 1 : offset - 1 + limit]
    body = "\n".join(f"{n:>6}| {line}" for n, line in enumerate(chunk, start=offset))
    more = len(lines) - (offset - 1 + len(chunk))
    footer = f"\n[{more} more lines; call read_file with offset={offset + len(chunk)}]" if more > 0 else ""
    return _truncate(f"{ctx.workspace.rel(target)} ({len(lines)} lines)\n{body}{footer}")


def search(ctx: ToolContext, pattern: str, path: str = ".", glob: str = "*",
           ignore_case: bool = False) -> str:
    try:
        regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as exc:
        return f"ERROR: invalid regular expression: {exc}"
    base = ctx.workspace.resolve(path)
    files = [base] if base.is_file() else _walk_files(base)
    hits = []
    for file in files:
        rel = Path(os.path.relpath(file, base)).as_posix() if base.is_dir() else file.name
        if not _glob_match(rel, file.name, glob):
            continue
        try:
            if file.stat().st_size > MAX_SEARCH_FILE_BYTES:
                continue
            text = _read_text(file)
        except (OSError, WorkspaceError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                hits.append(f"{ctx.workspace.rel(file)}:{number}: {line.strip()[:300]}")
                if len(hits) >= MAX_MATCHES:
                    hits.append(f"... stopped at {MAX_MATCHES} matches; narrow the search")
                    return "\n".join(hits)
    return "\n".join(hits) if hits else "No matches."


# ---------------------------------------------------------------- write tools

def _remember(ctx: ToolContext, target: Path) -> None:
    key = ctx.workspace.rel(target)
    if key not in ctx.changes:
        before = _read_text(target) if target.exists() else None
        ctx.changes[key] = FileChange(before=before)


def write_file(ctx: ToolContext, path: str, content: str) -> str:
    target = ctx.workspace.resolve(path, for_write=True)
    if target.is_dir():
        return f"ERROR: {path} is a directory"
    _remember(ctx, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    return f"Wrote {ctx.workspace.rel(target)} ({len(content.splitlines())} lines)."


def edit_file(ctx: ToolContext, path: str, old_text: str, new_text: str,
              replace_all: bool = False) -> str:
    target = ctx.workspace.resolve(path, for_write=True)
    if not target.is_file():
        return f"ERROR: file not found: {path}"
    if not old_text:
        return "ERROR: old_text must not be empty; use write_file to create files"
    text = _read_text(target)
    count = text.count(old_text)
    if count == 0:
        return "ERROR: old_text was not found. Read the file again and copy the text exactly."
    if count > 1 and not replace_all:
        return (f"ERROR: old_text appears {count} times. Include more surrounding lines so it is "
                "unique, or set replace_all=true.")
    _remember(ctx, target)
    updated = text.replace(old_text, new_text) if replace_all else text.replace(old_text, new_text, 1)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    return f"Edited {ctx.workspace.rel(target)} ({count if replace_all else 1} replacement)."


def _shell_command(command: str) -> list[str]:
    if os.name == "nt":
        for candidate in (
            os.environ.get("DEPUTY_BASH"),
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
            shutil.which("bash"),
        ):
            # Skip the WSL launcher in System32; it runs in a different filesystem.
            # No login shell (-l): Git Bash's profile would cd to $HOME.
            if candidate and os.path.isfile(candidate) and "system32" not in candidate.lower():
                return [candidate, "-c", command]
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    shell = shutil.which("bash") or "/bin/sh"
    return [shell, "-c", command]


def safe_env(source: dict[str, str] | None = None) -> dict[str, str]:
    source = dict(os.environ if source is None else source)
    return {
        name: value for name, value in source.items()
        if not SECRET_NAME.search(name) and not name.upper().startswith(SECRET_PREFIXES)
    }


def _kill_tree(process: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                           capture_output=True, check=False)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (OSError, ProcessLookupError):
        process.kill()


def run_command(ctx: ToolContext, command: str, timeout: int | None = None) -> str:
    if not command.strip():
        return "ERROR: command is empty"
    limit = max(1, min(int(timeout or ctx.command_timeout), ctx.command_timeout))
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(
            subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(
        _shell_command(command), cwd=ctx.workspace.root, env=safe_env(),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs,
    )
    try:
        output, _ = process.communicate(timeout=limit)
        code: int | str = process.returncode
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        output, _ = process.communicate()
        code = f"timeout after {limit}s"
    text = (output or b"").decode("utf-8", errors="replace")
    ctx.commands.append({"command": command[:200], "exit": code})
    return _truncate(f"exit code: {code}\n{text}" if text else f"exit code: {code} (no output)")


# ------------------------------------------------------------------- registry

def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required, "additionalProperties": False},
        },
    }


_S = {"type": "string"}
READ_SCHEMAS = [
    _fn("list_files", "List files in the workspace. pattern is a glob like '**/*.py' or '*.md'.",
        {"pattern": _S, "path": _S}, []),
    _fn("read_file", "Read a text file with line numbers. Use offset/limit for long files.",
        {"path": _S, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, ["path"]),
    _fn("search", "Search file contents with a Python regular expression. glob filters file names.",
        {"pattern": _S, "path": _S, "glob": _S, "ignore_case": {"type": "boolean"}}, ["pattern"]),
]
WRITE_SCHEMAS = [
    _fn("write_file", "Create or overwrite a file with the full content.",
        {"path": _S, "content": _S}, ["path", "content"]),
    _fn("edit_file", "Replace exact text in a file. old_text must match exactly and be unique "
        "unless replace_all is true.",
        {"path": _S, "old_text": _S, "new_text": _S, "replace_all": {"type": "boolean"}},
        ["path", "old_text", "new_text"]),
    _fn("run_command", "Run a shell command in the workspace root (bash, or PowerShell on Windows "
        "without Git Bash). Use it for tests, builds and linters. Secrets are not available.",
        {"command": _S, "timeout": {"type": "integer"}}, ["command"]),
]

TOOLS: dict[str, Callable[..., str]] = {
    "list_files": list_files, "read_file": read_file, "search": search,
    "write_file": write_file, "edit_file": edit_file, "run_command": run_command,
}
WRITE_TOOLS = {"write_file", "edit_file", "run_command"}


def schemas(allow_writes: bool) -> list[dict]:
    return READ_SCHEMAS + (WRITE_SCHEMAS if allow_writes else [])


def call_tool(ctx: ToolContext, name: str, raw_arguments: str | None) -> str:
    if name not in TOOLS:
        return f"ERROR: unknown tool {name!r}"
    if name in WRITE_TOOLS and not ctx.allow_writes:
        return f"ERROR: {name} is not allowed in read-only mode"
    try:
        arguments = json.loads(raw_arguments or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be a JSON object")
    except (ValueError, json.JSONDecodeError) as exc:
        return f"ERROR: tool arguments were not valid JSON: {exc}"
    try:
        return TOOLS[name](ctx, **arguments)
    except TypeError as exc:
        return f"ERROR: wrong arguments for {name}: {exc}"
    except WorkspaceError as exc:
        return f"ERROR: {exc}"
    except OSError as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


def summarize_changes(ctx: ToolContext) -> list[dict]:
    rows = []
    for rel, change in sorted(ctx.changes.items()):
        target = ctx.workspace.root / rel
        after = _read_text(target) if target.exists() else None
        if after == change.before:
            continue
        before_lines = (change.before or "").splitlines()
        after_lines = (after or "").splitlines()
        added = removed = 0
        for line in difflib.unified_diff(before_lines, after_lines, lineterm="", n=0):
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
        status = "created" if change.before is None else ("deleted" if after is None else "modified")
        rows.append({"path": rel, "status": status, "added": added, "removed": removed})
    return rows
