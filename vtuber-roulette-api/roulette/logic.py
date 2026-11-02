import random
import statistics
import uuid
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import HTTPException

from draw_config import (
    AUTO_FORCE_MAX_PER_DRAW,
    AUTO_FORCE_MEDIAN_GAP,
)
from .models import DrawMode, DrawRecord, ResultTeam, RouletteResult, RouletteState

# ── グローバル状態 ─────────────────────────────────────────────────────────────

state = RouletteState()


def reset_state() -> None:
    # router 側が import 済みの state を参照し続けるため、再代入せず中身を初期化する
    fresh = RouletteState()
    for field in RouletteState.model_fields:
        setattr(state, field, getattr(fresh, field))


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


def get_team_slots(mode: DrawMode) -> tuple[int, int]:
    """抽選で埋めるチームA・チームBのスロット数を返す。"""
    if mode == "standard_3":
        return 1, 2
    if mode == "standard_4":
        return 2, 2
    if mode == "hosts_vs_duo":
        return 0, 2
    # hosts_split_pairs
    return 1, 1


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


def select_players(mode: DrawMode):
    """
    チームA・チームBのスロットを埋めて返す。
    戻り値: (selected_ordered, spin_order, selection_reasons)
    selected_ordered は [チームA選手..., チームB選手...] の順。
    """
    selection_reasons: Dict[str, str] = {}
    team_a_slots, team_b_slots = get_team_slots(mode)

    organizers = organizer_set()

    # 有効な手動強制プレイヤー一覧
    all_manual_forced = [
        p for p in state.forced_players
        if p in state.participants and p not in organizers
    ]

    # チーム指定別に分離
    team_a_forced = [
        p for p in all_manual_forced
        if state.forced_player_teams.get(p) == "A"
    ][:team_a_slots]

    team_b_forced = [
        p for p in all_manual_forced
        if state.forced_player_teams.get(p) == "B"
    ][:team_b_slots]

    assigned_set = set(team_a_forced + team_b_forced)

    no_team_forced = [
        p for p in all_manual_forced
        if state.forced_player_teams.get(p, "none") == "none"
        and p not in assigned_set
    ]

    team_a: List[str] = list(team_a_forced)
    team_b: List[str] = list(team_b_forced)
    selected_set: set[str] = set(team_a + team_b)

    for p in team_a + team_b:
        selection_reasons[p] = "manual_check"

    # チーム指定なし強制プレイヤーを空きスロットに割り当て
    for p in no_team_forced:
        if len(team_a) < team_a_slots:
            team_a.append(p)
        elif len(team_b) < team_b_slots:
            team_b.append(p)
        else:
            break
        selected_set.add(p)
        selection_reasons[p] = "manual_check"

    def fill_slots(candidates: List[str], reason: str) -> None:
        for p in candidates:
            if p in selected_set:
                continue
            if len(team_a) < team_a_slots:
                team_a.append(p)
                selected_set.add(p)
                selection_reasons[p] = reason
            elif len(team_b) < team_b_slots:
                team_b.append(p)
                selected_set.add(p)
                selection_reasons[p] = reason
            if len(team_a) >= team_a_slots and len(team_b) >= team_b_slots:
                break

    # 前回不参加プールを除いた候補
    non_prev_pool = [
        p for p in state.participants
        if p not in organizers
        and p not in state.last_players
        and p not in selected_set
        and p not in state.excluded_players
    ]

    guaranteed = [p for p in non_prev_pool if state.miss_counts.get(p, 0) >= state.miss_threshold]
    fill_slots(guaranteed, "miss_3")

    auto_forced = compute_auto_forced_players(all_manual_forced, list(selected_set))
    fill_slots(auto_forced, "median_gap")

    pool = [p for p in non_prev_pool if p not in selected_set]
    random.shuffle(pool)
    fill_slots(pool, "random")

    if len(team_a) < team_a_slots or len(team_b) < team_b_slots:
        prev_pool = [
            p for p in state.last_players
            if p not in organizers
            and p not in selected_set
            and p not in state.excluded_players
        ]
        random.shuffle(prev_pool)
        fill_slots(prev_pool, "exception_prev_round")

    if len(team_a) < team_a_slots or len(team_b) < team_b_slots:
        raise HTTPException(status_code=400, detail="not enough eligible participants")

    selected_ordered = team_a + team_b
    spin_order = selected_ordered.copy()
    random.shuffle(spin_order)
    return selected_ordered, spin_order, selection_reasons


