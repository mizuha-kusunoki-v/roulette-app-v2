"""テスト用の窓口。内部の状態 (RouletteState) の形を知っているのは、テストではこのモジュールだけ。

テストごとに新しいセッションを start() で作り、session() で取り出して操作関数に渡す。
HTTP のテストも同じセッションを使うよう、アプリの依存性 (router.current_session) を差し替える。

テストは状態を操作 (logic の操作関数、router の API 関数) で作り、結果は名前で読む。
画面の操作では作れない状態 (ミス回数が 5 回の人など) を作るときだけ、ここの set_* を使う。
内部の持ち方を変えたら、ここだけを直せばほかのテストはそのまま通るはず。
"""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator, List

import main
from roulette import logic, router
from roulette.logic import count_history
from roulette.models import RouletteState
from roulette.protocol import PresentationCompleteRequest

_session = RouletteState()


def start() -> RouletteState:
    """新しいセッションでテストを始める。"""
    global _session
    _session = RouletteState()
    main.app.dependency_overrides[router.current_session] = lambda: _session
    return _session


def stop() -> None:
    main.app.dependency_overrides.pop(router.current_session, None)


def session() -> RouletteState:
    return _session

# ── 読む ─────────────────────────────────────────────────────────────────────


def participants() -> List[str]:
    return list(_session.participants)


def active_organizers() -> List[str]:
    return logic.active_organizers(_session)


def organizer_mode() -> str:
    return _session.organizer_mode


def miss_threshold() -> int:
    return _session.miss_threshold


def phase() -> str:
    return _session.phase


def round_id() -> str | None:
    return _session.round_id


def last_round_players() -> List[str]:
    """最新の回に出た人 (次の抽選で休む人)。"""
    return list(_session.last_players)


def previous_round_players() -> List[str]:
    """最新の回の 1 つ前の回に出た人。"""
    return list(_session.prev_players)


def participation_counts() -> Dict[str, int]:
    return {p: _session.participation_counts.get(p, 0) for p in _session.participants}


def miss_counts() -> Dict[str, int]:
    return {p: _session.miss_counts.get(p, 0) for p in _session.participants}


def pair_counts() -> Dict[str, int]:
    return dict(_session.pair_counts)


def history_round_ids() -> List[str]:
    return [r.round_id for r in _session.history]


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
    r = _session.history[-1]
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
    tally = count_history(_session.history)
    return (
        {p: tally.participation_counts.get(p, 0) for p in _session.participants},
        {p: tally.miss_counts.get(p, 0) for p in _session.participants},
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
    router.presentation_complete(PresentationCompleteRequest(round_id=_session.round_id), _session)


@contextmanager
def rollback() -> Iterator[None]:
    """中で変えた状態を、抜けるときに元に戻す。"""
    saved = _session.model_copy(deep=True)
    try:
        yield
    finally:
        for name in RouletteState.model_fields:
            setattr(_session, name, getattr(saved.model_copy(deep=True), name))


# ── 画面の操作では作れない状態を作る ─────────────────────────────────────────


def set_counts(*, participation: Dict[str, int] | None = None, miss: Dict[str, int] | None = None) -> None:
    """参加回数・ミス回数を直接決める (書いていない人は 0)。"""
    if participation is not None:
        _session.participation_counts = {p: participation.get(p, 0) for p in _session.participants}
    if miss is not None:
        _session.miss_counts = {p: miss.get(p, 0) for p in _session.participants}


def set_last_round_players(names: List[str]) -> None:
    """最新の回に出た人を直接決める。"""
    _session.last_players = list(names)
