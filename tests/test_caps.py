"""Per-lens caps: review and consult passes stop on time or output tokens, then write up."""
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest

from deputy import agent
from deputy.agent import WRAP_UP_SECONDS, WRAP_UP_TOKENS, review, run_agent
from deputy.config import ConfigError, load_settings

from conftest import FakeClient, reply, tool_call


def capped(project: Path, **env: str):
    return load_settings({"DEPUTY_API_KEY": "k", "DEPUTY_WORKSPACE": str(project), **env})


def list_files(completion: int = 20):
    return reply(calls=[tool_call("list_files", {})], completion=completion)


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> Clock:
    clock = Clock()

    def sleep(seconds: float) -> None:
        clock.now += seconds

    monkeypatch.setattr(agent, "time", SimpleNamespace(monotonic=clock, sleep=sleep))
    return clock


class SlowClient(FakeClient):
    """Every request takes `seconds` on the fake clock; requests listed in `time_out` time out."""

    def __init__(self, responses: list, clock: Clock, seconds: float, time_out: tuple = ()):
        super().__init__(responses)
        self.clock, self.seconds, self.time_out, self.sent = clock, seconds, time_out, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._slow))

    def _slow(self, **request):
        self.sent += 1
        self.clock.now += self.seconds
        if self.sent in self.time_out:
            raise openai.APITimeoutError(request=httpx.Request("POST", "https://example.invalid"))
        return self._create(**request)


def test_lens_caps_have_defaults_and_bounds(project: Path):
    settings = capped(project)
    assert (settings.lens_timeout, settings.lens_max_output) == (300, 32_000)
    assert settings.describe()["per_lens_limit"] == "300s or 32,000 output tokens"
    settings = capped(project, DEPUTY_LENS_TIMEOUT="60", DEPUTY_LENS_MAX_OUTPUT_TOKENS="5000")
    assert (settings.lens_timeout, settings.lens_max_output) == (60, 5_000)
    with pytest.raises(ConfigError):
        capped(project, DEPUTY_LENS_TIMEOUT="5")


def test_output_budget_shrinks_each_request_then_wraps_up(project: Path):
    client = FakeClient([list_files(completion=3_000), list_files(completion=1_900),
                         reply("VERDICT: approve\nNOT CHECKED: none")])
    result = run_agent("review it", capped(project), client, mode="review", output_limit=5_000,
                       wrap_up=True)
    assert [r["max_tokens"] for r in client.requests] == [5_000, 2_000, WRAP_UP_TOKENS]
    assert result.status == "output_limit" and result.usage.requests == 3
    assert result.final_message.startswith("VERDICT: approve")
    last = client.requests[-1]
    assert last["tool_choice"] == "none" and last["reasoning_effort"] == "low"
    prompt = last["messages"][-1]["content"]
    assert "Stop here" in prompt and "thinking budget" in prompt
    # A cut-off reviewer may report only confirmed problems; the rest goes under NOT CHECKED.
    assert "Only CONFIRMED points are findings" in prompt and "NOT CHECKED:" in prompt


def test_xai_budget_uses_max_completion_tokens(project: Path):
    client = FakeClient([list_files(completion=3_000), list_files(completion=1_900),
                         reply("VERDICT: approve\nNOT CHECKED: none")])
    run_agent("review it", capped(project, DEPUTY_PROVIDER="xai"), client, mode="review",
              output_limit=5_000, wrap_up=True)
    assert [r["max_completion_tokens"] for r in client.requests] == [5_000, 2_000, WRAP_UP_TOKENS]
    assert not any("max_tokens" in r for r in client.requests)


def test_consult_wrap_up_keeps_the_plain_prompt(project: Path):
    client = FakeClient([list_files(completion=950), reply("1. IDEA: cache it")])
    run_agent("ideas?", capped(project), client, mode="consult", output_limit=1_000, wrap_up=True)
    prompt = client.requests[-1]["messages"][-1]["content"]
    assert "Stop here" in prompt and "CONFIRMED" not in prompt


