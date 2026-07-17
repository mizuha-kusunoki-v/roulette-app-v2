import random
import statistics
import uuid
from typing import Dict, List

from fastapi import HTTPException

from draw_config import (
    AUTO_FORCE_MAX_PER_DRAW,
    AUTO_FORCE_MEDIAN_GAP,
)
from .models import DrawMode, ResultTeam, RouletteResult, RouletteState

# ── グローバル状態 ─────────────────────────────────────────────────────────────

state = RouletteState()


def reset_state() -> None:
    global state
    state = RouletteState()


# ── ユーティリティ ─────────────────────────────────────────────────────────────

def sanitize_names(names: List[str], limit: int) -> List[str]:
    unique: List[str] = []
    for name in names:
        trimmed = name.strip()
        if trimmed and trimmed not in unique:
            unique.append(trimmed)
        if len(unique) >= limit:
            break
    return unique


def active_organizers() -> List[str]:
    result = [
        state.organizers[i]
        for i in state.selected_organizer_indices
        if 0 <= i < len(state.organizers)
    ]
    limit = 2 if state.organizer_mode == "double" else 1
    return result[:limit]


def organizer_set() -> set[str]:
    return set(active_organizers())


# ── 抽選ロジック ───────────────────────────────────────────────────────────────

def compute_auto_forced_players(
    manual_forced: List[str],
    excluded_players: List[str] | None = None,
) -> List[str]:
    if not state.enable_auto_force or not state.participants:
        return []

    excluded_set = set(excluded_players or [])
    organizers = organizer_set()
    participant_counts = [
        state.participation_counts.get(p, 0)
        for p in state.participants
        if p not in organizers
    ]
    if not participant_counts:
        return []

    median_count = statistics.median(participant_counts)
    threshold = median_count - AUTO_FORCE_MEDIAN_GAP

    auto_forced = [
        p
        for p in state.participants
        if p not in organizers
        and p not in manual_forced
        and p not in state.last_players
        and p not in excluded_set
        and state.miss_counts.get(p, 0) < state.miss_threshold
        and state.participation_counts.get(p, 0) <= threshold
    ]
    auto_forced.sort(key=lambda p: (state.participation_counts.get(p, 0), p))
    if AUTO_FORCE_MAX_PER_DRAW > 0:
        auto_forced = auto_forced[:AUTO_FORCE_MAX_PER_DRAW]
    return auto_forced


def validate_draw_mode(mode: DrawMode) -> None:
    if state.organizer_mode == "single" and mode not in ("standard_3", "standard_4"):
        raise HTTPException(
            status_code=400,
            detail="single organizer mode supports only standard draws",
        )

    if state.organizer_mode == "double" and mode not in ("hosts_vs_duo", "hosts_split_pairs"):
        raise HTTPException(
            status_code=400,
            detail="double organizer mode supports only 2-player draws",
        )

    if state.organizer_mode == "double" and len(active_organizers()) < 2:
        raise HTTPException(status_code=400, detail="two organizers are required")


def select_players(count: int):
    selection_reasons: Dict[str, str] = {}

    def append_with_reason(candidates: List[str], reason: str, need: int) -> List[str]:
        if need <= 0:
            return []
        picked = candidates[:need]
        for player in picked:
            if player not in selection_reasons:
                selection_reasons[player] = reason
        return picked

    organizers = organizer_set()

    manual_forced = [
        p for p in state.forced_players if p in state.participants and p not in organizers
    ][:4]
    selected = append_with_reason(manual_forced, "manual_check", count)

    available = [
        p
        for p in state.participants
        if p not in organizers
        and p not in state.last_players
        and p not in selected
        and p not in state.excluded_players
    ]

    guaranteed = [p for p in available if state.miss_counts.get(p, 0) >= state.miss_threshold]
    selected += append_with_reason(guaranteed, "miss_3", count - len(selected))

    auto_forced = compute_auto_forced_players(manual_forced, selected)
    selected += append_with_reason(auto_forced, "median_gap", count - len(selected))

    if len(selected) < count:
        pool = [p for p in available if p not in selected]
        random.shuffle(pool)
        selected += append_with_reason(pool, "random", count - len(selected))

    if len(selected) < count and state.last_players:
        prev_pool = [
            p
            for p in state.last_players
            if p not in organizers and p not in selected and p not in state.excluded_players
        ]
        random.shuffle(prev_pool)
        selected += append_with_reason(prev_pool, "exception_prev_round", count - len(selected))

    if len(selected) < count:
        raise HTTPException(status_code=400, detail="not enough eligible participants")

    spin_order = selected.copy()
    random.shuffle(spin_order)
    return selected, spin_order, selection_reasons


def build_result(mode: DrawMode, spin_order: List[str]) -> RouletteResult:
    current_organizers = active_organizers()

    if mode == "standard_3":
        team_a_players = [spin_order[0]]
        if current_organizers:
            team_a_players = [current_organizers[0], spin_order[0]]
        return RouletteResult(
            kind=mode,
            teams=[
                ResultTeam(label="チーム A", players=team_a_players),
                ResultTeam(label="チーム B", players=[spin_order[1], spin_order[2]]),
            ],
        )

    if mode == "standard_4":
        return RouletteResult(
            kind=mode,
            teams=[
                ResultTeam(label="チーム A", players=[spin_order[0], spin_order[1]]),
                ResultTeam(label="チーム B", players=[spin_order[2], spin_order[3]]),
            ],
        )

    if mode == "hosts_vs_duo":
        return RouletteResult(
            kind=mode,
            teams=[
                ResultTeam(label="主催チーム", players=current_organizers[:2]),
                ResultTeam(label="挑戦者チーム", players=spin_order[:2]),
            ],
        )

    return RouletteResult(
        kind=mode,
        teams=[
            ResultTeam(
                label=f"{current_organizers[0]} チーム",
                players=[current_organizers[0], spin_order[0]],
            ),
            ResultTeam(
                label=f"{current_organizers[1]} チーム",
                players=[current_organizers[1], spin_order[1]],
            ),
        ],
    )


def apply_draw_result(
    selected: List[str],
    spin_order: List[str],
    selection_reasons: Dict[str, str],
    result: RouletteResult,
) -> None:
    organizers = organizer_set()
    new_miss: Dict[str, int] = {}
    new_participation_counts: Dict[str, int] = {}

    for player in state.participants:
        if player in organizers:
            new_miss[player] = state.miss_counts.get(player, 0)
            new_participation_counts[player] = state.participation_counts.get(player, 0)
            continue

        new_miss[player] = 0 if player in selected else state.miss_counts.get(player, 0) + 1
        new_participation_counts[player] = (
            state.participation_counts.get(player, 0) + (1 if player in selected else 0)
        )

    state.prev_players = state.last_players
    state.last_players = selected
    state.spin_order = spin_order
    state.miss_counts = new_miss
    state.participation_counts = new_participation_counts
    state.auto_forced_players = compute_auto_forced_players(state.forced_players)
    state.last_selection_reasons = {
        player: selection_reasons[player]
        for player in selected
        if player in selection_reasons
    }
    state.result = result
    state.round_id = str(uuid.uuid4())
    state.phase = "spinning"
