"""`deputy setup cursor|codex|claude`: add Deputy to an editor's MCP config, safely.

Existing config files are backed up before they change, and an existing "deputy" entry is never
overwritten unless --force is given. API keys are never written to config files: the editor
forwards the provider's key (DEEPINFRA_API_KEY, or XAI_API_KEY for Grok) from your environment.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .config import DEFAULT_MODE, DEFAULT_PROVIDER, MODES, PROVIDER_ALIASES, PROVIDERS

GIT_SOURCE = "git+https://github.com/alimohammadiamirhossein/deputy"
PYPI_PACKAGE = "deputy-cc"
# Per provider: the key variable, the model named in the rules, and the variables the editor
# passes through. For xAI only XAI_API_KEY is passed, never DEPUTY_API_KEY or the DeepInfra key,
# so a key meant for DeepInfra cannot reach xAI.
KEY_VAR = {"deepinfra": "DEEPINFRA_API_KEY", "xai": "XAI_API_KEY"}
MODEL_NAME = {"deepinfra": "DeepSeek V4.1 Flash", "xai": "Grok"}
FORWARDED_ENV = {
    "deepinfra": ["DEEPINFRA_API_KEY", "DEPUTY_API_KEY", "DEPUTY_THINKING", "DEPUTY_LEAD_MODEL"],
    "xai": ["XAI_API_KEY", "DEPUTY_THINKING", "DEPUTY_MODEL", "DEPUTY_LEAD_MODEL"],
}

RULES_TEMPLATE = """You can call Deputy, an MCP server that runs a cheaper model ({model_name}) as
a helper in this project. You are the lead: you plan, decide, write the important code and verify.
Deputy's output is never proof; check it against the code before relying on it.

Tools:
- `consult`: second opinions from 2-3 independent `lenses` before a non-trivial decision. Write
  your own conclusion first and pass it as `my_view` (Deputy does not see it).
- `review`: independent reviewers hunt for bugs in your uncommitted change (git diff). Call it
  before you say a non-trivial change is done; verify every finding; fix only what you confirm.
- `investigate`: read-only search across many files; returns file:line leads to check yourself.
- `delegate`: Deputy edits files and runs commands itself. {delegate_rule}
- `stats`: rough tokens and money saved. `status`: settings and the workspace Deputy uses.

