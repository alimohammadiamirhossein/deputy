import json
import os
from pathlib import Path

import pytest

from deputy.tools import ToolContext, call_tool, safe_env, schemas, summarize_changes
from deputy.workspace import Workspace, WorkspaceError, check_root


def ctx_for(root: Path, writes: bool = True) -> ToolContext:
    return ToolContext(workspace=Workspace(root), command_timeout=30, allow_writes=writes)


def call(ctx: ToolContext, name: str, **arguments) -> str:
    return call_tool(ctx, name, json.dumps(arguments))


def test_paths_cannot_escape_the_workspace(project: Path):
    ws = Workspace(project)
    with pytest.raises(WorkspaceError):
        ws.resolve("../outside.txt")
    with pytest.raises(WorkspaceError):
        ws.resolve(str(project.parent / "outside.txt"))
    with pytest.raises(WorkspaceError):
        ws.resolve(".git/config", for_write=True)
    assert ws.resolve("app.py") == Path(os.path.realpath(project / "app.py"))


def test_symlink_escape_is_blocked(project: Path, tmp_path: Path):
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = project / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available here")
    assert call(ctx_for(project), "read_file", path="link.txt").startswith("ERROR")


def test_broad_workspaces_are_refused():
    with pytest.raises(WorkspaceError):
        check_root(Path.home())
    with pytest.raises(WorkspaceError):
        check_root(Path(Path.cwd().anchor))


def test_read_list_search(project: Path):
    ctx = ctx_for(project)
    assert "return a - b" in call(ctx, "read_file", path="app.py")
    assert "app.py" in call(ctx, "list_files", pattern="*.py")
    assert "app.py:2:" in call(ctx, "search", pattern=r"a\s*-\s*b")
    assert call(ctx, "search", pattern="(").startswith("ERROR")


def test_double_star_glob_includes_top_level_files(project: Path):
    ctx = ctx_for(project)
    (project / "pkg").mkdir()
    (project / "pkg" / "deep.py").write_text("x = 1\n", encoding="utf-8")
    listing = call(ctx, "list_files", pattern="**/*.py")
    assert "app.py" in listing and "pkg/deep.py" in listing
    assert "README.md" in call(ctx, "list_files")
    assert "pkg/deep.py:1:" in call(ctx, "search", pattern="x = 1", glob="**/*.py")


def test_edit_requires_unique_exact_match(project: Path):
    ctx = ctx_for(project)
    (project / "dup.txt").write_text("x\nx\n", encoding="utf-8")
    assert "appears 2 times" in call(ctx, "edit_file", path="dup.txt", old_text="x", new_text="y")
    assert "not found" in call(ctx, "edit_file", path="dup.txt", old_text="zzz", new_text="y")
    assert "Edited" in call(ctx, "edit_file", path="dup.txt", old_text="x", new_text="y",
                            replace_all=True)
    assert (project / "dup.txt").read_text(encoding="utf-8") == "y\ny\n"


def test_changes_are_tracked(project: Path):
    ctx = ctx_for(project)
    call(ctx, "edit_file", path="app.py", old_text="a - b", new_text="a + b")
    call(ctx, "write_file", path="pkg/new.py", content="VALUE = 1\n")
    rows = {row["path"]: row for row in summarize_changes(ctx)}
    assert rows["app.py"]["status"] == "modified"
    assert (rows["app.py"]["added"], rows["app.py"]["removed"]) == (1, 1)
    assert rows["pkg/new.py"]["status"] == "created"


def test_read_only_mode_blocks_writes(project: Path):
    ctx = ctx_for(project, writes=False)
    names = {s["function"]["name"] for s in schemas(False)}
    assert names == {"list_files", "read_file", "search"}
    assert "read-only" in call(ctx, "write_file", path="x.txt", content="no")
    assert "read-only" in call(ctx, "run_command", command="echo hi")
    assert not (project / "x.txt").exists()


def test_bad_tool_input_is_reported_not_raised(project: Path):
    ctx = ctx_for(project)
    assert call_tool(ctx, "read_file", "{not json").startswith("ERROR")
    assert call_tool(ctx, "nope", "{}").startswith("ERROR")
    assert call(ctx, "read_file", wrong="x").startswith("ERROR")


def test_run_command_runs_in_workspace_without_secrets(project: Path, monkeypatch):
    monkeypatch.setenv("DEPUTY_TEST_API_KEY", "leak-me")
    ctx = ctx_for(project)
    output = call(ctx, "run_command", command="echo deputy-ok")
    assert "exit code: 0" in output and "deputy-ok" in output
    assert ctx.commands[0]["exit"] == 0
    env = safe_env({"PATH": "x", "MY_API_KEY": "1", "GITHUB_TOKEN": "2", "DEPUTY_X": "3",
                    "GIT_AUTHOR_NAME": "me"})
    assert env == {"PATH": "x", "GIT_AUTHOR_NAME": "me"}


def test_run_command_timeout(project: Path):
    ctx = ToolContext(workspace=Workspace(project), command_timeout=2, allow_writes=True)
    command = "sleep 10" if os.name != "nt" else "Start-Sleep -Seconds 10; sleep 10"
    output = call(ctx, "run_command", command=command)
    assert "timeout" in output


def test_check_root_refuses_the_plugin_folder(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache = tmp_path / ".claude" / "plugins" / "cache" / "deputy" / "deputy" / "0.3.0"
    cache.mkdir(parents=True)
    with pytest.raises(WorkspaceError, match="plugin folder"):
        check_root(cache)
    project = tmp_path / "project"
    project.mkdir()
    assert check_root(project) == project.resolve()
