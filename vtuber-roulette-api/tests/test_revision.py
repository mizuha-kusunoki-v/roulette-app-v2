"""状態の新しさの印 (revision) のテスト。

画面は同じ instance_id の中で version が大きい状態だけを採用する。印が付かない、進まない、
サーバーを起動し直しても同じ ID のまま、のどれでも、画面は古い状態を捨てられなくなる。
"""

from fastapi.testclient import TestClient

from main import create_app
from tests import harness
from tests.test_websocket import receive_json


def revision(client: TestClient) -> dict:
    return client.get("/session").json()["revision"]


def test_version_advances_after_each_write_and_not_after_a_read():
    client = TestClient(harness.app())
    first = revision(client)

    assert revision(client) == first  # 読むだけでは進まない
    client.put("/participants", json={"names": ["A", "B"]})
    second = revision(client)
    client.post("/participants/add", json={"name": "C"})
    third = revision(client)

    assert first["instance_id"] == second["instance_id"] == third["instance_id"]
    assert first["version"] < second["version"] < third["version"]


def test_a_restarted_app_has_another_instance_id():
    # version は起動のたびに 0 から数え直す。画面が「古い」と取り違えないよう、ID が変わる
    one = revision(TestClient(create_app()))
    another = revision(TestClient(create_app()))

    assert one["version"] == another["version"] == 0
    assert one["instance_id"] != another["instance_id"]


def test_http_and_websocket_carry_the_same_revision_for_the_same_state():
    client = TestClient(harness.app())
    with client.websocket_connect("/ws/session") as ws:
        assert receive_json(ws)["revision"] == revision(client)

        client.put("/participants", json={"names": ["A", "B"]})

        assert receive_json(ws)["revision"] == revision(client)


def test_every_write_is_pushed_with_a_newer_version_even_when_the_content_is_unchanged():
    # 内容が同じでも送り直す。同じ version のまま内容が違う状態が先に届いても、あとから新しい version で上書きされる
    client = TestClient(harness.app())
    with client.websocket_connect("/ws/session") as ws:
        first = receive_json(ws)["revision"]
        client.post("/participants/remove", json={"name": "nobody"})  # 失敗する書き込み (内容は変わらない)
        second = receive_json(ws)["revision"]

        assert second["version"] > first["version"]
