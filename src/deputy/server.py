"""MCP server that exposes Deputy to Claude Code, Cursor, Codex or any MCP client."""
from __future__ import annotations

import asyncio
import dataclasses
import threading
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__, stats
from .agent import DeputyError, Usage, consult as run_consult, review as run_review, run_agent
from .config import (DEFAULT_MODE, ConfigError, Settings, load_settings, read_mode,
                     workspace_pinned)
from .diff import DiffError, collect_diff
from .workspace import Workspace, WorkspaceError, check_root

COMMON = """Deputy runs a cheaper model (by default DeepSeek V4.1 Flash with thinking on) as a
helper in this workspace. You are the lead: you plan, decide, write the important code and
verify. Deputy's output is never proof; check it against the code before relying on it.

Tools:
- `consult`: diverse second opinions (ideas, risks, alternatives) through 2-3 parallel `lenses`.
- `review`: independent reviewers hunt for defects in your uncommitted change (git diff).
- `investigate`: read-only search across many files; returns file:line leads.
- `delegate`: Deputy edits files and runs commands itself.
- `stats`: rough tokens and money saved so far.
If `status` shows the wrong workspace, pass `project_dir` (absolute path of the project).
Never put secrets in any argument: everything is sent to the configured model provider."""

POLICIES = {
    "accuracy": """MODE: ACCURACY (the user wants the most accurate result; cost is secondary).
- Write and change all code yourself. Do NOT use `delegate` unless the user explicitly asks you to.
- Before committing to an approach on a non-trivial task, call `consult` with your plan and 2-3
  lenses. Weigh the ideas below your own analysis; adopt only what you verify.
- After finishing a non-trivial change and before telling the user it is done, call `review`.
  Verify every finding against the code. Fix confirmed problems; briefly note rejected ones.
- Use `investigate` only to locate code; then read the cited lines yourself before acting.""",
    "lean": """MODE: LEAN (spend as few of your tokens as possible, with little loss of accuracy).
- Reading code is your biggest cost. Use `investigate` instead of opening many files yourself,
  then read only the lines it cites.
- `delegate` well-specified work that is big enough to pay off: changes across several files,
  repetitive edits, test suites, boilerplate, migrations. Write changes of a few lines yourself:
  checking a small delegated diff costs about as much as writing it.
- Keep design decisions, unclear bugs, security-sensitive code and subtle logic yourself.
- Check delegated work cheaply but always: run the tests and read the diff, not whole files.
- Call `review` on non-trivial changes before you say they are done; skip it for small changes
  whose tests pass. Call `consult` only at real decision points.""",
    "balanced": """MODE: BALANCED (accuracy first, but save tokens on low-risk work).
- Write logic, algorithms, APIs, security-sensitive and tricky code yourself.
- You may `delegate` low-risk mechanical work: boilerplate, renames, formatting, test
  scaffolding, repetitive edits across many files. Review every delegated diff yourself.
- Use `consult` before non-trivial decisions and `review` before declaring non-trivial work done.
- Use `investigate` for wide reading, then confirm the cited lines yourself.""",
    "partner": """MODE: PARTNER. The user chose this mode: they want Deputy to do the low-level work while
you lead. This is the user's instruction for this session, not a suggestion, and it applies to
small tasks too.
- Before you read or edit files for a coding task, decide which parts are low-level and hand them
  to Deputy: reading and searching code (`investigate`), and boilerplate, renames, formatting,
  tests, repetitive or multi-file edits and well-specified implementation (`delegate`). Do the
  work yourself only for a one-line change, or for parts that need judgment.
- Ask Deputy for ideas: call `consult` with 2-3 lenses before non-trivial decisions and when you
  are stuck. Write your own view in `my_view` first.
- Deputy makes mistakes. Treat everything it returns as a draft from a junior colleague: read
  every delegated diff, run the tests, check the file:line citations before acting on them, and
  adopt an idea only after checking it against the code.
- Keep design, ambiguous bugs, security-sensitive code and final decisions yourself.
- Call `review` before you say non-trivial work is done.""",
    "savings": """MODE: SAVINGS (the user wants to save tokens).
- `delegate` well-specified coding work: multi-file edits, refactors, tests, boilerplate,
  migrations, lint and type fixes. Give the goal, scope, constraints and a verify command.
  Decide to delegate BEFORE reading lots of source yourself.
- Keep architecture, ambiguous root-cause analysis and security-sensitive changes yourself.
- Always verify delegated work: read the changed files, check the diff, run the tests.
- Use `investigate` for wide reading, `consult` at decision points, `review` before done.""",
}


