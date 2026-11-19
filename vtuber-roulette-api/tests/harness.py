"""テスト用の窓口。内部の状態 (RouletteState) の形を知っているのは、テストではこのモジュールだけ。

テストごとに start() で自分のアプリ (main.create_app) を作り、そのセッションを session() で取り出して
操作関数に渡す。HTTP のテストは app() を TestClient に渡せば、同じセッションを使う。

テストは状態を操作 (logic の操作関数、router の API 関数) で作り、結果は名前で読む。
状態を作るのは tests/builders.py の SessionBuilder (画面の操作では作れない値もそこで入れる)。
内部の持ち方を変えたら、ここだけを直せばほかのテストはそのまま通るはず。
"""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator, List

from fastapi import FastAPI

from main import create_app
from roulette import logic, router
from roulette.logic import count_history
from roulette.models import RouletteState
from roulette.protocol import PresentationCompleteRequest

_app: FastAPI = create_app()


def start() -> None:
    """新しいアプリ (と、その新しいセッション) でテストを始める。"""
    global _app
    _app = create_app()


def app() -> FastAPI:
    return _app


def session() -> RouletteState:
    return _app.state.session


def use(session: RouletteState) -> RouletteState:
    """作ったセッション (tests/builders.py) を、このテストのアプリに置く。"""
    _app.state.session = session
    return session

# ── 読む ─────────────────────────────────────────────────────────────────────


def participants() -> List[str]:
    return logic.participant_names(session())


def active_organizers() -> List[str]:
    return logic.active_organizers(session())


def organizer_mode() -> str:
    return session().organizer_mode


def miss_threshold() -> int:
    return session().miss_threshold


def phase() -> str:
    return session().phase


def round_id() -> str | None:
    latest = logic.latest_round(session())
    return latest.round_id if latest else None


def last_round_players() -> List[str]:
    """最新の回に出た人 (次の抽選で休む人)。"""
    return logic.last_round_players(session())


def previous_round_players() -> List[str]:
    """最新の回の 1 つ前の回に出た人。"""
    return logic.previous_round_players(session())


def participation_counts() -> Dict[str, int]:
    return {p: session().participation_counts.get(p, 0) for p in logic.participant_names(session())}


def miss_counts() -> Dict[str, int]:
    return {p: session().miss_counts.get(p, 0) for p in logic.participant_names(session())}


def pair_counts() -> Dict[str, int]:
    return dict(session().pair_counts)


def history_round_ids() -> List[str]:
    return [r.round_id for r in session().history]


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
    r = session().history[-1]
    return RoundRecord(
        round_id=r.round_id,
        selected=list(r.selected),
        reasons=dict(r.reasons),
        organizers=list(r.organizers),
        participants=list(r.participants),
        teams=[list(t.players) for t in r.result.teams],
    )


@dataclass
class Counts:
    """今の参加者の分の集計。"""

    participation: Dict[str, int]
    miss: Dict[str, int]
    pairs: Dict[str, int]


def counts() -> Counts:
    """セッションが持っている集計。"""
    return Counts(participation=participation_counts(), miss=miss_counts(), pairs=pair_counts())


def recount() -> Counts:
    """履歴を最初から数え直した集計。"""
    tally = count_history(session().history)
    names = logic.participant_names(session())
    return Counts(
        participation={p: tally.participation_counts.get(p, 0) for p in names},
        miss={p: tally.miss_counts.get(p, 0) for p in names},
        pairs=dict(tally.pair_counts),
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
    router.presentation_complete(PresentationCompleteRequest(round_id=round_id() or ""), session())


@contextmanager
def rollback() -> Iterator[None]:
    """中で変えた状態を、抜けるときに元に戻す。"""
    saved = session().model_copy(deep=True)
    try:
        yield
    finally:
        for name in RouletteState.model_fields:
            setattr(session(), name, getattr(saved.model_copy(deep=True), name))
