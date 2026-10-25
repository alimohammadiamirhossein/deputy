import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp.exceptions import ToolError

from deputy import __version__, server

from conftest import FakeClient, reply


def test_initialize_reports_deputy_version(tmp_path: Path):
    async def initialize():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "deputy", "serve"],
            env={"DEPUTY_DATA_DIR": str(tmp_path / "server-data"),
                 "DEPUTY_MODE": "accuracy"},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.initialize()
                assert result.serverInfo.name == "deputy"
                assert result.serverInfo.version == __version__

    asyncio.run(asyncio.wait_for(initialize(), timeout=30))


def test_tools_are_registered():
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == {"delegate", "investigate", "consult", "review", "status",
                                       "stats"}
    for tool in tools:  # the injected MCP context must never leak into the tool schema
        assert "ctx" not in tool.inputSchema.get("properties", {})
    assert "UNVERIFIED" in next(t for t in tools if t.name == "consult").description
    assert "UNVERIFIED" in next(t for t in tools if t.name == "review").description


def test_instructions_follow_the_mode():
    accuracy = server.build_instructions("accuracy")
    assert "Do NOT use `delegate` unless the user explicitly asks" in accuracy
    assert "Call `review` only before you finish a risky or large change" in accuracy
    for mode in server.POLICIES:  # reviews are for risky changes in every mode
        assert "risky or large" in server.build_instructions(mode)
    assert "low-risk mechanical work" in server.build_instructions("balanced")
    assert "`delegate` well-specified coding work" in server.build_instructions("savings")
    lean = server.build_instructions("lean")
    assert "MODE: LEAN" in lean and "big enough to pay off" in lean and "Write changes of a few lines yourself" in lean
    partner = server.build_instructions("partner")
    assert "MODE: PARTNER" in partner and "the user's instruction" in partner
    assert "Before you read or edit files" in partner and "small tasks too" in partner
    assert "call `consult`" in partner and "Deputy makes mistakes" in partner
    assert server.build_instructions("nonsense") == accuracy


def test_every_mode_is_offered_everywhere():
    """The plugin option list, the registry entry and the setup rules all match config.MODES."""
    import json

    from deputy.config import MODES, read_mode
    from deputy.setup import DELEGATE_RULES

    root = Path(__file__).resolve().parents[1]
    plugin = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert plugin["userConfig"]["mode"]["options"] == list(MODES)
    registry = json.loads((root / "server.json").read_text(encoding="utf-8"))
    mode_env = next(v for v in registry["packages"][0]["environmentVariables"]
                    if v["name"] == "DEPUTY_MODE")
    assert mode_env["choices"] == list(MODES)
    assert set(DELEGATE_RULES) == set(MODES) and set(server.POLICIES) == set(MODES)
    assert MODES[:2] == ("accuracy", "lean")  # lean sits right after the default
    for mode in MODES:
        assert read_mode({"DEPUTY_MODE": mode.upper()}) == mode


def test_missing_key_gives_a_helpful_error(project: Path, monkeypatch):
    for name in ("DEPUTY_API_KEY", "DEEPINFRA_API_KEY", "DEEPINFRA_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEPUTY_WORKSPACE", str(project))
    with pytest.raises(ToolError, match="DEEPINFRA_API_KEY"):
        asyncio.run(server.delegate("do something"))


def test_status_shows_config_without_the_key(project: Path, monkeypatch):
    monkeypatch.setenv("DEPUTY_API_KEY", "very-secret-key")
    monkeypatch.setenv("DEPUTY_WORKSPACE", str(project))
    text = asyncio.run(server.status())
    assert "DeepSeek-V4.1-Flash-1017" in text and "thinking: high" in text
    assert "mode: accuracy" in text and "MODE: ACCURACY" in text
    assert "very-secret-key" not in text


def test_delegate_end_to_end_with_fake_provider(project: Path, monkeypatch):
    monkeypatch.setenv("DEPUTY_API_KEY", "k")
    monkeypatch.setenv("DEPUTY_WORKSPACE", str(project))
    fake = FakeClient([reply("RESULT: done")])
    monkeypatch.setattr(server, "make_client", lambda settings: fake)
    text = asyncio.run(server.delegate("say done", thinking="max"))
    assert "RESULT: done" in text and "thinking max" in text
    assert fake.requests[0]["reasoning_effort"] == "max"
    assert "Savings (rough)" in text and "Claude Opus 5.5" in text
    assert "| This session | 1 |" in server.stats_report()


def test_project_dir_picks_the_workspace_unless_pinned(project: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEPUTY_API_KEY", "k")
    monkeypatch.delenv("DEPUTY_WORKSPACE", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    fake = FakeClient([reply("ANSWER: ok")])
    monkeypatch.setattr(server, "make_client", lambda settings: fake)
    asyncio.run(server.investigate("what is here?", project_dir=str(project)))
    assert str(project) in fake.requests[0]["messages"][0]["content"]
    assert f"workspace: {project}" in asyncio.run(server.status(project_dir=str(project)))
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("DEPUTY_WORKSPACE", str(other))  # an explicit pin wins
    assert f"workspace: {other}" in asyncio.run(server.status(project_dir=str(project)))


def test_file_uris_become_paths():
    import os

    if os.name == "nt":
        assert server._uri_to_path("file:///C:/Users/me/app") == Path("C:/Users/me/app")
    else:
        assert server._uri_to_path("file:///home/me/my%20app") == Path("/home/me/my app")
    assert server._uri_to_path("https://example.com") is None


def test_plugin_does_not_pin_the_workspace():
    env = json.loads((Path(__file__).parents[1] / ".claude-plugin" / "plugin.json")
                     .read_text(encoding="utf-8"))["mcpServers"]["deputy"]["env"]
    # Pinning (DEPUTY_WORKSPACE) would make Deputy ignore project_dir and the client's roots.
    assert "DEPUTY_WORKSPACE" not in env
    assert env["CLAUDE_PROJECT_DIR"] == "${CLAUDE_PROJECT_DIR}"


def test_project_dir_overrides_claude_project_dir(tmp_path: Path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.delenv("DEPUTY_WORKSPACE", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(first))
    assert f"workspace: {first.resolve()}" in asyncio.run(server.status())
    assert f"workspace: {second.resolve()}" in asyncio.run(server.status(project_dir=str(second)))