def build_instructions(mode: str) -> str:
    return f"{COMMON}\n\n{POLICIES.get(mode, POLICIES[DEFAULT_MODE])}"


def _startup_mode() -> str:
    try:
        return read_mode()
    except ConfigError:
        return DEFAULT_MODE


mcp = FastMCP("deputy", instructions=build_instructions(_startup_mode()), log_level="WARNING")
# FastMCP otherwise reports the SDK's version in the initialize handshake.
mcp._mcp_server.version = __version__

_code_lock = threading.Lock()
_session_lock = threading.Lock()
_session_records: list[stats.Record] = []

Thinking = Literal["high", "max"]


def make_client(settings: Settings) -> Any:
    from openai import OpenAI

    return OpenAI(base_url=settings.base_url, api_key=settings.api_key, timeout=300.0, max_retries=0)


def _uri_to_path(uri: str) -> Path | None:
    parsed = urlparse(str(uri))
    if parsed.scheme != "file":
        return None
    path = url2pathname(unquote(parsed.path))
    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"
    return Path(path)


async def _client_root(ctx: Context | None) -> Path | None:
    """Ask the MCP client which folder is open (Cursor, VS Code and others support "roots")."""
    if ctx is None:
        return None
    try:
        params = ctx.session.client_params
        if params is None or params.capabilities.roots is None:
            return None
        result = await asyncio.wait_for(ctx.session.list_roots(), timeout=5)
    except Exception:  # noqa: BLE001 - roots are optional; any failure means "unknown"
        return None
    for root in result.roots:
        path = _uri_to_path(str(root.uri))
        if path is not None and path.is_dir():
            return path
    return None


async def _ready_settings(ctx: Context | None = None, project_dir: str = "") -> Settings:
    """Load settings and pick the workspace: DEPUTY_WORKSPACE, then project_dir, then the
    client's root folder, then Claude Code's project folder or the current directory."""
    try:
        settings = load_settings()
        if not workspace_pinned():
            chosen = Path(project_dir).expanduser() if project_dir.strip() else await _client_root(ctx)
            if chosen is not None:
                settings = dataclasses.replace(settings, workspace=chosen.resolve())
        check_root(settings.workspace)
    except (ConfigError, WorkspaceError) as exc:
        raise ToolError(f"Deputy is not configured correctly: {exc}. If the workspace is wrong, "
                        "pass project_dir with the project's absolute path.") from None
    if not settings.api_key:
        raise ToolError(
            "Deputy has no API key. Set DEEPINFRA_API_KEY (or DEPUTY_API_KEY) in your "
            "environment, then restart your editor. See the README for the DeepInfra setup."
        )
    return settings


def _finish(tool: str, text: str, usage: Usage, cost: float | None, settings: Settings) -> str:
    """Record the run for the savings estimate and append a one-line summary."""
    record = stats.estimate(tool, usage, cost, text, settings)
    with _session_lock:
        _session_records.append(record)
    stats.append(record, settings)
    line = stats.footer(record, settings)
    return f"{text}\n\n{line}" if line else text


@mcp.tool(annotations=ToolAnnotations(
    title="Get diverse second opinions from Deputy", readOnlyHint=True, destructiveHint=False,
    idempotentHint=False, openWorldHint=True))
