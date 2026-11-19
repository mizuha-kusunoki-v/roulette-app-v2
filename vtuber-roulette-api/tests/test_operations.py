"""画面から送る操作 (書き込み API) のテスト。HTTP 経由で操作し、結果は /session で確かめる。"""

import pytest
from fastapi.testclient import TestClient

from tests import harness


@pytest.fixture
def client():
    return TestClient(harness.app())


def session(client):
    return client.get("/session").json()


def statuses(client):
    return {p["name"]: p for p in session(client)["participants"]}


def test_add_and_remove_participants(client):
    assert client.post("/participants/add", json={"name": " 山田 "}).status_code == 200
    assert client.post("/participants/add", json={"name": "佐藤"}).status_code == 200
    assert list(statuses(client)) == ["山田", "佐藤"]

    assert client.post("/participants/add", json={"name": "山田"}).status_code == 409
    assert client.post("/participants/add", json={"name": "  "}).status_code == 400

    assert client.post("/participants/remove", json={"name": "山田"}).status_code == 200
    assert list(statuses(client)) == ["佐藤"]
    assert client.post("/participants/remove", json={"name": "山田"}).status_code == 404


def test_names_with_a_slash_can_be_operated(client):
    client.put("/participants", json={"names": ["A/B", "C"]})

    assert client.post("/participants/excluded", json={"name": "A/B", "excluded": True}).status_code == 200
    assert statuses(client)["A/B"]["excluded"] is True


def test_replacing_participants_drops_records_of_removed_ones(client):
    client.put("/participants", json={"names": ["A", "B", "C"]})
    client.post("/participants/forced", json={"name": "A", "forced": "A"})
    client.post("/participants/excluded", json={"name": "B", "excluded": True})

    client.put("/participants", json={"names": ["C", "D"]})

    s = statuses(client)
    assert list(s) == ["C", "D"]
    assert all(p["forced"] is None and not p["excluded"] for p in s.values())


def test_forced_can_be_set_changed_and_cleared(client):
    client.put("/participants", json={"names": ["A", "B"]})

    client.post("/participants/forced", json={"name": "A", "forced": "any"})
    assert statuses(client)["A"]["forced"] == "any"
    client.post("/participants/forced", json={"name": "A", "forced": "B"})
    assert statuses(client)["A"]["forced"] == "B"
    client.post("/participants/forced", json={"name": "A", "forced": None})
    assert statuses(client)["A"]["forced"] is None


def test_forced_cannot_exceed_the_limit(client):
    client.put("/participants", json={"names": ["A", "B", "C", "D", "E"]})
    for name in "ABCD":
        assert client.post("/participants/forced", json={"name": name, "forced": "any"}).status_code == 200

    res = client.post("/participants/forced", json={"name": "E", "forced": "any"})

    assert res.status_code == 400
    assert statuses(client)["E"]["forced"] is None
    # すでに強制している人のチームを変えるのは上限に関係ない
    assert client.post("/participants/forced", json={"name": "A", "forced": "A"}).status_code == 200


def test_operations_on_unknown_participants_are_rejected(client):
    assert client.post("/participants/forced", json={"name": "X", "forced": "any"}).status_code == 404
    assert client.post("/participants/excluded", json={"name": "X", "excluded": True}).status_code == 404


def test_organizers_are_saved_with_active_flags(client):
    res = client.put(
        "/organizers",
        json={
            "organizer_mode": "double",
            "organizers": [
                {"name": "H1", "active": False},
                {"name": "H2", "active": True},
                {"name": "H3", "active": True},
            ],
        },
    )

    assert res.status_code == 200
    s = session(client)
    assert s["organizer_mode"] == "double"
    assert s["organizers"] == [
        {"name": "H1", "active": False},
        {"name": "H2", "active": True},
        {"name": "H3", "active": True},
    ]


def test_single_mode_keeps_only_one_active_organizer(client):
    client.put(
        "/organizers",
        json={"organizer_mode": "single", "organizers": [{"name": "H1", "active": True}, {"name": "H2", "active": True}]},
    )

    assert [o["active"] for o in session(client)["organizers"]] == [True, False]


def test_settings_are_saved_and_validated(client):
    assert client.put("/settings", json={"miss_threshold": 5, "enable_auto_force": True}).status_code == 200
    assert session(client)["settings"]["miss_threshold"] == 5
    assert session(client)["settings"]["enable_auto_force"] is True

    assert client.put("/settings", json={"miss_threshold": 0, "enable_auto_force": True}).status_code == 400


def test_reset_returns_to_the_initial_state(client):
    client.put("/participants", json={"names": ["A", "B", "C", "D"]})
    client.put("/settings", json={"miss_threshold": 5, "enable_auto_force": True})
    client.post("/draw", json={"mode": "standard_4"})

    assert client.post("/reset").status_code == 200

    s = session(client)
    assert s["participants"] == [] and s["history"] == [] and s["phase"] == "idle"
    assert s["settings"]["miss_threshold"] == 3

