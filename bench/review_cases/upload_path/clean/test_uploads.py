import pytest

from uploads import read_upload, safe_path


@pytest.fixture
def base(tmp_path):
    folder = tmp_path / "uploads"
    folder.mkdir()
    (folder / "cat.png").write_bytes(b"png")
    (tmp_path / "secret.txt").write_text("secret")
    return folder


def test_reads_files_inside_the_folder(base):
    assert read_upload("cat.png", base) == b"png"


@pytest.mark.parametrize("name", ["../secret.txt", "a/../../secret.txt"])
def test_rejects_relative_escapes(base, name):
    with pytest.raises(ValueError):
        safe_path(base, name)


def test_rejects_absolute_paths(base):
    with pytest.raises(ValueError):
        safe_path(base, str(base.parent / "secret.txt"))


def test_rejects_the_folder_itself(base):
    with pytest.raises(ValueError):
        safe_path(base, "")