async def consult(question: str, context: str = "", lenses: list[str] | None = None,
                  my_view: str = "", thinking: Thinking | None = None, project_dir: str = "",
                  ctx: Context | None = None) -> str:
    """Brainstorm with a cheaper model: ideas, risks and alternatives you may have missed.
    Use it before committing to an approach, when stuck, or before declaring a task done.

    question: what you are deciding, including your current plan if you have one.
    context: relevant facts, constraints and what you already ruled out.
    lenses: up to 4 angles, each answered independently in parallel, for example
      ["simplest approach", "edge cases and failure modes", "performance"].
    my_view: your own conclusion, written BEFORE you see Deputy's ideas. It is not sent to
      Deputy, so its ideas stay independent; it is echoed back so you can compare honestly.
    project_dir: absolute path of the project, only if Deputy picked the wrong folder.

    The answers are UNVERIFIED suggestions from a weaker model. Weigh them below your own
    analysis, check them against the code, and adopt only what holds up."""
    settings = await _ready_settings(ctx, project_dir)
    try:
        text, usage, cost = await asyncio.to_thread(
            run_consult, question, settings, lambda: make_client(settings), context=context,
            lenses=lenses, effort=thinking or settings.effort)
    except (DeputyError, WorkspaceError) as exc:
        raise ToolError(f"Deputy failed: {exc}") from None
    if my_view.strip():
        text = (f"YOUR VIEW BEFORE CONSULTING (not shown to Deputy): {my_view.strip()}\n"
                "Keep it unless an idea below survives your own check.\n\n" + text)
    return _finish("consult", text, usage, cost, settings)


@mcp.tool(annotations=ToolAnnotations(
    title="Review your change with Deputy", readOnlyHint=True, destructiveHint=False,
    idempotentHint=False, openWorldHint=True))
async def review(focus: str = "", diff: str = "", base: str = "", paths: list[str] | None = None,
                 lenses: list[str] | None = None, thinking: Thinking | None = None,
                 project_dir: str = "", ctx: Context | None = None) -> str:
    """Have independent cheap reviewers hunt for defects in a change, one per lens, in parallel.
    By default it reviews your uncommitted changes (git diff against HEAD, plus new files).

    focus: what the change is supposed to do, so reviewers can spot mismatches.
    diff: the change to review, if you do not want the automatic git diff.
    base: compare against this revision instead of HEAD (for example "main").
    paths: limit the review to these files or folders.
    lenses: up to 4 review angles; default ["correctness and logic bugs",
      "edge cases, error handling and missing tests"].
    project_dir: absolute path of the project, only if Deputy picked the wrong folder.

    Findings are UNVERIFIED and may be false positives. Verify each against the code; fix only
    what you confirm, and tell the user which findings you rejected and why."""
    settings = await _ready_settings(ctx, project_dir)
    try:
        text = diff.strip() or await asyncio.to_thread(
            collect_diff, Workspace(settings.workspace), base=base, paths=paths)
        result, usage, cost = await asyncio.to_thread(
            run_review, text, settings, lambda: make_client(settings), focus=focus,
            lenses=lenses, effort=thinking or settings.effort)
    except (DeputyError, DiffError, WorkspaceError) as exc:
        raise ToolError(f"Deputy review failed: {exc}") from None
    return _finish("review", result, usage, cost, settings)


