"""抽選の履歴と集計 (参加回数・ミス回数・対戦カードの回数) のテスト。

集計は履歴を順にたどった結果。抽選のときは 1 回分を足し、履歴を消したときは数え直すが、
どちらも同じ集計にならなければならない。
"""

import random

from roulette.logic import build_result, delete_history_record, replace_participants
from roulette.models import Selection
from tests import harness
from tests.simulation import draw, players, setup_session


def counts_from_history() -> tuple[dict, dict, dict]:
    return harness.recount()


def counts_in_state() -> tuple[dict, dict, dict]:
    return harness.participation_counts(), harness.miss_counts(), harness.pair_counts()


def latest_round() -> tuple:
    return (
        counts_in_state(),
        harness.last_round_players(),
        harness.previous_round_players(),
        harness.round_id(),
        harness.latest_record().teams if harness.history_round_ids() else None,
    )


def test_counts_after_each_draw_equal_a_recount_of_the_history():
    rng = random.Random(0)
    setup_session(8)
    new_names = (f"N{i:02d}" for i in range(100))
    for _ in range(60):
        # 参加者を入れ替えながら抽選を続ける。消した名前は入れ直さない:
        # 入れ直すと、抽選 (1 回分を足す) では参加回数が 0 から始まり、履歴を消して数え直すと昔の回も数える。
        # この食い違いは既知 (どちらを正とするか未決) なので、ここでは扱わない
        if rng.random() < 0.3:
            names = [p for p in harness.participants() if rng.random() > 0.1] + [next(new_names)]
            if len(names) >= 4:
                replace_participants(names)
        draw("standard_4")

        assert counts_in_state() == counts_from_history()


def test_deleting_the_latest_round_restores_what_was_before_it():
    setup_session(7)
    for _ in range(5):
        draw("standard_4")
    harness.finish_presentation()
    before = latest_round()

    latest = draw("standard_4")
    assert delete_history_record(harness.round_id())

    assert latest_round() == before
    assert harness.phase() == "result"
    assert latest.selected != []


def test_deleting_a_middle_round_recounts_from_the_rest():
    setup_session(7)
    for _ in range(6):
        draw("standard_4")
    middle = harness.history_round_ids()[2]

    assert delete_history_record(middle)

    assert middle not in harness.history_round_ids()
    assert counts_in_state() == counts_from_history()
    assert harness.last_round_players() == harness.latest_record().selected


def test_deleting_every_round_returns_to_idle():
    setup_session(5)
    draw("standard_4")

    assert delete_history_record(harness.round_id())

    assert harness.phase() == "idle"
    assert harness.round_id() is None and harness.last_round_players() == []
    assert set(harness.participation_counts().values()) == {0}


def test_build_result_puts_organizers_from_the_argument():
    selection = Selection(team_a=["P1"], team_b=["P2", "P3"], reasons={})

    with_host = build_result("standard_3", selection, ["Host"])
    without_host = build_result("standard_3", selection, [])
    pairs = build_result("hosts_split_pairs", Selection(team_a=["P1"], team_b=["P2"], reasons={}), ["H1", "H2"])

    assert [t.players for t in with_host.teams] == [["Host", "P1"], ["P2", "P3"]]
    assert [t.players for t in without_host.teams] == [["P1"], ["P2", "P3"]]
    assert [(t.label, t.players) for t in pairs.teams] == [("H1チーム", ["H1", "P1"]), ("H2チーム", ["H2", "P2"])]


def test_draw_records_the_organizers_and_participants_of_that_round():
    setup_session(6, "hosts_vs_duo")

    draw("hosts_vs_duo")

    record = harness.latest_record()
    assert record.organizers == harness.active_organizers() == ["Host1", "Host2"]
    assert record.participants == players(6)
    assert list(record.reasons) == record.selected


def test_removing_a_participant_drops_them_from_the_latest_rounds():
    setup_session(8)
    before_latest = draw("standard_4")
    latest = draw("standard_4")
    gone = [latest.selected[0], before_latest.selected[0]]

    replace_participants([p for p in harness.participants() if p not in gone])

    assert not set(gone) & set(harness.last_round_players())
    assert not set(gone) & set(harness.previous_round_players())
    assert set(harness.participation_counts()) == set(harness.participants())
    assert counts_in_state() == counts_from_history()

