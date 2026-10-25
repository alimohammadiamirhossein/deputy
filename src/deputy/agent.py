"""The deputy's agent loop: an OpenAI-compatible tool-calling loop in the workspace."""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Literal

from .config import Settings, is_deepseek_api, is_xai_api
from .tools import ToolContext, call_tool, schemas, summarize_changes
from .workspace import Workspace

Mode = Literal["code", "readonly", "consult", "review"]

SYSTEM_BASE = """You are Deputy, a careful sub-agent working for a stronger lead agent.
The lead agent cannot watch you work. It only sees your final message, so make it accurate and short.
Workspace root: {root}
Today's date: {today}. Libraries, APIs and model versions newer than your training data exist.
If you do not recognize one, mark it [unverified] instead of calling it wrong or nonexistent.

Rules:
- Work only through the tools. Paths are relative to the workspace root.
- Read before you change anything. Keep changes minimal and focused on the task.
- Never claim something you did not check. If you could not do something, say so plainly.
- Do not read secrets or credential files, and do not touch files unrelated to the task.
- Never change anything outside the workspace: do not install packages globally or for the
  user, and do not edit system or user config. If a tool or dependency is missing, say so in
  your report instead of installing it, unless the task explicitly asks you to install it.
"""

MODE_PROMPTS = {
    "code": """Mode: CODE. You can create and edit files and run commands.
- Meet the task's acceptance criteria. Run the relevant tests, build or linter when the project has one.
- Stop when the task is done. Do not start unrelated improvements.

Final message format:
RESULT: done | partial | failed
SUMMARY: 2-5 sentences on what you changed and why.
VERIFY: the commands you ran and their outcome, or what the lead agent should check.
OPEN ISSUES: anything unfinished, risky or uncertain, or "none".""",
    "readonly": """Mode: READ-ONLY. You can list, read and search files. You cannot change anything.
Answer with specific evidence. The lead agent pays to read your answer, so be concise.

Final message format:
ANSWER: the direct answer.
EVIDENCE: bullets of path:line references, each with a one-line note.
UNCERTAIN: what you could not confirm, or "none".""",
    "consult": """Mode: CONSULT. The lead agent wants ideas, risks and alternatives it may have missed.
It will treat your ideas as unverified suggestions and make the final decision itself.
You can read and search files (read-only) to ground your ideas. Favor breadth and non-obvious
points over generic advice. Disagree with the lead agent's plan if you have a reason to.
A lens changes what you focus on, not whether you tell the truth: call out bad ideas and
acknowledge good ones whatever the lens.
{lens}
Final message format: a numbered list of 3-7 ideas. For each:
- IDEA: one sentence.
- WHY: the reasoning, citing files when relevant.
- CONFIDENCE: low | medium | high
Then one line: BIGGEST RISK: ...""",
    "review": """Mode: REVIEW. You are an adversarial code reviewer. Your job is to break confidence
in the change in the task (a diff), not to validate it. You can read and search files
(read-only) to check how the changed code is used.
{lens}
Attack surface to consider: wrong logic or off-by-one errors; null, empty, zero and boundary
inputs; error handling and timeouts; data loss or corruption; retries and idempotency; races and
stale state; auth and trust boundaries; untrusted input; API, schema or version mismatches with
callers; behavior changes for existing callers; missing or wrong tests.

Rules:
- Report only problems you can support with the code. No style nitpicks, no generic advice, no praise.
- Check each suspicion against the surrounding code before reporting it.
- Prefer one strong finding over several weak ones.
- If no substantive problem can be supported, answer "VERDICT: approve" and list what you checked.
  Inventing issues is worse than missing a minor one.

Final message format:
VERDICT: approve | needs-attention
Then one block per finding, most severe first:
- SEVERITY: critical | major | minor
- WHERE: path:line
- WHAT GOES WRONG: one sentence.
- WHY: why this code path is vulnerable, citing code.
- IMPACT: what the user or system would experience.
- REPRO: a command or test that would show it, if you can think of one.
- FIX: the smallest change that fixes it.
- CONFIDENCE: low | medium | high""",
}