def build_result(mode: DrawMode, selected: List[str]) -> RouletteResult:
    """selected は [チームA選手..., チームB選手...] の順で受け取る。"""
    current_organizers = active_organizers()

    if mode == "standard_3":
        team_a_players = [selected[0]]
        if current_organizers:
            team_a_players = [current_organizers[0], selected[0]]
        return RouletteResult(
            kind=mode,
            teams=[
                ResultTeam(label="チームA", players=team_a_players),
                ResultTeam(label="チームB", players=[selected[1], selected[2]]),
            ],
        )

    if mode == "standard_4":
        return RouletteResult(
            kind=mode,
            teams=[
                ResultTeam(label="チームA", players=[selected[0], selected[1]]),
                ResultTeam(label="チームB", players=[selected[2], selected[3]]),
            ],
        )

    if mode == "hosts_vs_duo":
        return RouletteResult(
            kind=mode,
            teams=[
                ResultTeam(label="主催チーム", players=current_organizers[:2]),
                ResultTeam(label="挑戦者チーム", players=selected[:2]),
            ],
        )

    # hosts_split_pairs
    return RouletteResult(
        kind=mode,
        teams=[
            ResultTeam(
                label=f"{current_organizers[0]}チーム",
                players=[current_organizers[0], selected[0]],
            ),
            ResultTeam(
                label=f"{current_organizers[1]}チーム",
                players=[current_organizers[1], selected[1]],
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
    key = compute_matchup_key(result, organizer_set())
    state.pair_counts[key] = state.pair_counts.get(key, 0) + 1
    state.result = result
    state.round_id = str(uuid.uuid4())
    state.phase = "spinning"
    state.history.append(
        DrawRecord(
            round_id=state.round_id,
            drawn_at=datetime.now(timezone.utc).isoformat(),
            result=result,
            selected=list(selected),
            organizers=active_organizers(),
            participants=list(state.participants),
            reasons=dict(state.last_selection_reasons),
        )
    )


def compute_matchup_key(result: RouletteResult, organizers: set[str] | None = None) -> str:
    """参加者のみでチーム構成キーを生成する（主催は除外）。チーム順・選手順不問。"""
    orgs = organizers or set()
    team_keys = sorted(
        "|".join(sorted(p for p in team.players if p not in orgs))
        for team in result.teams
    )
    return "||".join(team_keys)


def delete_history_record(round_id: str) -> bool:
    """履歴から1件削除し、残りの履歴から集計値を再計算する。"""
    remaining = [r for r in state.history if r.round_id != round_id]
    if len(remaining) == len(state.history):
        return False
    state.history = remaining

    current = set(state.participants)
    miss = {p: 0 for p in state.participants}
    counts = {p: 0 for p in state.participants}
    for rec in remaining:
        skip = set(rec.organizers)
        picked = set(rec.selected)
        for p in rec.participants:
            if p not in current or p in skip:
                continue
            if p in picked:
                miss[p] = 0
                counts[p] += 1
            else:
                miss[p] += 1
    state.miss_counts = miss
    state.participation_counts = counts

    new_pair_counts: Dict[str, int] = {}
    for rec in remaining:
        k = compute_matchup_key(rec.result, set(rec.organizers))
        new_pair_counts[k] = new_pair_counts.get(k, 0) + 1
    state.pair_counts = new_pair_counts

    def alive(names: List[str]) -> List[str]:
        return [p for p in names if p in current]

    state.last_players = alive(remaining[-1].selected) if remaining else []
    state.prev_players = alive(remaining[-2].selected) if len(remaining) > 1 else []
    state.last_selection_reasons = dict(remaining[-1].reasons) if remaining else {}
    state.spin_order = []
    state.result = remaining[-1].result if remaining else None
    state.round_id = remaining[-1].round_id if remaining else None
    state.phase = "result" if remaining else "idle"
    state.auto_forced_players = compute_auto_forced_players(state.forced_players)
    return True
