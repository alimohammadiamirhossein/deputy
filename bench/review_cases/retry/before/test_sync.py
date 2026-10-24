from sync import push


def test_push_returns_the_response():
    assert push({"id": 1}, lambda record: {"ok": True, "id": record["id"]}) == {"ok": True, "id": 1}
