import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from deputy import server
from deputy.agent import REVIEW_HEADER, review
from deputy.diff import DiffError, collect_diff
from deputy.workspace import Workspace

from conftest import FakeClient, reply

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "core.autocrlf=false",
                    *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(project: Path) -> Path:
    git(project, "init", "-q")
    git(project, "add", "-A")
    git(project, "commit", "-qm", "init")
    return project


@needs_git
def test_collect_diff_includes_edits_and_new_files(repo: Path):
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "new_module.py").write_text("VALUE = 42\n", encoding="utf-8")
    text = collect_diff(Workspace(repo))
    assert "-    return a - b" in text and "+    return a + b" in text
    assert ("diff --git a/new_module.py b/new_module.py\nnew file mode 100644\n--- /dev/null\n"
            "+++ b/new_module.py\n@@ -0,0 +1 @@\n+VALUE = 42") in text
    assert "untracked" not in text


@needs_git
def test_collect_diff_scoping_and_errors(repo: Path):
    with pytest.raises(DiffError, match="no uncommitted changes"):
        collect_diff(Workspace(repo))
    (repo / "app.py").write_text("changed\n", encoding="utf-8")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    scoped = collect_diff(Workspace(repo), paths=["README.md"])
    assert "README.md" in scoped and "app.py" not in scoped
    with pytest.raises(DiffError, match="invalid base"):
        collect_diff(Workspace(repo), base="--output=/tmp/x")
    with pytest.raises(DiffError, match="outside the workspace"):
        collect_diff(Workspace(repo), paths=["../elsewhere"])


@needs_git
def test_collect_diff_requires_a_repository(project: Path):
    with pytest.raises(DiffError, match="not a git repository"):
        collect_diff(Workspace(project))


def test_review_runs_default_lenses_read_only(settings):
    clients = []

    def factory():
        client = FakeClient([reply("NO ISSUES FOUND\nChecked: add().")])
        clients.append(client)
        return client

    text, usage, _ = review("diff --git a/app.py b/app.py\n-x\n+y", settings, factory, focus="fix add")
    assert len(clients) == 2 and usage.requests == 2
    assert text.startswith(REVIEW_HEADER.format(model=settings.model))
    assert "Lens: correctness and logic bugs" in text
    first = clients[0].requests[0]
    assert "write_file" not in str(first["tools"]) and "run_command" not in str(first["tools"])
    system = first["messages"][0]["content"]
    assert "break confidence" in system and "VERDICT: approve" in system
    assert "Today's date:" in system and "lead agent wrote" not in system
    assert "fix add" in first["messages"][1]["content"] and "+y" in first["messages"][1]["content"]


def test_consult_my_view_is_echoed_but_not_sent(project: Path, monkeypatch):
    monkeypatch.setenv("DEPUTY_API_KEY", "k")
    monkeypatch.setenv("DEPUTY_WORKSPACE", str(project))
    fake = FakeClient([reply("1. IDEA: x")])
    monkeypatch.setattr(server, "make_client", lambda settings: fake)
    text = asyncio.run(server.consult("Use Redis?", my_view="Yes, Redis with a 5 min TTL"))
    assert text.startswith("YOUR VIEW BEFORE CONSULTING") and "5 min TTL" in text
    assert "5 min TTL" not in str(fake.requests[0]["messages"])


def test_review_tool_with_explicit_diff(project: Path, monkeypatch):
    monkeypatch.setenv("DEPUTY_API_KEY", "k")
    monkeypatch.setenv("DEPUTY_WORKSPACE", str(project))
    monkeypatch.setattr(server, "make_client", lambda settings: FakeClient([reply("NO ISSUES FOUND")]))
    text = asyncio.run(server.review(diff="+print('hi')", lenses=["security"]))
    assert "REVIEW by" in text and "Lens: security" in text and "NO ISSUES FOUND" in text
