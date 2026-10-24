from uploads import read_upload


def test_reads_files(tmp_path):
    (tmp_path / "cat.png").write_bytes(b"png")
    assert read_upload("cat.png", tmp_path) == b"png"
