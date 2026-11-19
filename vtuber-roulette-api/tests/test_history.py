"""抽選の履歴と集計 (参加回数・ミス回数・対戦カードの回数) のテスト。

集計は履歴を順にたどった結果。抽選のときは 1 回分を足し、履歴を消したときは数え直すが、
どちらも同じ集計にならなければならない。
"""

import random
from dataclasses import dataclass
from typing import List

from roulette import router
from roulette.logic import build_result, delete_history_record, replace_participants
from roulette.models import Selection
from roulette.protocol import PresentationCompleteRequest
from tests import harness
from tests.builders import players
from tests.simulation import draw, setup_session


@dataclass
class RoundView:
    """最新の回まわりの様子。履歴を消したあとに、消す前と同じに戻ったかを比べる。"""

    counts: harness.Counts
    last_round_players: List[str]
    previous_round_players: List[str]
    round_id: str | None
    teams: List[List[str]] | None


def round_view() -> RoundView:
    return RoundView(
        counts=harness.counts(),
        last_round_players=harness.last_round_players(),
        previous_round_players=harness.previous_round_players(),
        round_id=harness.round_id(),
        teams=harness.latest_record().teams if harness.history_round_ids() else None,
    )


def test_counts_after_each_draw_equal_a_recount_of_the_history():
    rng = random.Random(0)
    setup_session(8)
    removed: list[str] = []
    new_names = (f"N{i:02d}" for i in range(100))
    for _ in range(80):
        # 参加者を入れ替えながら抽選を続ける。消した人を同じ名前で入れ直すこともある (別の参加者として扱う)
        if rng.random() < 0.3:
            kept = [p for p in harness.participants() if rng.random() > 0.15]
            removed += [p for p in harness.participants() if p not in kept]
            back = [removed.pop(rng.randrange(len(removed)))] if removed and rng.random() < 0.5 else [next(new_names)]
            if len(kept + back) >= 4:
                replace_participants(harness.session(), kept + back)
        draw("standard_4")

        assert harness.counts() == harness.recount()


def test_deleting_the_latest_round_restores_what_was_before_it():
    setup_session(7)
    for _ in range(5):
        draw("standard_4")
    harness.finish_presentation()
    before = round_view()

    latest = draw("standard_4")
    assert delete_history_record(harness.session(), harness.round_id())

    assert round_view() == before
    assert harness.phase() == "result"
    assert latest.selected != []


def test_deleting_a_middle_round_recounts_from_the_rest():
    setup_session(7)
    for _ in range(6):
        draw("standard_4")
    middle = harness.history_round_ids()[2]

    assert delete_history_record(harness.session(), middle)

    assert middle not in harness.history_round_ids()
    assert harness.counts() == harness.recount()
    assert harness.last_round_players() == harness.latest_record().selected


def test_deleting_every_round_returns_to_idle():
    setup_session(5)
    draw("standard_4")

    assert delete_history_record(harness.session(), harness.round_id())

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

    replace_participants(harness.session(), [p for p in harness.participants() if p not in gone])

    assert not set(gone) & set(harness.last_round_players())
    assert not set(gone) & set(harness.previous_round_players())
    assert set(harness.participation_counts()) == set(harness.participants())
    assert harness.counts() == harness.recount()


def test_phase_follows_the_latest_round():
    setup_session(6)
    assert harness.phase() == "idle"

    draw("standard_4")
    assert harness.phase() == "spinning"

    harness.finish_presentation()
    assert harness.phase() == "result"


def test_a_round_replaced_by_a_new_draw_counts_as_presented():
    # 演出が終わる前に次の抽選をした場合 (API を直接呼ぶなど)。最新の回を消すと、置き換わった回の結果表示に戻る
    setup_session(6)
    draw("standard_4")
    draw("standard_4")

    assert delete_history_record(harness.session(), harness.round_id())

    assert harness.phase() == "result"


def test_presentation_complete_for_another_round_changes_nothing():
    setup_session(6)
    draw("standard_4")
    old = harness.round_id()
    draw("standard_4")

    res = router.presentation_complete(PresentationCompleteRequest(round_id=old), harness.session())

    assert res == {"ok": False, "reason": "round_id_mismatch"}
    assert harness.phase() == "spinning"


def test_a_participant_removed_and_added_again_starts_over():
    # 消したら、その人の記録はリセット。同じ名前で入れ直しても別の参加者として 0 から数える
    setup_session(6)
    for _ in range(4):
        draw("standard_4")
    played = harness.latest_record().selected[0]
    assert harness.participation_counts()[played] > 0

    replace_participants(harness.session(), [p for p in harness.participants() if p != played])
    replace_participants(harness.session(), harness.participants() + [played])

    assert harness.participation_counts()[played] == 0
    assert harness.miss_counts()[played] == 0
    assert played not in harness.last_round_players()  # 前回出たのは、消す前の別の参加者

    # 履歴を消して数え直しても、昔の回は数えない
    assert delete_history_record(harness.session(), harness.round_id())
    assert harness.participation_counts()[played] == 0

