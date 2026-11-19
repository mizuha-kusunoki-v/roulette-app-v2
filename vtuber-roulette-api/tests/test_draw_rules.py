"""1 回ごとの抽選で必ず守られるべきルール。

ランダムな設定で何回も抽選し、毎回の結果をルールと照らし合わせる。
"""

import random

import pytest

from roulette import logic
from tests import harness
from tests.simulation import Scenario, draw, players, setup_session, slots

MODES = ("standard_3", "standard_4", "hosts_vs_duo", "hosts_split_pairs")


def random_scenario(rng: random.Random) -> Scenario:
    mode = rng.choice(MODES)
    n = rng.randint(slots(mode) + 1, 16)
    names = players(n)
    excluded = rng.sample(names, rng.randint(0, max(0, n - slots(mode) - 1)))
    rest = [p for p in names if p not in excluded]
    forced = rng.sample(rest, rng.randint(0, min(2, slots(mode))))
    return Scenario(
        n=n,
        mode=mode,
        auto_force=rng.random() < 0.5,
        miss_threshold=rng.randint(1, 4),
        excluded=excluded,
        forced=forced,
        forced_teams={p: "none" for p in forced},
    )


def start(s: Scenario) -> None:
    setup_session(
        s.n,
        s.mode,
        auto_force=s.auto_force,
        miss_threshold=s.miss_threshold,
        excluded=s.excluded,
        forced=s.forced,
        forced_teams=s.forced_teams,
    )


def scenario_rounds(seeds=range(40), rounds=30):
    """(シナリオ, 各回の結果) を順に返す。"""
    for seed in seeds:
        s = random_scenario(random.Random(seed))
        start(s)
        yield s, [draw(s.mode) for _ in range(rounds)]


def test_each_draw_fills_every_slot_with_distinct_non_organizers():
    for s, history in scenario_rounds():
        for r in history:
            assert len(r.selected) == slots(s.mode), s
            assert len(set(r.selected)) == len(r.selected), s
            assert set(r.selected) <= set(r.before.participants), s
            assert not set(r.selected) & set(r.before.active_organizers), s


def test_excluded_players_are_never_selected():
    for s, history in scenario_rounds():
        for r in history:
            assert not set(r.selected) & set(s.excluded), (s, r.reasons)


def test_excluded_player_is_not_auto_forced_even_when_far_below_median():
    # 参加回数が中央値より大きく少なく (自動強制の条件)、かつ除外されている人
    setup_session(10, auto_force=True, excluded=["P00"])
    harness.set_counts(participation={p: 4 for p in players(10) if p != "P00"}, miss={})

    r = draw("standard_4")

    assert "P00" not in r.selected, r.reasons


def test_manually_forced_players_are_always_selected():
    for s, history in scenario_rounds():
        for r in history:
            assert set(s.forced) <= set(r.selected), (s, r.reasons)


@pytest.mark.parametrize("mode", ["standard_3", "standard_4", "hosts_split_pairs"])
def test_forced_team_is_respected(mode):
    setup_session(10, mode, forced=["P03", "P07"], forced_teams={"P03": "B", "P07": "A"})
    for _ in range(30):
        r = draw(mode)
        assert "P03" in r.team_b
        assert "P07" in r.team_a


def test_players_from_last_round_rest_when_enough_others_are_available():
    for s, history in scenario_rounds():
        for r in history:
            last = set(r.before.last_round_players)
            others = [p for p in r.before.participants if p not in last and p not in s.excluded]
            if len(others) >= slots(s.mode):
                repeated = (set(r.selected) & last) - set(s.forced)
                assert not repeated, (s, r.reasons)


def test_players_who_missed_too_often_are_selected_when_they_fit():
    for s, history in scenario_rounds():
        for r in history:
            b = r.before
            due = [
                p for p in b.participants
                if b.miss_counts[p] >= b.miss_threshold
                and p not in b.last_round_players
                and p not in s.excluded
                and p not in s.forced
            ]
            free = slots(s.mode) - len(s.forced)
            if len(due) <= free:
                assert set(due) <= set(r.selected), (s, due, r.reasons)


def test_a_participant_with_the_same_name_as_an_organizer_is_an_ordinary_participant():
    # 主催と参加者の名前の一致は偶然の一致で、別人として扱う (運用では被らない前提だが、照合はしない)
    setup_session(4, "standard_3", forced=["P00"], forced_teams={"P00": "B"})
    logic.configure_organizers(harness.session(), "single", ["P00"], ["P00"])

    r = draw("standard_3")

    assert r.team_a[0] != "P00"  # 抽選枠のチームAに主催が入るわけではない
    assert "P00" in r.team_b  # 参加者の P00 は強制どおりチームBに入る
    assert harness.participation_counts()["P00"] == 1

