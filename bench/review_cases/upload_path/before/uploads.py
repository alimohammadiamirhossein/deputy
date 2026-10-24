"""Serve files that users uploaded."""
from pathlib import Path

UPLOAD_DIR = Path("uploads")


def read_upload(name, base=UPLOAD_DIR):
    """Return the bytes of the uploaded file `name` (taken from the request URL)."""
    return (Path(base) / name).read_bytes()
