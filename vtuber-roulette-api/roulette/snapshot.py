"""内部の状態 (RouletteState) から、プロトコルの SessionState を組み立てる。

ここは変換だけを受け持つ。抽選のルールに関わる判定 (抽選できるか、優先対象か、強制の上限) は
logic の関数を呼び、ここでは計算しない。
"""

from typing import Dict, List

from .logic import (
    auto_forced_players,
    draw_blocker,
    forced_players_limit,
    due_players,
    latest_round,
    modes_for_organizer_mode,
    previous_round_players,
)
from .messages import PRESENTATION_RUNNING, describe_draw_block
from . import models
from .models import DrawMode, RouletteState
from .protocol import (
    CurrentRound,
    DrawRecord,
    DrawOption,
    ForcedTeam,
    Organizer,
    ParticipantStatus,
    ResultTeam,
    RouletteResult,
    SelectionGroup,
    SessionState,
    Settings,
)


def _forced_team(p: models.Participant) -> ForcedTeam | None:
    # 内部ではチーム指定なしを "none" で持つが、プロトコルでは "any" で表す (None は「強制していない」)
    if p.forced is None:
        return None
    return p.forced if p.forced in ("A", "B") else "any"


def _draw_option(session: RouletteState, mode: DrawMode) -> DrawOption:
    if session.phase == "spinning":
        reason: str | None = PRESENTATION_RUNNING
    else:
        block = draw_blocker(session, mode)
        reason = None if block is None else describe_draw_block(block)
    return DrawOption(mode=mode, available=reason is None, unavailable_reason=reason)


def _result(result: models.RouletteResult) -> RouletteResult:
    return RouletteResult(
        kind=result.kind,
        teams=[ResultTeam(label=t.label, players=list(t.players)) for t in result.teams],
    )


def _record(record: models.DrawRecord) -> DrawRecord:
    return DrawRecord(
        round_id=record.round_id,
        drawn_at=record.drawn_at,
        result=_result(record.result),
        selected=list(record.selected),
        organizers=list(record.organizers),
        participants=list(record.participants),
        reasons=dict(record.reasons),
    )


def _current_round(session: RouletteState) -> CurrentRound | None:
    latest = latest_round(session)
    if latest is None:
        return None
    grouped: Dict[str, List[str]] = {}
    for name, reason in latest.reasons.items():
        grouped.setdefault(reason, []).append(name)
    selections = [SelectionGroup(reason=r, players=names) for r, names in grouped.items()]  # type: ignore[arg-type]
    return CurrentRound(round_id=latest.round_id, result=_result(latest.result), selections=selections)


def _organizers(session: RouletteState) -> List[Organizer]:
    return [Organizer(name=o.name, active=o.active) for o in session.organizers]


def _participants(session: RouletteState) -> List[ParticipantStatus]:
    auto_forced = set(auto_forced_players(session))
    due = due_players(session)
    return [
        ParticipantStatus(
            name=p.name,
            participation_count=session.participation_counts.get(p.name, 0),
            miss_count=session.miss_counts.get(p.name, 0),
            forced=_forced_team(p),
            excluded=p.excluded,
            auto_forced=p.name in auto_forced,
            due=p.name in due,
        )
        for p in session.participants
    ]


def _settings(session: RouletteState) -> Settings:
    return Settings(
        miss_threshold=session.miss_threshold,
        enable_auto_force=session.enable_auto_force,
        forced_limit=forced_players_limit(session),
    )


def build_session_state(session: RouletteState) -> SessionState:
    return SessionState(
        phase=session.phase,
        organizer_mode=session.organizer_mode,
        organizers=_organizers(session),
        participants=_participants(session),
        settings=_settings(session),
        draw_options=[_draw_option(session, m) for m in modes_for_organizer_mode(session)],
        current_round=_current_round(session),
        previous_round_players=previous_round_players(session),
        history=[_record(r) for r in session.history],
    )
