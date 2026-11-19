"""フロントの住所 (CORS) のテスト。

開発サーバーは localhost でも 127.0.0.1 でも開ける。どちらで開いても、書き込みの API を呼べなければならない。
"""

from fastapi.testclient import TestClient

from tests import harness


def test_the_frontend_may_be_opened_by_localhost_or_by_the_loopback_address():
    client = TestClient(harness.app())

    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        res = client.options(
            "/draw",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
        )
        assert res.headers.get("access-control-allow-origin") == origin, origin
