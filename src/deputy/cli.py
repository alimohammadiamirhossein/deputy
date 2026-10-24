"""Command line: `deputy serve` runs the MCP server, `deputy doctor` checks your setup."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from .config import (DEFAULT_MODE, DEFAULT_PROVIDER, MODES, PROVIDER_ALIASES, PROVIDERS,
                     ConfigError, load_settings)
from .workspace import WorkspaceError, check_root

DOCTOR_PROMPT = ("A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. "
                 "How much does the ball cost? Reply with just the amount.")


def doctor() -> int:
    """Check the key, endpoint, model and that thinking is really on."""
    from .agent import DeputyError, Usage, _complete, build_request
    from .server import make_client

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"[fail] configuration: {exc}")
        return 1
    print(f"Deputy {__version__}")
    for key, value in settings.describe().items():
        print(f"  {key}: {value}")
    try:
        check_root(settings.workspace)
        print("[ok]   workspace")
    except WorkspaceError as exc:
        print(f"[warn] workspace: {exc} (run Claude Code from a project folder)")
    if not settings.api_key:
        print(f"[fail] no API key. Set {settings.key_hint}, then open a new terminal.")
        return 1

    request = build_request(settings, settings.effort,
                            [{"role": "user", "content": DOCTOR_PROMPT}], [], max_tokens=2000)
    started = time.monotonic()
    try:
        response = _complete(make_client(settings), request, time.monotonic() + 120)
    except DeputyError as exc:
        print(f"[fail] provider: {exc}")
        return 1
    usage = Usage()
    usage.add(response.usage)
    answer = (response.choices[0].message.content or "").strip()
    cost = usage.cost(settings)
    print(f"[ok]   model answered in {time.monotonic() - started:.1f}s: {answer[:60]!r}")
    if settings.effort == "none":
        print("[info] thinking is off (DEPUTY_THINKING=none)")
    elif usage.reasoning > 0:
        print(f"[ok]   thinking is ON ({usage.reasoning} thinking tokens)")
    else:
        print("[warn] the provider reported no thinking tokens; thinking may be off for this model")
    if cost is not None:
        print(f"[ok]   this check cost about ${cost:.6f}")
    return 0


def run_setup(args: argparse.Namespace) -> int:
    from . import setup

    try:
        if args.target == "cursor":
            notes = setup.setup_cursor(args.project, pypi=args.pypi, mode=args.mode,
                                       force=args.force, dry_run=args.dry_run,
                                       provider=args.provider)
        elif args.target == "codex":
            notes = setup.setup_codex(pypi=args.pypi, mode=args.mode, force=args.force,
                                      dry_run=args.dry_run, provider=args.provider)
        elif args.target == "rules":
            notes = [setup.agent_rules(args.mode, args.provider)]
        else:
            notes = setup.claude_instructions()
    except (setup.SetupError, OSError) as exc:
        print(f"[fail] {exc}")
        return 1
    print("\n".join(notes))
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(
        prog="deputy", description="Deputize cheap models. Claude stays the sheriff.")
    parser.add_argument("--version", action="version", version=f"deputy {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (what your editor starts)")
    sub.add_parser("doctor", help="check your key, the model, and that thinking is on")
    sub.add_parser("stats", help="show rough tokens and money saved")
    setup = sub.add_parser("setup", help="add Deputy to Cursor, Codex or Claude Code")
    setup.add_argument("target", choices=["cursor", "codex", "claude", "rules"])
    setup.add_argument("--project", type=Path, help="Cursor: configure this project folder "
                       "(adds .cursor/mcp.json and a rule) instead of ~/.cursor/mcp.json")
    setup.add_argument("--mode", default=DEFAULT_MODE, choices=MODES)
    setup.add_argument("--provider", default=DEFAULT_PROVIDER,
                       choices=[*PROVIDERS, *PROVIDER_ALIASES],
                       help="model provider: deepinfra (DeepSeek, the default) or xai/grok")
    setup.add_argument("--pypi", action="store_true", help="run the PyPI package instead of GitHub")
    setup.add_argument("--force", action="store_true", help="replace an existing Deputy entry")
    setup.add_argument("--dry-run", action="store_true", help="show the changes without writing")
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return doctor()
    if args.command == "stats":
        from . import stats
        from .config import ConfigError, load_settings

        try:
            print(stats.report(load_settings(), []))
        except ConfigError as exc:
            print(f"configuration error: {exc}")
            return 1
        return 0
    if args.command == "setup":
        return run_setup(args)
    from .server import main as serve

    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
