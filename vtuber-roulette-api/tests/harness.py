"""テスト用の窓口。内部の状態 (logic.state) の形を知っているのは、テストではこのモジュールだけ。

テストは状態を操作 (logic の操作関数、router の API 関数) で作り、結果は名前で読む。
画面の操作では作れない状態 (ミス回数が 5 回の人など) を作るときだけ、ここの set_* を使う。
内部の持ち方を変えたら、ここだけを直せばほかのテストはそのまま通るはず。
"""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator, List

from roulette import logic, router
from roulette.logic import count_history, state
from roulette.protocol import PresentationCompleteRequest

# ── 読む ─────────────────────────────────────────────────────────────────────


def participants() -> List[str]:
    return list(state.participants)


def active_organizers() -> List[str]:
    return logic.active_organizers()


def organizer_mode() -> str:
    return state.organizer_mode


def miss_threshold() -> int:
    return state.miss_threshold


def phase() -> str:
    return state.phase


def round_id() -> str | None:
    return state.round_id


def last_round_players() -> List[str]:
    """最新の回に出た人 (次の抽選で休む人)。"""
    return list(state.last_players)


def previous_round_players() -> List[str]:
    """最新の回の 1 つ前の回に出た人。"""
    return list(state.prev_players)


def participation_counts() -> Dict[str, int]:
    return {p: state.participation_counts.get(p, 0) for p in state.participants}


def miss_counts() -> Dict[str, int]:
    return {p: state.miss_counts.get(p, 0) for p in state.participants}


def pair_counts() -> Dict[str, int]:
    return dict(state.pair_counts)


def history_round_ids() -> List[str]:
    return [r.round_id for r in state.history]


@dataclass
class RoundRecord:
    """履歴の 1 回分。名前で表す。"""

    round_id: str
    selected: List[str]  # [チームA..., チームB...] の順
    reasons: Dict[str, str]
    organizers: List[str]
    participants: List[str]
    teams: List[List[str]]  # 結果のチームごとの顔ぶれ (主催を含む)


def latest_record() -> RoundRecord:
    r = state.history[-1]
    return RoundRecord(
        round_id=r.round_id,
        selected=list(r.selected),
        reasons=dict(r.reasons),
        organizers=list(r.organizers),
        participants=list(r.participants),
        teams=[list(t.players) for t in r.result.teams],
    )


def recount() -> tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    """履歴を最初から数え直した集計 (今の参加者の分)。"""
    tally = count_history(state.history)
    return (
        {p: tally.participation_counts.get(p, 0) for p in state.participants},
        {p: tally.miss_counts.get(p, 0) for p in state.participants},
        dict(tally.pair_counts),
    )


@dataclass
class Before:
    """抽選の直前の様子。1 回ごとのルールの確認に使う。"""

    participants: List[str]
    last_round_players: List[str]
    active_organizers: List[str]
    miss_counts: Dict[str, int]
    miss_threshold: int


def before() -> Before:
    return Before(
        participants=participants(),
        last_round_players=last_round_players(),
        active_organizers=active_organizers(),
        miss_counts=miss_counts(),
        miss_threshold=miss_threshold(),
    )


# ── 操作で進める ──────────────────────────────────────────────────────────────


def finish_presentation() -> None:
    """ビュワーの演出が終わったことを知らせる (POST /presentation_complete と同じ)。"""
    router.presentation_complete(PresentationCompleteRequest(round_id=state.round_id))


@contextmanager
def rollback() -> Iterator[None]:
    """中で変えた状態を、抜けるときに元に戻す。"""
    saved = state.model_copy(deep=True)
    try:
        yield
    finally:
        for name in type(state).model_fields:
            setattr(state, name, getattr(saved.model_copy(deep=True), name))


# ── 画面の操作では作れない状態を作る ─────────────────────────────────────────


def set_counts(*, participation: Dict[str, int] | None = None, miss: Dict[str, int] | None = None) -> None:
    """参加回数・ミス回数を直接決める (書いていない人は 0)。"""
    if participation is not None:
        state.participation_counts = {p: participation.get(p, 0) for p in state.participants}
    if miss is not None:
        state.miss_counts = {p: miss.get(p, 0) for p in state.participants}


def set_last_round_players(names: List[str]) -> None:
    """最新の回に出た人を直接決める。"""
    state.last_players = list(names)
