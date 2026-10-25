"""The folder Deputy is allowed to touch, and nothing outside it."""
from __future__ import annotations

import os
from pathlib import Path


class WorkspaceError(Exception):
    """A path request that falls outside the workspace or is otherwise refused."""


def _norm(path: Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def is_within(path: Path, root: Path) -> bool:
    child, parent = _norm(path), _norm(root)
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:  # different drives on Windows
        return False


def check_root(root: Path) -> Path:
    """Refuse workspaces that are far too broad to hand to an agent."""
    resolved = Path(os.path.realpath(root))
    if not resolved.is_dir():
        raise WorkspaceError(f"workspace is not a directory: {resolved}")
    if resolved.parent == resolved:
        raise WorkspaceError(f"refusing to use a filesystem root as the workspace: {resolved}")
    if _norm(resolved) == _norm(Path.home()):
        raise WorkspaceError(
            "refusing to use your home folder as the workspace; open Claude Code in a project folder"
        )
    # A plugin server whose project folder was not passed in may start in its install folder.
    if is_within(resolved, Path.home() / ".claude" / "plugins"):
        raise WorkspaceError(f"refusing to use Claude Code's plugin folder as the workspace: {resolved}")
    return resolved


class Workspace:
    def __init__(self, root: Path):
        self.root = check_root(root)

    def resolve(self, path: str, *, for_write: bool = False) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise WorkspaceError("path must be a non-empty string")
        candidate = Path(path.strip())
        if not candidate.is_absolute():
            candidate = self.root / candidate
        # realpath follows symlinks, so a link pointing outside is caught here.
        real = Path(os.path.realpath(candidate))
        if not is_within(real, self.root):
            raise WorkspaceError(f"path is outside the workspace: {path}")
        if for_write:
            parts = Path(os.path.relpath(real, self.root)).parts
            if parts and parts[0].lower() == ".git":
                raise WorkspaceError("writing inside .git is not allowed")
        return real

    def rel(self, path: Path) -> str:
        return Path(os.path.relpath(path, self.root)).as_posix()
