"""内部の状態からプロトコルの状態 (SessionState) を組み立てる処理のテスト。

状態にはルールから導いた値 (抽選できるか、優先対象か) が入る。これが実際の抽選とずれると、
画面で選べる抽選が失敗したり、選べない抽選が本当はできたりするので、実際の抽選と突き合わせる。
"""

import random

from fastapi import HTTPException
from fastapi.testclient import TestClient

import draw_config
from roulette import logic
from roulette.logic import DOUBLE_MODES, SINGLE_MODES
from roulette.models import DrawMode
from tests import harness
from tests.builders import SessionBuilder, players
from tests.simulation import draw, setup_session


def random_setup(rng: random.Random) -> None:
    """画面の操作で作れる状態をランダムに作る (手動強制は上限まで)。"""
    double = rng.random() < 0.4
    n = rng.randint(0, 9)
    names = players(n)
    forced = rng.sample(names, rng.randint(0, min(n, 2 if double else 4)))
    setup_session(
        n,
        "hosts_vs_duo" if double else "standard_4",
        miss_threshold=rng.randint(1, 4),
        excluded=rng.sample(names, rng.randint(0, n)),
        forced=forced,
        forced_teams={p: rng.choice(["none", "A", "B"]) for p in forced},
    )
    if double and rng.random() < 0.3:
        logic.configure_organizers(harness.session(), "double", ["Host1", "Host2"], ["Host1"])  # 主催を 1 人しか選んでいない


def draw_succeeds(mode: DrawMode) -> bool:
    with harness.rollback():
        try:
            draw(mode)
            return True
        except HTTPException:
            return False


def test_available_draw_options_match_what_the_draw_api_accepts():
    for seed in range(300):
        random_setup(random.Random(seed))
        session = harness.state()

        listed = {o.mode for o in session.draw_options}
        assert listed == set(DOUBLE_MODES if session.organizer_mode == "double" else SINGLE_MODES)
        for o in session.draw_options:
            assert draw_succeeds(o.mode) == o.available, (seed, o)
            assert (o.unavailable_reason is None) == o.available
        for mode in set(SINGLE_MODES + DOUBLE_MODES) - listed:
            assert not draw_succeeds(mode), (seed, mode)


def test_no_draw_is_available_while_the_presentation_runs():
    setup_session(10)
    draw("standard_4")
    assert harness.phase() == "spinning"

    assert all(not o.available for o in harness.state().draw_options)


def test_state_carries_the_presentation_duration_from_the_config():
    # 演出の長さはバックエンドの設定 (draw_config) だけで決め、状態に載せて画面に渡す
    assert harness.state().presentation_duration_ms == draw_config.PRESENTATION_DURATION_MS


def test_due_matches_who_the_miss_guarantee_would_pick():
    harness.use(
        SessionBuilder()
        .participants(6)
        .settings(miss_threshold=3)
        .excluded("P01")
        .counts(miss={"P00": 3, "P01": 5, "P02": 2, "P03": 4})
        .last_round(["P04", "P05"])
        .build()
    )

    due = {p.name for p in harness.state().participants if p.due}

    assert due == {"P00", "P03"}  # P01 は除外中、P02 は規定未満


def test_forced_is_reported_per_participant():
    setup_session(4, forced=["P00", "P01", "P02"], forced_teams={"P00": "none", "P01": "A", "P02": "B"})

    forced = {p.name: p.forced for p in harness.state().participants}

    assert forced == {"P00": "any", "P01": "A", "P02": "B", "P03": None}


def test_current_round_groups_players_by_selection_reason():
    setup_session(8, forced=["P05"])
    draw("standard_4")

    current = harness.state().current_round

    assert current.round_id == harness.round_id()
    by_reason = {g.reason: g.players for g in current.selections}
    assert by_reason["manual_check"] == ["P05"]
    assert sorted(sum(by_reason.values(), [])) == sorted(harness.last_round_players())


def test_previous_round_players_are_from_the_round_before_the_latest():
    setup_session(8)
    before_latest = draw("standard_4")
    draw("standard_4")

    assert harness.state().previous_round_players == before_latest.selected


def test_session_is_served_over_http():
    setup_session(5)

    session = TestClient(harness.app()).get("/session").json()

    assert [p["name"] for p in session["participants"]] == players(5)
    assert session["phase"] == "idle" and session["current_round"] is None


def test_auto_forced_is_computed_from_the_current_state():
    harness.use(
        SessionBuilder().participants(10).settings(auto_force=True).counts(participation={p: 4 for p in players(10) if p != "P00"}).build()
    )

    assert [p.name for p in harness.state().participants if p.auto_forced] == ["P00"]

    # 保存した値ではなく今の状態から計算するので、設定を変えればすぐ反映される
    logic.set_excluded(harness.session(), "P00", True)
    assert not any(p.auto_forced for p in harness.state().participants)

