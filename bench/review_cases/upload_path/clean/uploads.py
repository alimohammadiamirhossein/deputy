"""Serve files that users uploaded."""
from pathlib import Path

UPLOAD_DIR = Path("uploads")


def safe_path(base, name):
    """Resolve the request-supplied `name` inside `base`. Raise ValueError if it would point
    outside `base`, for example through "..", an absolute path or a symlink, or at `base` itself."""
    root = Path(base).resolve()
    target = (root / name).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError(f"not a file in the upload folder: {name!r}")
    return target


def read_upload(name, base=UPLOAD_DIR):
    """Return the bytes of the uploaded file `name` (taken from the request URL)."""
    return safe_path(base, name).read_bytes()
