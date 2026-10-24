import pytest

from uploads import safe_path


def test_absolute_names_are_rejected(tmp_path):
    base = tmp_path / "uploads"
    base.mkdir()
    with pytest.raises(ValueError):
        safe_path(base, str(tmp_path / "secret.txt"))
