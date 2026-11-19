"""内部の状態からプロトコルの状態 (SessionState) を組み立てる処理のテスト。

状態にはルールから導いた値 (抽選できるか、優先対象か) が入る。これが実際の抽選とずれると、
画面で選べる抽選が失敗したり、選べない抽選が本当はできたりするので、実際の抽選と突き合わせる。
"""

import random

from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from roulette.logic import DOUBLE_MODES, SINGLE_MODES, state
from roulette.models import DrawMode, RouletteState
from roulette.snapshot import build_session_state
from tests.simulation import draw, players, setup_session


def snapshot() -> RouletteState:
    return state.model_copy(deep=True)


def restore(saved: RouletteState) -> None:
    for name in RouletteState.model_fields:
        setattr(state, name, getattr(saved.model_copy(deep=True), name))


def random_setup(rng: random.Random) -> None:
    double = rng.random() < 0.4
    n = rng.randint(0, 9)
    setup_session(n, "hosts_vs_duo" if double else "standard_4", miss_threshold=rng.randint(1, 4))
    if double and rng.random() < 0.3:
        state.selected_organizer_indices = [0]  # 主催を 1 人しか選んでいない
    names = players(n)
    state.excluded_players = rng.sample(names, rng.randint(0, n))
    state.forced_players = rng.sample(names, rng.randint(0, min(n, 5)))
    state.forced_player_teams = {p: rng.choice(["none", "A", "B"]) for p in state.forced_players}


def draw_succeeds(mode: DrawMode) -> bool:
    saved = snapshot()
    try:
        draw(mode)
        return True
    except HTTPException:
        return False
    finally:
        restore(saved)


def test_available_draw_options_match_what_the_draw_api_accepts():
    for seed in range(300):
        random_setup(random.Random(seed))
        session = build_session_state()

        listed = {o.mode for o in session.draw_options}
        assert listed == set(DOUBLE_MODES if state.organizer_mode == "double" else SINGLE_MODES)
        for o in session.draw_options:
            assert draw_succeeds(o.mode) == o.available, (seed, o)
            assert (o.unavailable_reason is None) == o.available
        for mode in set(SINGLE_MODES + DOUBLE_MODES) - listed:
            assert not draw_succeeds(mode), (seed, mode)


def test_no_draw_is_available_while_the_presentation_runs():
    setup_session(10)
    draw("standard_4")
    assert state.phase == "spinning"

    assert all(not o.available for o in build_session_state().draw_options)


def test_due_matches_who_the_miss_guarantee_would_pick():
    setup_session(6, miss_threshold=3, excluded=["P01"])
    state.miss_counts = {"P00": 3, "P01": 5, "P02": 2, "P03": 4, "P04": 0, "P05": 0}
    state.last_players = ["P04", "P05"]

    due = {p.name for p in build_session_state().participants if p.due}

    assert due == {"P00", "P03"}  # P01 は除外中、P02 は規定未満


def test_forced_is_reported_per_participant():
    setup_session(4, forced=["P00", "P01", "P02"], forced_teams={"P00": "none", "P01": "A", "P02": "B"})

    forced = {p.name: p.forced for p in build_session_state().participants}

    assert forced == {"P00": "any", "P01": "A", "P02": "B", "P03": None}


def test_current_round_groups_players_by_selection_reason():
    setup_session(8, forced=["P05"])
    draw("standard_4")

    current = build_session_state().current_round

    assert current.round_id == state.round_id
    by_reason = {g.reason: g.players for g in current.selections}
    assert by_reason["manual_check"] == ["P05"]
    assert sorted(sum(by_reason.values(), [])) == sorted(state.last_players)


def test_previous_round_players_are_from_the_round_before_the_latest():
    setup_session(8)
    before_latest = draw("standard_4")
    draw("standard_4")

    assert build_session_state().previous_round_players == before_latest.selected


def test_session_is_served_over_http():
    setup_session(5)

    session = TestClient(main.app).get("/session").json()

    assert [p["name"] for p in session["participants"]] == players(5)
    assert session["phase"] == "idle" and session["current_round"] is None
