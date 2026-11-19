"""/ws/session のテスト。接続したまま操作して、変わった状態が届くことを確かめる。"""

import json

import anyio
from fastapi.testclient import TestClient

from tests import harness

WAIT_SECONDS = 2.0


def receive_json(ws, seconds: float = WAIT_SECONDS) -> dict:
    """待ち時間に上限を付けて 1 件受け取る。

    TestClient の receive_json には上限がなく、届かない不具合のときにテストが失敗せず止まる。
    Starlette の WebSocketTestSession.receive と同じ部品 (portal と _send_rx、非公開) を使って上限を付ける。
    """

    async def receive():
        with anyio.fail_after(seconds):
            return await ws._send_rx.receive()

    return json.loads(ws.portal.call(receive)["text"])


def names(message: dict) -> list[str]:
    return [p["name"] for p in message["participants"]]


def receive_until(ws, name: str) -> list[str]:
    """name を含む参加者リストが届くまで受け取り、そのリストを返す。"""
    while True:
        current = names(receive_json(ws))
        if name in current:
            return current


def test_changes_are_pushed_to_an_open_connection():
    client = TestClient(harness.app())
    with client.websocket_connect("/ws/session") as ws:
        assert names(receive_json(ws)) == []

        client.put("/participants", json={"names": ["A", "B"]})

        assert names(receive_json(ws)) == ["A", "B"]


def test_an_open_connection_follows_the_session_created_by_reset():
    client = TestClient(harness.app())
    with client.websocket_connect("/ws/session") as ws:
        client.put("/participants", json={"names": ["A", "B"]})
        receive_until(ws, "B")

        # リセットはセッションを作り直して差し替える。開いている接続も新しいセッションを送る
        # (古いセッションを送り続けていると ["A", "B", "C"] が届く)
        client.post("/reset")
        client.post("/participants/add", json={"name": "C"})

        assert receive_until(ws, "C") == ["C"]