CONSULT_HEADER = (
    "SECOND OPINION from {model} (a cheaper model). Treat every item as an unverified "
    "suggestion: weigh it below your own analysis, check it against the code, and adopt "
    "only what holds up. Change your plan only when an argument survives your own check, "
    "not because the helper disagrees."
)
REVIEW_HEADER = (
    "REVIEW by {model} (a cheaper model). These findings are UNVERIFIED and may include "
    "false positives. The lenses ran independently, so a problem flagged by more than one lens "
    "is more likely real. Check each finding against the code (run its REPRO when there is "
    "one), then mark it accept, dismiss (with a reason) or defer, fix only what you confirm, "
    "and tell the user what you dismissed and why."
)
DEFAULT_REVIEW_LENSES = ["correctness and logic bugs", "edge cases, error handling and missing tests"]

# When a capped run stops early, one last call without tools asks for the write-up. It thinks a
# little: with thinking off, a reviewer reasons in its answer and leaves retracted findings in it.
WRAP_UP = ("Stop here: you reached the {reason} for this pass. Do not call any tools. Write your "
           "final message now, in the required format, using only what you have already checked. "
           "End with a line NOT CHECKED: listing what you did not get to, or \"none\".")
# A reviewer cut off mid-check otherwise reports its open suspicions as findings (benchmark: every
# cut-off lens on a clean diff raised a major false alarm), so only confirmed problems count.
REVIEW_WRAP_UP = (
    "Stop here: you reached the {reason} for this pass. Do not call any tools.\n"
    "Before you write, sort every point you have into one of two groups:\n"
    "- CONFIRMED: you read the exact lines involved and can name an input that goes wrong.\n"
    "- UNCONFIRMED: anything else, including suspicions you had not finished checking and code "
    "you did not read.\n"
    "Only CONFIRMED points are findings; write them in the required format. UNCONFIRMED points are "
    "never findings: give them no severity and no finding block. If nothing is CONFIRMED, answer "
    "VERDICT: approve. End with a line NOT CHECKED: followed by one line per UNCONFIRMED point, "
    "or \"none\".")
WRAP_UP_REASONS = {"time_limit": "time limit", "timeout": "time limit",
                   "output_limit": "thinking budget", "truncated": "length limit",
                   "max_turns": "turn limit", "budget": "token budget"}
WRAP_UP_EFFORT = "low"
WRAP_UP_TOKENS = 6_000
WRAP_UP_SECONDS = 120
MIN_TURN_TOKENS = 256  # below this, a turn could not say anything useful


class DeputyError(RuntimeError):
    """A run could not start or the provider failed in a way the model cannot fix."""


class _OutOfTime(Exception):
    """A request timed out because the run's deadline passed."""


@dataclass
class Usage:
    requests: int = 0
    prompt: int = 0
    cached: int = 0
    completion: int = 0
    reasoning: int = 0

    @property
    def total(self) -> int:
        return self.prompt + self.completion

    def add(self, usage: Any) -> None:
        self.requests += 1
        if usage is None:
            return
        self.prompt += int(getattr(usage, "prompt_tokens", 0) or 0)
        self.completion += int(getattr(usage, "completion_tokens", 0) or 0)
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        self.cached += int(getattr(prompt_details, "cached_tokens", 0) or 0)
        completion_details = getattr(usage, "completion_tokens_details", None)
        self.reasoning += int(getattr(completion_details, "reasoning_tokens", 0) or 0)

    def merge(self, other: "Usage") -> None:
        for name in ("requests", "prompt", "cached", "completion", "reasoning"):
            setattr(self, name, getattr(self, name) + getattr(other, name))

    def cost(self, settings: Settings) -> float | None:
        if not settings.has_prices:
            return None
        cached = min(self.cached, self.prompt)
        return ((self.prompt - cached) * settings.price_input + cached * settings.price_cached
                + self.completion * settings.price_output) / 1_000_000


@dataclass
class RunResult:
    mode: str
    # completed | max_turns | budget | timeout | truncated | time_limit | output_limit | cancelled
    status: str
    final_message: str
    turns: int
    seconds: float
    usage: Usage
    model: str
    effort: str
    files_changed: list[dict] = field(default_factory=list)
    commands: list[dict] = field(default_factory=list)
    cost: float | None = None

    def stats_line(self) -> str:
        u = self.usage
        cost = f" | est. cost ${self.cost:.4f}" if self.cost is not None else ""
        return (f"{self.status} | {self.turns} turns | {self.seconds:.0f}s | "
                f"{u.prompt:,} in ({u.cached:,} cached), {u.completion:,} out "
                f"({u.reasoning:,} thinking){cost}")

    def to_text(self) -> str:
        lines = [f"Deputy {self.mode} run [{self.model}, thinking {self.effort}]: {self.stats_line()}"]
        if self.status != "completed":
            lines.append(f"WARNING: the run ended early ({self.status}). Treat the report as incomplete.")
        if self.files_changed:
            lines.append("Files changed (review these before relying on them):")
            marks = {"created": "A", "modified": "M", "deleted": "D"}
            for row in self.files_changed:
                lines.append(f"  {marks[row['status']]} {row['path']} (+{row['added']} -{row['removed']})")
        if self.commands:
            shown = "; ".join(f"`{c['command']}` -> {c['exit']}" for c in self.commands[-8:])
            lines.append(f"Commands run ({len(self.commands)}): {shown}")
            lines.append("Note: commands may also have changed files that are not listed above.")
        lines.append("--- Deputy's report ---")
        lines.append(self.final_message.strip() or "(empty report)")
        return "\n".join(lines)


