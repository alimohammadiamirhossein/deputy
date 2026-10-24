"""Providers: DeepInfra (DeepSeek, the default) and xAI (Grok), with keys bound to their hosts."""
from pathlib import Path

import pytest

from deputy import setup
from deputy.agent import build_request, run_agent, xai_reasoning_effort
from deputy.config import XAI_BASE_URL, ConfigError, load_settings
from deputy.tools import safe_env

from conftest import FakeClient, reply, tool_call


def grok(tmp_path: Path, **env: str):
    return load_settings({"DEPUTY_PROVIDER": "xai", **env}, cwd=tmp_path)


def test_xai_preset_and_grok_alias(tmp_path: Path):
    for name in ("xai", "grok", "XAI"):
        settings = load_settings({"DEPUTY_PROVIDER": name}, cwd=tmp_path)
        assert (settings.provider, settings.base_url, settings.model) == ("xai", XAI_BASE_URL, "grok-4.3")
    assert grok(tmp_path).has_prices and grok(tmp_path, DEPUTY_MODEL="grok-build-0.1").has_prices
    assert load_settings({}, cwd=tmp_path).provider == "deepinfra"
    with pytest.raises(ConfigError, match="DEPUTY_PROVIDER"):
        load_settings({"DEPUTY_PROVIDER": "openai"}, cwd=tmp_path)


def test_keys_only_go_to_their_own_provider(tmp_path: Path):
    # A DeepInfra key is never sent to xAI, and an xAI key never to DeepInfra.
    assert grok(tmp_path, DEEPINFRA_API_KEY="infra").api_key == ""
    assert grok(tmp_path, DEEPINFRA_API_KEY="infra").key_hint == "XAI_API_KEY"
    assert load_settings({"XAI_API_KEY": "x"}, cwd=tmp_path).api_key == ""
    settings = grok(tmp_path, XAI_API_KEY="x", DEEPINFRA_API_KEY="infra")
    assert (settings.api_key, settings.key_source) == ("x", "XAI_API_KEY")
    # DEPUTY_API_KEY is the explicit key for whatever endpoint is configured.
    assert grok(tmp_path, DEPUTY_API_KEY="d", XAI_API_KEY="x").key_source == "DEPUTY_API_KEY"
    # Other endpoints never get a provider key.
    custom = load_settings({"DEPUTY_BASE_URL": "https://llm.example.com/v1",
                            "DEEPINFRA_API_KEY": "infra", "XAI_API_KEY": "x"}, cwd=tmp_path)
    assert custom.api_key == "" and custom.key_hint == "DEPUTY_API_KEY"


def test_xai_request_shape(tmp_path: Path):
    request = build_request(grok(tmp_path), "high", [{"role": "user", "content": "hi"}], [])
    assert request["max_completion_tokens"] == 16_384 and "max_tokens" not in request
    assert request["reasoning_effort"] == "high" and "extra_body" not in request
    assert build_request(grok(tmp_path), "high", [], [], max_tokens=2000)["max_completion_tokens"] == 2000
    deepinfra = build_request(load_settings({}, cwd=tmp_path), "high", [], [])
    assert deepinfra["max_tokens"] == 16_384 and "max_completion_tokens" not in deepinfra


@pytest.mark.parametrize("model, effort, expected", [
    ("grok-4.3", "none", "none"),
    ("grok-4.3", "medium", "medium"),
    ("grok-4.7", "max", "xhigh"),
    ("grok-4.7", "none", "low"),  # reasoning cannot be turned off on grok-4.5 and later
    ("grok-build-0.1", "high", None),
    ("grok-code-fast-1", "high", None),
    ("grok-4.20-0309-non-reasoning", "high", None),
    ("grok-4.20-reasoning", "high", None),
])
def test_xai_reasoning_effort(model: str, effort: str, expected: str | None):
    assert xai_reasoning_effort(model, effort) == expected


def test_grok_runs_keep_one_conversation_id(project: Path):
    settings = load_settings({"DEPUTY_PROVIDER": "xai", "XAI_API_KEY": "x",
                              "DEPUTY_WORKSPACE": str(project)})
    first = FakeClient([reply(calls=[tool_call("list_files", {})]), reply("ANSWER: done")])
    run_agent("look", settings, first, mode="readonly")
    ids = {r["extra_headers"]["x-grok-conv-id"] for r in first.requests}
    assert len(first.requests) == 2 and len(ids) == 1
    second = FakeClient([reply("ANSWER: done")])
    run_agent("look again", settings, second, mode="readonly")
    assert second.requests[0]["extra_headers"]["x-grok-conv-id"] not in ids


def test_deepinfra_runs_send_no_grok_header(settings):
    client = FakeClient([reply("ANSWER: done")])
    run_agent("look", settings, client, mode="readonly")
    assert "extra_headers" not in client.requests[0]


def test_cursor_and_codex_for_grok_forward_only_the_xai_key():
    entry = setup.cursor_entry(project=False, provider="grok")
    assert entry["env"] == {"XAI_API_KEY": "${env:XAI_API_KEY}", "DEPUTY_MODE": "accuracy",
                            "DEPUTY_PROVIDER": "xai"}
    block = setup.codex_block(provider="xai")
    assert 'DEPUTY_PROVIDER = "xai"' in block and '"XAI_API_KEY"' in block
    assert "DEEPINFRA_API_KEY" not in block and "DEPUTY_API_KEY" not in block
    assert "(Grok)" in setup.agent_rules("partner", "xai")
    default = setup.cursor_entry(project=False)
    assert "DEEPINFRA_API_KEY" in default["env"] and "DEPUTY_PROVIDER" not in default["env"]
    with pytest.raises(setup.SetupError, match="provider"):
        setup.agent_rules("accuracy", "openai")


def test_xai_wrong_key_400_reads_as_a_key_error(settings):
    import httpx
    import openai

    from deputy.agent import DeputyError, _complete

    class WrongKey:
        def __init__(self):
            response = httpx.Response(400, request=httpx.Request("POST", "https://api.x.ai/v1"))
            error = openai.BadRequestError(
                "Error code: 400 - {'code': 'invalid-argument', 'error': 'Incorrect API key "
                "provided. You can obtain an API key from https://console.x.ai.'}",
                response=response, body=None)

            def create(**_request):
                raise error
            self.chat = type("Chat", (), {"completions": type("C", (), {"create": staticmethod(create)})})

    with pytest.raises(DeputyError, match="rejected the API key"):
        _complete(WrongKey(), {"model": "grok-4.3"}, deadline=1e12)


def test_shell_commands_never_see_xai_variables():
    env = safe_env({"PATH": "x", "XAI_API_KEY": "1", "XAI_TEAM": "2", "HOME": "h"})
    assert "XAI_API_KEY" not in env and "XAI_TEAM" not in env and env["PATH"] == "x"