If `status` shows the wrong workspace, pass `project_dir` with the project's absolute path.
Never put secrets in tool arguments: they are sent to the model provider.
Change your plan only when Deputy's argument survives your own check, not because it disagrees.
"""

DELEGATE_RULES = {
    "accuracy": "Use it only when the user explicitly asks; otherwise write the code yourself.",
    "lean": "Use it for well-specified work big enough to pay off (multi-file or repetitive edits, "
            "tests, boilerplate) and `investigate` instead of reading many files yourself; write "
            "small changes yourself, and always run the tests and read the diff.",
    "balanced": "Use it only for low-risk mechanical work (boilerplate, renames, formatting, test "
                "scaffolding); write logic yourself and review every delegated diff.",
    "partner": "Hand it every low-level job, even small ones (with `investigate` for reading), and "
               "use `consult` for ideas; Deputy makes mistakes, so read every diff, run the tests "
               "and check each idea against the code.",
    "savings": "Use it for well-specified coding work; keep design and risky changes yourself and "
               "verify every result (read the changed files, check the diff, run the tests).",
}


class SetupError(RuntimeError):
    pass


def server_command(pypi: bool = False) -> tuple[str, list[str]]:
    if pypi:
        return "uvx", [PYPI_PACKAGE, "serve"]
    return "uvx", ["--from", GIT_SOURCE, "deputy", "serve"]


def provider_name(provider: str) -> str:
    name = PROVIDER_ALIASES.get(provider.lower(), provider.lower())
    if name not in PROVIDERS:
        raise SetupError(f"provider must be one of {', '.join([*PROVIDERS, *PROVIDER_ALIASES])}")
    return name


def agent_rules(mode: str = DEFAULT_MODE, provider: str = DEFAULT_PROVIDER) -> str:
    if mode not in MODES:
        raise SetupError(f"mode must be one of {', '.join(MODES)}")
    return RULES_TEMPLATE.format(delegate_rule=DELEGATE_RULES[mode],
                                 model_name=MODEL_NAME[provider_name(provider)])


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(path.name + ".deputy-backup")
    shutil.copy2(path, backup)
    return backup


def _write_new(path: Path, content: str, force: bool) -> str:
    if path.exists() and not force:
        return f"kept existing {path} (use --force to replace it)"
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup(path)
    path.write_text(content, encoding="utf-8")
    return f"wrote {path}"


# --------------------------------------------------------------------------- Cursor

def cursor_entry(project: bool, pypi: bool = False, mode: str = DEFAULT_MODE,
                 provider: str = DEFAULT_PROVIDER) -> dict:
    command, args = server_command(pypi)
    provider = provider_name(provider)
    key = KEY_VAR[provider]
    env = {key: f"${{env:{key}}}", "DEPUTY_MODE": mode}
    if provider != DEFAULT_PROVIDER:
        env["DEPUTY_PROVIDER"] = provider
    if project:
        # ${workspaceFolder} is the folder that contains .cursor/mcp.json.
        env["DEPUTY_WORKSPACE"] = "${workspaceFolder}"
    return {"type": "stdio", "command": command, "args": args, "env": env}


def setup_cursor(project_dir: Path | None = None, pypi: bool = False, mode: str = DEFAULT_MODE,
                 force: bool = False, dry_run: bool = False,
                 provider: str = DEFAULT_PROVIDER) -> list[str]:
    """Add Deputy to ~/.cursor/mcp.json, or to <project>/.cursor/mcp.json plus a project rule."""
    provider = provider_name(provider)
    agent_rules(mode, provider)  # validates the mode
    base = project_dir.resolve() if project_dir else Path.home()
    config = base / ".cursor" / "mcp.json"
    entry = cursor_entry(project_dir is not None, pypi, mode, provider)
    data: dict = {}
    if config.exists():
        try:
            data = json.loads(config.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise SetupError(f"{config} is not valid JSON ({exc}); fix it first") from None
        if not isinstance(data, dict):
            raise SetupError(f"{config} must contain a JSON object")
    servers = data.setdefault("mcpServers", {})
    notes = []
    if "deputy" in servers and not force:
        notes.append(f"kept the existing deputy entry in {config} (use --force to replace it)")
    else:
        servers["deputy"] = entry
        if dry_run:
            notes.append(f"would write {config}:\n{json.dumps({'mcpServers': {'deputy': entry}}, indent=2)}")
        else:
            config.parent.mkdir(parents=True, exist_ok=True)
            backup = _backup(config)
            config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            notes.append(f"updated {config}" + (f" (backup: {backup.name})" if backup else ""))

    rule = ("---\ndescription: When and how to use the Deputy MCP tools (consult, review, "
            "investigate, delegate, stats)\nalwaysApply: false\n---\n\n" + agent_rules(mode, provider))
    if project_dir:
        target = base / ".cursor" / "rules" / "deputy.mdc"
        notes.append(f"would write {target}" if dry_run else _write_new(target, rule, force))
    else:
        notes.append("Cursor has no global rules file: run `deputy setup cursor --project <dir>` "
                     "to add the Deputy rule to a project, or paste `deputy setup rules` into "
                     "Cursor Settings > Rules.")
    notes.append(f"Make sure {KEY_VAR[provider]} is set in your environment, then restart Cursor.")
    return notes


# ---------------------------------------------------------------------------- Codex

def codex_block(pypi: bool = False, mode: str = DEFAULT_MODE,
                provider: str = DEFAULT_PROVIDER) -> str:
    command, args = server_command(pypi)
    provider = provider_name(provider)
    quoted = ", ".join(json.dumps(a) for a in args)
    forwarded = ", ".join(json.dumps(v) for v in FORWARDED_ENV[provider])
    env = f"DEPUTY_MODE = {json.dumps(mode)}"
    if provider != DEFAULT_PROVIDER:
        env += f", DEPUTY_PROVIDER = {json.dumps(provider)}"
    return (
        "\n[mcp_servers.deputy]\n"
        f"command = {json.dumps(command)}\n"
        f"args = [{quoted}]\n"
        f"env = {{ {env} }}\n"
        f"env_vars = [{forwarded}]\n"
        "# Deputy runs take minutes; Codex's default tool timeout is 60 s.\n"
        "startup_timeout_sec = 120\n"
        "tool_timeout_sec = 1800\n"
    )


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def setup_codex(pypi: bool = False, mode: str = DEFAULT_MODE, force: bool = False,
                dry_run: bool = False, provider: str = DEFAULT_PROVIDER) -> list[str]:
    """Add Deputy to ~/.codex/config.toml and install the playbook as a Codex skill."""
    provider = provider_name(provider)
    rules = agent_rules(mode, provider)
    config = codex_home() / "config.toml"
    text = config.read_text(encoding="utf-8") if config.exists() else ""
    notes = []
    if "[mcp_servers.deputy]" in text:
        notes.append(f"kept the existing [mcp_servers.deputy] in {config}; edit it by hand to change it")
    elif dry_run:
        notes.append(f"would append to {config}:{codex_block(pypi, mode, provider)}")
    else:
        config.parent.mkdir(parents=True, exist_ok=True)
        backup = _backup(config)
        with open(config, "a", encoding="utf-8") as handle:
            handle.write(codex_block(pypi, mode, provider))
        notes.append(f"updated {config}" + (f" (backup: {backup.name})" if backup else ""))

    skill = Path.home() / ".agents" / "skills" / "deputy" / "SKILL.md"
    body = ("---\nname: deputy\ndescription: Use the Deputy MCP tools for second opinions before "
            "decisions (consult), bug reviews of your changes (review) and wide code searches "
            "(investigate). Do not use for trivial edits.\n---\n\n" + rules)
    notes.append(f"would write {skill}" if dry_run else _write_new(skill, body, force))
    notes.append(f"Deputy runs in {mode!r} mode in Codex (change DEPUTY_MODE in config.toml). "
                 f"Make sure {KEY_VAR[provider]} is set in your environment, then restart Codex.")
    return notes


def claude_instructions() -> list[str]:
    return [
        "In a terminal:",
        "  claude plugin marketplace add alimohammadiamirhossein/deputy",
        "  claude plugin install deputy@deputy",
        "Claude Code then asks for your DeepInfra key and stores it in secure storage.",
    ]
