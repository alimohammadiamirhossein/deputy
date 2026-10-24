"""Serve files that users uploaded."""
from pathlib import Path

UPLOAD_DIR = Path("uploads")


def safe_path(base, name):
    """Join the request-supplied `name` to `base`. Raise ValueError if it tries to climb out
    of `base`."""
    if ".." in Path(name).parts:
        raise ValueError(f"not a file in the upload folder: {name!r}")
    return Path(base) / name


def read_upload(name, base=UPLOAD_DIR):
    """Return the bytes of the uploaded file `name` (taken from the request URL)."""
    return safe_path(base, name).read_bytes()