@mcp.tool(annotations=ToolAnnotations(
    title="Investigate the codebase with Deputy (read-only)", readOnlyHint=True,
    destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def investigate(question: str, context: str = "", thinking: Thinking | None = None,
                      workdir: str = ".", project_dir: str = "",
                      ctx: Context | None = None) -> str:
    """Ask Deputy a question that needs a lot of reading: where something is handled, how a flow
    works, what a large log says. Deputy can only list, read and search files. Returns a compact
    answer with file:line evidence. Treat it as leads: read the cited lines before acting.
    project_dir: absolute path of the project, only if Deputy picked the wrong folder."""
    settings = await _ready_settings(ctx, project_dir)
    try:
        result = await asyncio.to_thread(
            run_agent, question, settings, make_client(settings), mode="readonly",
            context=context, effort=thinking or settings.effort, workdir=workdir)
    except (DeputyError, WorkspaceError) as exc:
        raise ToolError(f"Deputy failed: {exc}") from None
    return _finish("investigate", result.to_text(), result.usage, result.cost, settings)


@mcp.tool(annotations=ToolAnnotations(
    title="Delegate coding work to Deputy", readOnlyHint=False, destructiveHint=True,
    idempotentHint=False, openWorldHint=True))
async def delegate(task: str, context: str = "", thinking: Thinking | None = None,
                   workdir: str = ".", project_dir: str = "", ctx: Context | None = None) -> str:
    """Hand a well-specified coding task to Deputy. It reads and edits files and runs commands
    in the workspace on its own, then returns a short report with the files it changed.
    In accuracy mode, use this only when the user explicitly asks for delegation.

    task: the goal, scope (files or folders), constraints and acceptance criteria.
    context: facts Deputy cannot discover itself (decisions made, conventions, error messages).
    thinking: "high" (default) or "max" for hard tasks.
    workdir: subfolder of the workspace to treat as the root (default: whole workspace).
    project_dir: absolute path of the project, only if Deputy picked the wrong folder.

    Verify the result yourself before relying on it: review the changed files and run tests."""
    settings = await _ready_settings(ctx, project_dir)
    if not _code_lock.acquire(blocking=False):
        raise ToolError("Deputy is already running a coding task; wait for it to finish first.")
    try:
        result = await asyncio.to_thread(
            run_agent, task, settings, make_client(settings), mode="code", context=context,
            effort=thinking or settings.effort, workdir=workdir)
    except (DeputyError, WorkspaceError) as exc:
        raise ToolError(f"Deputy failed: {exc}") from None
    finally:
        _code_lock.release()
    return _finish("delegate", result.to_text(), result.usage, result.cost, settings)


@mcp.tool(name="stats", annotations=ToolAnnotations(
    title="Deputy savings", readOnlyHint=True, destructiveHint=False, idempotentHint=True,
    openWorldHint=False))
def stats_report() -> str:
    """Show roughly how many tokens and how much money Deputy saved: this session, today, the
    last 7 days and all time. Makes no network calls."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        return f"Deputy configuration error: {exc}"
    with _session_lock:
        session = list(_session_records)
    return stats.report(settings, session)


@mcp.tool(annotations=ToolAnnotations(
    title="Deputy status", readOnlyHint=True, destructiveHint=False, idempotentHint=True,
    openWorldHint=False))
async def status(project_dir: str = "", ctx: Context | None = None) -> str:
    """Show Deputy's mode, model, thinking level, workspace, whether a key is set, and what this
    session has spent and saved. Makes no network calls to the model provider."""
    lines = [f"Deputy {__version__}"]
    try:
        settings = load_settings()
        if not workspace_pinned():
            chosen = Path(project_dir).expanduser() if project_dir.strip() else await _client_root(ctx)
            if chosen is not None:
                settings = dataclasses.replace(settings, workspace=chosen.resolve())
    except ConfigError as exc:
        return f"Deputy {__version__}: configuration error: {exc}"
    for key, value in settings.describe().items():
        lines.append(f"{key}: {value}")
    try:
        check_root(settings.workspace)
    except WorkspaceError as exc:
        lines.append(f"workspace problem: {exc} (pass project_dir)")
    with _session_lock:
        t = stats.totals(list(_session_records))
    lines.append(f"this session: {t.runs} runs, Deputy cost ${t.deputy_cost:.4f}, "
                 f"saved about ${t.saved:.4f} on replaced work (rough; see the stats tool)")
    lines.append("")
    lines.append(POLICIES[settings.mode])
    return "\n".join(lines)


def main() -> None:
    mcp.run()
