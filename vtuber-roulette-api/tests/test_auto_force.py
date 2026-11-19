"""自動強制 (参加回数の中央値差) のルール本体のテスト。state を使わずに引数だけで確かめる。"""

from roulette.logic import auto_forced_players, compute_auto_forced_players, state
from tests.simulation import setup_session


def pick(counts, candidates=None, gap=2, limit=0):
    return compute_auto_forced_players(
        counts, list(counts) if candidates is None else candidates, median_gap=gap, max_per_draw=limit
    )


def test_players_at_or_below_median_minus_gap_are_picked():
    # 中央値 4、しきい値 2
    counts = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 4}

    assert pick(counts) == ["A", "B"]


def test_median_is_taken_over_everyone_but_only_candidates_are_picked():
    counts = {"A": 0, "B": 0, "C": 5, "D": 5, "E": 5}

    assert pick(counts, candidates=["B", "C"]) == ["B"]


def test_fewest_first_then_by_name_and_limited():
    counts = {"Z": 0, "A": 0, "M": 1, "X": 9, "Y": 9, "W": 9, "V": 9}

    assert pick(counts) == ["A", "Z", "M"]
    assert pick(counts, limit=2) == ["A", "Z"]


def test_nobody_is_picked_without_participants():
    assert pick({}) == []


def test_state_wrapper_skips_forced_resting_excluded_and_due_players():
    setup_session(10, auto_force=True, miss_threshold=3, excluded=["P02"], forced=["P03"])
    state.participation_counts = {p: (0 if p in ("P00", "P01", "P02", "P03", "P04") else 9) for p in state.participants}
    state.last_players = ["P00"]
    state.miss_counts = {p: (5 if p == "P01" else 0) for p in state.participants}

    # P00 は前回出た、P01 はミス回数の保証の対象、P02 は除外中、P03 は手動強制
    assert auto_forced_players() == ["P04"]
    assert auto_forced_players(already_selected=["P04"]) == []