# Grok models whose reasoning effort cannot be set (or where the parameter is undocumented), so
# Deputy does not send it: the coding models and grok-4.20.
XAI_FIXED_REASONING = ("grok-build", "grok-code-fast", "grok-4.20")


def xai_reasoning_effort(model: str, effort: str) -> str | None:
    """Deputy's thinking level as xAI's reasoning_effort, or None to leave it out."""
    name = model.lower().rsplit("/", 1)[-1]
    if name.startswith(XAI_FIXED_REASONING) or "non-reasoning" in name:
        return None
    if effort == "max":
        return "xhigh"
    if effort == "none" and not name.startswith("grok-4.3"):
        return "low"  # only grok-4.3 can turn reasoning off; later models always reason
    return effort


def build_request(settings: Settings, effort: str, messages: list[dict],
                  tool_schemas: list[dict], max_tokens: int | None = None) -> dict:
    limit = max_tokens or settings.max_output_tokens
    request: dict[str, Any] = {"model": settings.model, "messages": messages}
    if tool_schemas:
        request["tools"] = tool_schemas
    if is_xai_api(settings.base_url):
        # xAI deprecated max_tokens; max_completion_tokens leaves out reasoning tokens.
        request["max_completion_tokens"] = limit
        xai_effort = xai_reasoning_effort(settings.model, effort)
        if xai_effort:
            request["reasoning_effort"] = xai_effort
        return request
    request["max_tokens"] = limit
    if is_deepseek_api(settings.base_url):
        # DeepSeek's own API switches thinking with a separate field.
        request["extra_body"] = {"thinking": {"type": "disabled" if effort == "none" else "enabled"}}
        if effort != "none":
            request["reasoning_effort"] = effort
    else:
        # DeepInfra and other OpenAI-compatible hosts: thinking is OFF unless asked for.
        request["reasoning_effort"] = effort
    return request


def _complete(client: Any, request: dict, deadline: float, timeout: float | None = None) -> Any:
    """Send one request with retries. `timeout` bounds this request; with it, a timeout after the
    deadline raises _OutOfTime instead of DeputyError, so the caller can still wrap up."""
    import openai

    delays = (2, 6, 15)
    bad_key = DeputyError("the provider rejected the API key (check DEPUTY_API_KEY, or "
                          "DEEPINFRA_API_KEY / XAI_API_KEY for your provider)")
    for attempt in range(len(delays) + 1):
        # Recompute on every attempt so a retry cannot run past the deadline.
        extra = {"timeout": max(1.0, min(timeout, deadline - time.monotonic()))} if timeout else {}
        try:
            return client.chat.completions.create(**request, **extra)
        except openai.AuthenticationError:
            raise bad_key from None
        except openai.NotFoundError:
            raise DeputyError(f"the provider does not know the model {request['model']!r}") from None
        except openai.BadRequestError as exc:
            if "api key" in str(exc).lower():  # xAI answers a wrong key with 400, not 401
                raise bad_key from None
            raise DeputyError(f"the provider rejected the request: {exc}") from None
        except (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError) as exc:
            if timeout and isinstance(exc, openai.APITimeoutError) and time.monotonic() >= deadline - 1:
                raise _OutOfTime from None
            if attempt == len(delays) or time.monotonic() + delays[attempt] > deadline:
                raise DeputyError(f"the provider is unavailable: {exc}") from None
            time.sleep(delays[attempt])
    raise AssertionError("unreachable")


def _reasoning_of(message: Any) -> str | None:
    for name in ("reasoning_content", "reasoning"):
        value = getattr(message, name, None)
        if isinstance(value, str) and value:
            return value
    extra = getattr(message, "model_extra", None) or {}
    value = extra.get("reasoning_content")
    return value if isinstance(value, str) and value else None


