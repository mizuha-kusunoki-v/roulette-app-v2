"""フロントとバックエンドの間のプロトコル (サーバーから送る状態のメッセージ)。

内部の状態 (logic.state) はそのまま外に出さず、ここで決めた形にしてから送る。内部の持ち方を変えても、
この形を保てばフロントは壊れない。

抽選のルールから導く値 (抽選できるか、優先対象か、強制の上限) もここで計算して送る。
ルールを持つのはサーバーだけにして、フロントで計算し直さない。
"""

from typing import Dict, List, Literal

from pydantic import BaseModel

from .logic import (
    active_organizers,
    draw_blocker,
    forced_players_limit,
    modes_for_organizer_mode,
    organizer_set,
    state,
)
from .models import DrawMode, DrawRecord, OrganizerMode, RouletteResult

Phase = Literal["idle", "spinning", "result"]
SelectionReason = Literal["manual_check", "miss_3", "median_gap", "random", "exception_prev_round"]
ForcedTeam = Literal["any", "A", "B"]


class Organizer(BaseModel):
    name: str
    active: bool  # 今の主催モードで主催として選ばれている


class ParticipantStatus(BaseModel):
    name: str
    participation_count: int
    miss_count: int
    forced: ForcedTeam | None  # None = 手動強制なし、"any" = チーム指定なし
    excluded: bool
    auto_forced: bool  # 次の抽選で自動強制 (参加回数の中央値差) の対象
    due: bool  # 次の抽選でミス回数の保証の対象


class Settings(BaseModel):
    miss_threshold: int
    enable_auto_force: bool
    forced_limit: int  # 手動強制にできる最大人数


class DrawOption(BaseModel):
    mode: DrawMode
    available: bool
    unavailable_reason: str | None


class CurrentRound(BaseModel):
    round_id: str
    result: RouletteResult
    reasons: Dict[SelectionReason, List[str]]  # 選ばれた理由ごとの参加者


class SessionState(BaseModel):
    phase: Phase
    organizer_mode: OrganizerMode
    organizers: List[Organizer]
    participants: List[ParticipantStatus]
    settings: Settings
    draw_options: List[DrawOption]  # 今の主催モードで使える抽選モードだけを並べる
    current_round: CurrentRound | None
    previous_round_players: List[str]  # 最新の回の 1 つ前の回に出た人 (管理画面の「前回参加者」)
    history: List[DrawRecord]


# ── 組み立て ─────────────────────────────────────────────────────────────────


def _forced_team(name: str) -> ForcedTeam | None:
    if name not in state.forced_players:
        return None
    team = state.forced_player_teams.get(name, "none")
    return team if team in ("A", "B") else "any"


def _is_due(name: str, organizers: set[str]) -> bool:
    """select_players の保証対象 (guaranteed) と同じ条件。"""
    return (
        name not in organizers
        and name not in state.last_players
        and name not in state.excluded_players
        and state.miss_counts.get(name, 0) >= state.miss_threshold
    )


def _draw_option(mode: DrawMode) -> DrawOption:
    reason = "抽選演出中です" if state.phase == "spinning" else draw_blocker(mode)
    return DrawOption(mode=mode, available=reason is None, unavailable_reason=reason)


def _current_round() -> CurrentRound | None:
    if state.round_id is None or state.result is None:
        return None
    reasons: Dict[SelectionReason, List[str]] = {}
    for name, reason in state.last_selection_reasons.items():
        reasons.setdefault(reason, []).append(name)  # type: ignore[arg-type]
    return CurrentRound(round_id=state.round_id, result=state.result, reasons=reasons)


def session_state() -> SessionState:
    organizers = organizer_set()
    active = set(active_organizers())
    return SessionState(
        phase=state.phase,
        organizer_mode=state.organizer_mode,
        organizers=[Organizer(name=n, active=n in active) for n in state.organizers],
        participants=[
            ParticipantStatus(
                name=p,
                participation_count=state.participation_counts.get(p, 0),
                miss_count=state.miss_counts.get(p, 0),
                forced=_forced_team(p),
                excluded=p in state.excluded_players,
                auto_forced=p in state.auto_forced_players,
                due=_is_due(p, organizers),
            )
            for p in state.participants
        ],
        settings=Settings(
            miss_threshold=state.miss_threshold,
            enable_auto_force=state.enable_auto_force,
            forced_limit=forced_players_limit(),
        ),
        draw_options=[_draw_option(m) for m in modes_for_organizer_mode()],
        current_round=_current_round(),
        previous_round_players=list(state.prev_players),
        history=list(state.history),
    )
