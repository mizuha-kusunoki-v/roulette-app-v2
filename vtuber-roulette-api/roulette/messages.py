"""利用者に見せる文言。

抽選のルール (logic) は理由の種類と数値だけを返し、文言はここで組み立てる。
画面に送る状態 (snapshot) と API のエラー (router) は、どちらもここの文言を使う。
"""

from typing import assert_never

from .models import (
    DrawBlock,
    ModeNotAvailable,
    NotEnoughParticipants,
    OrganizersRequired,
    TeamForcedOverSlots,
    TooManyForced,
)


def describe_draw_block(block: DrawBlock) -> str:
    # 理由の種類を足したら、ここに case を足す (足さないと型チェッカーが assert_never で検出する)
    match block:
        case ModeNotAvailable():
            return "今の主催モードでは実行できない抽選です"
        case OrganizersRequired(required=required):
            return f"主催{required}人モードでは主催を{required}人選択してください"
        case TeamForcedOverSlots(team=team, forced=forced, slots=slots):
            return f"チーム{team}の強制人数（{forced}人）が抽選枠（{slots}人）を超えています"
        case TooManyForced(forced=forced, slots=slots):
            return f"{slots}人抽選では手動強制は{slots}人以内にしてください（現在{forced}人選択中）"
        case NotEnoughParticipants(needed=needed):
            return f"{needed}人抽選には、除外を除いて{needed}人以上の参加者が必要です"
        case _:
            assert_never(block)


def forced_limit_exceeded(limit: int) -> str:
    return f"手動強制は最大{limit}人までです"
