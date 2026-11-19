import dataclasses
import typing

import pytest

from roulette.logic import (
    DrawBlock,
    ModeNotAvailable,
    NotEnoughParticipants,
    OrganizersRequired,
    TeamForcedOverSlots,
    TooManyForced,
    draw_blocker,
    state,
)
from roulette.messages import describe_draw_block
from tests.simulation import setup_session


def sample(block_type: type) -> DrawBlock:
    """数値の欄には 1、チームの欄には "A" を入れた見本。"""
    values = {f.name: ("A" if f.name == "team" else 1) for f in dataclasses.fields(block_type)}
    return block_type(**values)


@pytest.mark.parametrize("block_type", typing.get_args(DrawBlock))
def test_every_kind_of_draw_block_has_a_message(block_type):
    # 理由の種類を足して messages.py に文言を足し忘れると、ここで失敗する
    assert describe_draw_block(sample(block_type))


@pytest.mark.parametrize(
    "block, message",
    [
        (ModeNotAvailable(), "今の主催モードでは実行できない抽選です"),
        (OrganizersRequired(required=2, active=1), "主催2人モードでは主催を2人選択してください"),
        (TeamForcedOverSlots(team="B", forced=3, slots=2), "チームBの強制人数（3人）が抽選枠（2人）を超えています"),
        (TooManyForced(forced=4, slots=3), "3人抽選では手動強制は3人以内にしてください（現在4人選択中）"),
        (NotEnoughParticipants(needed=4, eligible=2), "4人抽選には、除外を除いて4人以上の参加者が必要です"),
    ],
)
def test_messages_read_as_before(block, message):
    assert describe_draw_block(block) == message


def test_draw_blocker_reports_the_reason_and_numbers_without_wording():
    setup_session(6, "standard_3", forced=["P00", "P01"], forced_teams={"P00": "A", "P01": "A"})

    assert draw_blocker("standard_3") == TeamForcedOverSlots(team="A", forced=2, slots=1)

    state.forced_player_teams = {"P00": "none", "P01": "none"}
    state.excluded_players = ["P02", "P03", "P04", "P05"]
    assert draw_blocker("standard_4") == NotEnoughParticipants(needed=4, eligible=2)