def test_response_cut_by_the_budget_counts_as_output_limit(project: Path):
    client = FakeClient([reply("VERDICT: needs-att", finish="length", completion=1_000),
                         reply("VERDICT: needs-attention\n- SEVERITY: major")])
    result = run_agent("review it", capped(project), client, mode="review", output_limit=1_000,
                       wrap_up=True)
    assert result.status == "output_limit"
    assert result.final_message == "VERDICT: needs-attention\n- SEVERITY: major"


def test_time_limit_stops_between_turns_and_wraps_up(project: Path, clock: Clock):
    client = SlowClient([list_files(), list_files(), reply("VERDICT: approve")], clock, seconds=200)
    result = run_agent("review it", capped(project), client, mode="review", time_limit=300,
                       wrap_up=True)
    assert result.status == "time_limit" and result.turns == 3
    assert [r["timeout"] for r in client.requests] == [300, 100, WRAP_UP_SECONDS]
    assert result.final_message == "VERDICT: approve"
    assert "time limit" in client.requests[-1]["messages"][-1]["content"]


def test_request_that_times_out_at_the_deadline_still_wraps_up(project: Path, clock: Clock):
    client = SlowClient([reply("VERDICT: needs-attention")], clock, seconds=301, time_out=(1,))
    result = run_agent("review it", capped(project), client, mode="review", time_limit=300,
                       wrap_up=True)
    assert result.status == "time_limit" and result.turns == 1
    assert result.final_message == "VERDICT: needs-attention"


def test_retry_after_a_rate_limit_keeps_to_the_deadline(project: Path, clock: Clock):
    class RateLimited(SlowClient):
        def _slow(self, **request):
            if self.sent == 0:
                self.sent += 1
                self.clock.now += 250
                raise openai.RateLimitError("slow down", response=httpx.Response(
                    429, request=httpx.Request("POST", "https://example.invalid")), body=None)
            return super()._slow(**request)

    client = RateLimited([reply("VERDICT: approve")], clock, seconds=10)
    run_agent("review it", capped(project), client, mode="review", time_limit=300, wrap_up=True)
    assert client.requests[0]["timeout"] == pytest.approx(48)  # 300 - 250 waited - 2 s backoff


def test_failed_wrap_up_keeps_the_partial_report(project: Path, clock: Clock):
    client = SlowClient([reply("Checked the window logic so far.", calls=[tool_call("list_files", {})])],
                        clock, seconds=301, time_out=(2,))
    result = run_agent("review it", capped(project), client, mode="review", time_limit=300,
                       wrap_up=True)
    assert result.status == "time_limit"
    assert result.final_message == "Checked the window logic so far."


def test_uncapped_runs_are_unchanged(project: Path):
    settings = capped(project)
    client = FakeClient([reply("ANSWER: 42")])
    result = run_agent("question", settings, client, mode="readonly")
    assert result.status == "completed"
    assert "timeout" not in client.requests[0]
    assert client.requests[0]["max_tokens"] == settings.max_output_tokens


def test_review_lens_that_hits_a_cap_is_labelled(project: Path):
    clients = []

    def factory():
        client = FakeClient([list_files(completion=900), reply("VERDICT: approve\nNOT CHECKED: tests")])
        clients.append(client)
        return client

    settings = capped(project, DEPUTY_LENS_MAX_OUTPUT_TOKENS="1000")
    text, usage, _ = review("diff --git a/app.py b/app.py\n-x\n+y", settings, factory,
                            lenses=["only lens"])
    assert "[output_limit |" in text
    assert "NOTE: this lens stopped at its thinking budget" in text
    assert "NOT CHECKED: tests" in text and usage.requests == 2
    assert clients[0].requests[0]["timeout"] == pytest.approx(300, abs=1)
