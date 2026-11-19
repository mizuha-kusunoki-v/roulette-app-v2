"""内部の状態 (logic.state) から、プロトコルの SessionState を組み立てる。

ここは変換だけを受け持つ。抽選のルールに関わる判定 (抽選できるか、優先対象か、強制の上限) は
logic の関数を呼び、ここでは計算しない。
"""

from typing import Dict, List

from .logic import (
    active_organizers,
    compute_auto_forced_players,
    draw_blocker,
    forced_players_limit,
    is_due,
    modes_for_organizer_mode,
    state,
)
from .messages import PRESENTATION_RUNNING, describe_draw_block
from .models import DrawMode
from .protocol import (
    CurrentRound,
    DrawOption,
    ForcedTeam,
    Organizer,
    ParticipantStatus,
    SelectionGroup,
    SessionState,
    Settings,
)


def _forced_team(name: str) -> ForcedTeam | None:
    # 内部ではチーム指定なしを "none" で持つが、プロトコルでは "any" で表す (None は「強制していない」)
    if name not in state.forced_players:
        return None
    team = state.forced_player_teams.get(name, "none")
    return team if team in ("A", "B") else "any"


def _draw_option(mode: DrawMode) -> DrawOption:
    if state.phase == "spinning":
        reason: str | None = PRESENTATION_RUNNING
    else:
        block = draw_blocker(mode)
        reason = None if block is None else describe_draw_block(block)
    return DrawOption(mode=mode, available=reason is None, unavailable_reason=reason)


def _current_round() -> CurrentRound | None:
    if state.round_id is None or state.result is None:
        return None
    grouped: Dict[str, List[str]] = {}
    for name, reason in state.last_selection_reasons.items():
        grouped.setdefault(reason, []).append(name)
    selections = [SelectionGroup(reason=r, players=names) for r, names in grouped.items()]  # type: ignore[arg-type]
    return CurrentRound(round_id=state.round_id, result=state.result, selections=selections)


def build_session_state() -> SessionState:
    active = set(active_organizers())
    auto_forced = set(compute_auto_forced_players(state.forced_players))
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
                auto_forced=p in auto_forced,
                due=is_due(p),
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
