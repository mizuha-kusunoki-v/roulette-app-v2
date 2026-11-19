"""同時に届いたリクエストが、互いの書き込みを壊さないこと。

FastAPI は def のエンドポイントをスレッドで並行に動かす。状態の鍵 (main.create_app の state_lock) がないと、
同時に抽選すると履歴に足したはずの回が消えたり、保存している集計が履歴と食い違ったりする。
Python はスレッドを 5ms ごとにしか切り替えず、1 回の抽選はそれより短いので、普段はめったに起きない。
ここでは切り替えの間隔を極端に短くして、ぶつかる機会を作る。
"""

import asyncio
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from main import create_app
from roulette.logic import count_history
from tests import harness
from tests.test_websocket import receive_json

DRAWS = 200


async def draw_all_at_once(app) -> list[int]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.put("/participants", json={"names": [f"P{i:02d}" for i in range(12)]})
        responses = await asyncio.gather(*[client.post("/draw", json={"mode": "standard_4"}) for _ in range(DRAWS)])
    return [r.status_code for r in responses]


def test_simultaneous_draws_are_all_recorded_and_tallied():
    app = create_app()
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        statuses = asyncio.run(draw_all_at_once(app))
    finally:
        sys.setswitchinterval(interval)

    session = app.state.session
    assert statuses == [200] * DRAWS
    assert len(session.history) == DRAWS
    recount = count_history(session.history)
    names = {p.id: p.name for p in session.participants}
    assert session.participation_counts == {names[i]: n for i, n in recount.participation_counts.items()}
    assert session.pair_counts == recount.pair_counts


def test_the_websocket_builds_the_state_only_while_holding_the_state_lock():
    # 書き込みの途中を読まないよう、WebSocket も HTTP と同じ鍵を取ってから状態を組み立てる。
    # 鍵を持ったまま変更を知らせ、放すまで送ってこないことを見る (偶然に頼らずに確かめる)
    app = harness.app()
    lock, changes = app.state.state_lock, app.state.changes
    with TestClient(app).websocket_connect("/ws/session") as ws:
        receive_json(ws)  # つないだ直後の状態
        ws.portal.call(lock.acquire)
        ws.portal.call(changes.notify)

        with pytest.raises(TimeoutError):
            receive_json(ws, seconds=0.3)

        ws.portal.call(lock.release)
        assert receive_json(ws)["revision"]["version"] == changes.version
