import asyncio
import threading
import time
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from deputy import server
from deputy.agent import run_agent

from conftest import FakeClient, reply, tool_call


def write_note():
    return reply(calls=[tool_call("write_file", {"path": "note.txt", "content": "hi"})])


def test_cancel_before_the_first_turn_sends_nothing(settings):
    cancel = threading.Event()
    cancel.set()
    client = FakeClient([])
    result = run_agent("do it", settings, client, cancel=cancel)
    assert result.status == "cancelled" and client.requests == []


def test_cancel_stops_before_the_next_tool_call(settings, project: Path):
    cancel = threading.Event()

    class CancelOnReply(FakeClient):
        def _create(self, **request):
            cancel.set()  # the user cancels while the model is answering
            return super()._create(**request)

    client = CancelOnReply([write_note()])
    result = run_agent("write a note", settings, client, cancel=cancel)
    assert result.status == "cancelled" and len(client.requests) == 1
    assert not (project / "note.txt").exists()
    assert "ended early (cancelled)" in result.to_text()


def test_progress_reports_each_turn_and_tool(settings):
    steps = []
    client = FakeClient([reply(calls=[tool_call("list_files", {})]), reply("RESULT: done")])
    run_agent("look around", settings, client, progress=lambda turn, tool: steps.append((turn, tool)))
    assert steps == [(1, ""), (1, "list_files"), (2, "")]


class BlockingClient(FakeClient):
    """Holds the first request until `release` is set, like a slow model call."""

    def __init__(self, responses):
        super().__init__(responses)
        self.started, self.release = threading.Event(), threading.Event()

    def _create(self, **request):
        self.started.set()
        self.release.wait(10)
        return super()._create(**request)


@pytest.fixture
def server_env(project: Path, monkeypatch):
    monkeypatch.setenv("DEPUTY_API_KEY", "k")
    monkeypatch.setenv("DEPUTY_WORKSPACE", str(project))
    return project


def test_cancelled_delegate_keeps_the_lock_until_its_thread_stops(server_env: Path, monkeypatch):
    client = BlockingClient([write_note()])
    monkeypatch.setattr(server, "make_client", lambda settings: client)

    async def scenario():
        call = asyncio.create_task(server.delegate("write a note"))
        await asyncio.to_thread(client.started.wait, 5)
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call
        # The run is still inside its model call: a second delegate must not start yet.
        assert server._code_lock.locked()
        with pytest.raises(ToolError, match="already running"):
            await server.delegate("another task")

    asyncio.run(scenario())
    client.release.set()  # the model answers with a write_file call; the run stops before it
    deadline = time.monotonic() + 5
    while server._code_lock.locked() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not server._code_lock.locked()
    assert not (server_env / "note.txt").exists()


def test_review_sends_progress_to_the_client(server_env: Path, monkeypatch):
    monkeypatch.setattr(server, "make_client", lambda settings: FakeClient([reply("VERDICT: approve")]))
    sent = []

    class Ctx:
        async def report_progress(self, progress, total=None, message=None):
            sent.append((progress, message))

    async def scenario():
        await server.review(diff="+x = 1", lenses=["bugs"], ctx=Ctx())
        await asyncio.sleep(0.05)  # progress is scheduled from the worker thread

    asyncio.run(scenario())
    assert sent == [(1, "bugs: turn 1, thinking")]