def run_agent(
    task: str,
    settings: Settings,
    client: Any,
    *,
    mode: Mode = "code",
    context: str = "",
    effort: str | None = None,
    workdir: str = ".",
    lens: str = "",
    max_turns: int | None = None,
    progress: Callable[[int, str], None] | None = None,
    time_limit: float | None = None,
    output_limit: int | None = None,
    wrap_up: bool = False,
    cancel: threading.Event | None = None,
) -> RunResult:
    """Run the tool loop. `time_limit` (seconds) and `output_limit` (output tokens, thinking
    included) cap this run below the global limits. With `wrap_up`, a run that stops early gets
    one last call, without tools and with light thinking, to write up what it already checked.
    The run stops before its next turn or tool call once `cancel` is set. `progress(turn, tool)`
    is called at the start of each turn (tool "") and before each tool call."""
    if not task or not task.strip():
        raise DeputyError("task must not be empty")
    effort = effort or settings.effort
    root = Workspace(settings.workspace)
    workspace = Workspace(root.resolve(workdir)) if workdir not in ("", ".") else root
    ctx = ToolContext(workspace=workspace, command_timeout=settings.command_timeout,
                      allow_writes=(mode == "code"))
    tool_schemas = schemas(ctx.allow_writes)

    mode_prompt = MODE_PROMPTS[mode]
    if mode in ("consult", "review"):
        mode_prompt = mode_prompt.format(lens=f"Lens for this pass: {lens}\n" if lens else "")
    system = SYSTEM_BASE.format(root=workspace.root, today=date.today().isoformat()) + "\n" + mode_prompt
    user = f"TASK:\n{task.strip()}"
    if context and context.strip():
        user += f"\n\nCONTEXT FROM THE LEAD AGENT:\n{context.strip()}"
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    usage = Usage()
    started = time.monotonic()
    deadline = started + min(settings.run_timeout, time_limit or settings.run_timeout)
    limit = max_turns or settings.max_turns
    status, final, turns = "max_turns", "", 0
    # xAI routes requests with the same conversation id to the same server, so the growing
    # prompt stays cached; without it, turns often pay the full input price.
    headers = {"x-grok-conv-id": uuid.uuid4().hex} if is_xai_api(settings.base_url) else None

    for turns in range(1, limit + 1):
        if cancel is not None and cancel.is_set():
            status = "cancelled"
            break
        if progress:
            progress(turns, "")
        if time.monotonic() > deadline:
            status = "time_limit" if time_limit else "timeout"
            break
        if usage.total >= settings.max_run_tokens:
            status = "budget"
            break
        turn_tokens = None
        if output_limit:
            left = output_limit - usage.completion
            if left < MIN_TURN_TOKENS:
                status = "output_limit"
                break
            turn_tokens = min(settings.max_output_tokens, left)
        request = build_request(settings, effort, messages, tool_schemas, turn_tokens)
        if headers:
            request["extra_headers"] = headers
        try:
            response = _complete(client, request, deadline,
                                 timeout=max(1.0, deadline - time.monotonic()) if time_limit else None)
        except _OutOfTime:
            status = "time_limit"
            break
        usage.add(getattr(response, "usage", None))
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        calls = list(message.tool_calls or [])

        assistant: dict[str, Any] = {"role": "assistant", "content": content}
        if calls:
            assistant["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                for c in calls
            ]
            # DeepSeek's thinking mode expects its reasoning to be sent back while a
            # tool-calling turn is still in progress.
            reasoning = _reasoning_of(message)
            if settings.keep_reasoning and reasoning:
                assistant["reasoning_content"] = reasoning
        messages.append(assistant)

        if not calls:
            final = content
            status = "completed"
            if getattr(choice, "finish_reason", "") == "length":
                out_of_budget = output_limit and output_limit - usage.completion < MIN_TURN_TOKENS
                status = "output_limit" if out_of_budget else "truncated"
            break

        for call in calls:
            if cancel is not None and cancel.is_set():
                status = "cancelled"
                break
            if progress:
                progress(turns, call.function.name)
            output = call_tool(ctx, call.function.name, call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
        if status == "cancelled":
            break
        if content:
            final = content  # keep the latest commentary in case the run stops early

    if wrap_up and status not in ("completed", "cancelled"):
        prompt = REVIEW_WRAP_UP if mode == "review" else WRAP_UP
        final = _wrap_up(client, settings, messages, tool_schemas, status, usage, prompt) or final

    result = RunResult(
        mode=mode, status=status, final_message=final, turns=turns,
        seconds=time.monotonic() - started, usage=usage, model=settings.model, effort=effort,
        files_changed=summarize_changes(ctx), commands=ctx.commands,
    )
    result.cost = usage.cost(settings)
    return result


def _wrap_up(client: Any, settings: Settings, messages: list[dict], tool_schemas: list[dict],
             status: str, usage: Usage, prompt: str = WRAP_UP) -> str | None:
    """Ask a run that stopped early for its final message. Returns None if that fails too."""
    reason = WRAP_UP_REASONS.get(status, "limit")
    messages.append({"role": "user", "content": prompt.format(reason=reason)})
    request = build_request(settings, WRAP_UP_EFFORT, messages, tool_schemas, WRAP_UP_TOKENS)
    if tool_schemas:
        request["tool_choice"] = "none"
    try:
        response = _complete(client, request, time.monotonic() + WRAP_UP_SECONDS,
                             timeout=WRAP_UP_SECONDS)
    except (DeputyError, _OutOfTime):
        return None
    usage.add(getattr(response, "usage", None))
    return (response.choices[0].message.content or "").strip() or None


def parallel_passes(task: str, settings: Settings, client_factory: Callable[[], Any], *,
                    mode: Mode, header: str, context: str = "", lenses: list[str] | None = None,
                    effort: str | None = None, max_turns: int = 15,
                    cancel: threading.Event | None = None,
                    progress: Callable[[str], None] | None = None) -> tuple[str, Usage, float | None]:
    """Run one read-only pass per lens in parallel and merge the answers under a warning header.
    `progress` gets a short message, such as "edge cases: turn 2, read_file", as lenses work."""
    lenses = [lens.strip() for lens in (lenses or []) if lens and lens.strip()][:4] or [""]

    def one(lens: str) -> RunResult:
        def step(turn: int, tool: str) -> None:
            if progress:
                progress(f"{lens or mode}: turn {turn}, {tool or 'thinking'}")

        return run_agent(task, settings, client_factory(), mode=mode, context=context,
                         effort=effort, lens=lens, max_turns=min(max_turns, settings.max_turns),
                         time_limit=settings.lens_timeout, output_limit=settings.lens_max_output,
                         wrap_up=True, cancel=cancel, progress=step)

    with ThreadPoolExecutor(max_workers=len(lenses)) as pool:
        results = list(pool.map(one, lenses))

    total = Usage()
    for result in results:
        total.merge(result.usage)
    parts = [header.format(model=settings.model)]
    for lens, result in zip(lenses, results):
        title = f"Lens: {lens}" if lens else "General"
        note = ""
        if result.status != "completed":
            note = (f"NOTE: this lens stopped at its {WRAP_UP_REASONS.get(result.status, 'limit')} "
                    "and reported only what it had checked, so it may have missed things.\n")
        parts.append(f"\n=== {title} [{result.stats_line()}] ===\n{note}"
                     f"{result.final_message.strip() or '(no report)'}")
    return "\n".join(parts), total, total.cost(settings)


def consult(question: str, settings: Settings, client_factory: Callable[[], Any], *,
            context: str = "", lenses: list[str] | None = None, effort: str | None = None,
            max_turns: int = 15, cancel: threading.Event | None = None,
            progress: Callable[[str], None] | None = None) -> tuple[str, Usage, float | None]:
    """Ask the deputy for ideas, optionally from several angles in parallel."""
    return parallel_passes(question, settings, client_factory, mode="consult", header=CONSULT_HEADER,
                           context=context, lenses=lenses, effort=effort, max_turns=max_turns,
                           cancel=cancel, progress=progress)


def review(diff: str, settings: Settings, client_factory: Callable[[], Any], *, focus: str = "",
           lenses: list[str] | None = None, effort: str | None = None,
           max_turns: int = 20, cancel: threading.Event | None = None,
           progress: Callable[[str], None] | None = None) -> tuple[str, Usage, float | None]:
    """Have independent reviewers look for defects in a diff, one per lens, in parallel."""
    task = "Review this change for defects.\n"
    if focus.strip():
        task += f"What the change is meant to do, per the lead agent: {focus.strip()}\n"
    task += f"\nDIFF:\n{diff}"
    return parallel_passes(task, settings, client_factory, mode="review", header=REVIEW_HEADER,
                           lenses=lenses or DEFAULT_REVIEW_LENSES, effort=effort,
                           max_turns=max_turns, cancel=cancel, progress=progress)
