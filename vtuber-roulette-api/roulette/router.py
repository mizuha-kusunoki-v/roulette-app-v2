import asyncio
import random

from fastapi import APIRouter, HTTPException, WebSocket

from .logic import (
    active_organizers,
    apply_draw_result,
    build_result,
    compute_auto_forced_players,
    compute_matchup_key,
    delete_history_record,
    get_team_slots,
    organizer_set,
    reset_state,
    sanitize_names,
    select_players,
    state,
    validate_draw_mode,
)

_PAIR_RETRY_MAX = 10
from .models import (
    DrawRequest,
    DrawSettingsRequest,
    ExcludedPlayersRequest,
    ForcedPlayersRequest,
    OrganizerConfigRequest,
    ParticipantsRequest,
    PresentationCompleteRequest,
)

router = APIRouter()


@router.get("/state")
def get_state():
    return state


def forced_players_limit() -> int:
    return 2 if state.organizer_mode == "double" else 4


def _clean_forced_player_teams() -> None:
    """forced_players に含まれないプレイヤーの team 情報を削除する。"""
    state.forced_player_teams = {
        p: state.forced_player_teams.get(p, "none")
        for p in state.forced_players
    }


@router.post("/participants")
def set_participants(req: ParticipantsRequest):
    state.participants = sanitize_names(req.participants, limit=1000)
    organizers = organizer_set()

    state.forced_players = [
        p for p in state.forced_players if p in state.participants and p not in organizers
    ][:forced_players_limit()]
    _clean_forced_player_teams()
    state.excluded_players = [
        p for p in state.excluded_players if p in state.participants and p not in organizers
    ]
    state.last_players = [
        p for p in state.last_players if p in state.participants and p not in organizers
    ]
    state.prev_players = [
        p for p in state.prev_players if p in state.participants and p not in organizers
    ]
    state.spin_order = [
        p for p in state.spin_order if p in state.participants and p not in organizers
    ]
    state.miss_counts = {p: state.miss_counts.get(p, 0) for p in state.participants}
    state.participation_counts = {
        p: state.participation_counts.get(p, 0) for p in state.participants
    }
    state.auto_forced_players = compute_auto_forced_players(state.forced_players)

    return {"ok": True}


@router.post("/organizer_config")
def set_organizer_config(req: OrganizerConfigRequest):
    state.organizer_mode = req.organizer_mode
    state.organizers = sanitize_names(req.organizers, limit=10)

    valid_indices = [i for i in req.selected_organizer_indices if 0 <= i < len(state.organizers)]
    limit = 2 if req.organizer_mode == "double" else 1
    state.selected_organizer_indices = valid_indices[:limit]

    organizers = organizer_set()
    state.forced_players = [p for p in state.forced_players if p not in organizers][:forced_players_limit()]
    _clean_forced_player_teams()
    state.excluded_players = [p for p in state.excluded_players if p not in organizers]
    state.auto_forced_players = compute_auto_forced_players(state.forced_players)
    return {"ok": True}


@router.post("/forced_players")
def set_forced_players(req: ForcedPlayersRequest):
    unique = []
    organizers = organizer_set()
    for player in req.forced_players:
        if player in state.participants and player not in organizers and player not in unique:
            unique.append(player)

    state.forced_players = unique[:forced_players_limit()]
    state.forced_player_teams = {
        p: req.forced_player_teams.get(p, "none")
        for p in state.forced_players
    }
    state.auto_forced_players = compute_auto_forced_players(state.forced_players)
    return {"ok": True}


@router.post("/excluded_players")
def set_excluded_players(req: ExcludedPlayersRequest):
    unique = []
    organizers = organizer_set()
    for player in req.excluded_players:
        if player in state.participants and player not in organizers and player not in unique:
            unique.append(player)

    state.excluded_players = unique
    state.auto_forced_players = compute_auto_forced_players(state.forced_players)
    return {"ok": True}


@router.post("/draw")
def draw(req: DrawRequest):
    validate_draw_mode(req.mode)

    team_a_slots, team_b_slots = get_team_slots(req.mode)
    total_slots = team_a_slots + team_b_slots

    organizers = organizer_set()
    effective_forced = [
        p for p in state.forced_players if p in state.participants and p not in organizers
    ]

    team_a_forced_count = sum(
        1 for p in effective_forced if state.forced_player_teams.get(p) == "A"
    )
    team_b_forced_count = sum(
        1 for p in effective_forced if state.forced_player_teams.get(p) == "B"
    )

    if team_a_forced_count > team_a_slots:
        raise HTTPException(
            status_code=400,
            detail=f"チームAの強制人数（{team_a_forced_count}人）が抽選枠（{team_a_slots}人）を超えています",
        )
    if team_b_forced_count > team_b_slots:
        raise HTTPException(
            status_code=400,
            detail=f"チームBの強制人数（{team_b_forced_count}人）が抽選枠（{team_b_slots}人）を超えています",
        )
    if len(effective_forced) > total_slots:
        raise HTTPException(
            status_code=400,
            detail=f"{total_slots}人抽選では手動強制は{total_slots}人以内にしてください（現在{len(effective_forced)}人選択中）",
        )

    # 全スロットが強制チーム固定で埋まっている場合のみ再抽選をスキップする
    all_slots_fixed = (
        team_a_forced_count >= team_a_slots and team_b_forced_count >= team_b_slots
    )
    for attempt in range(_PAIR_RETRY_MAX + 1):
        selected, spin_order, selection_reasons = select_players(req.mode)
        result = build_result(req.mode, selected)
        if all_slots_fixed:
            break
        key = compute_matchup_key(result)
        count = state.pair_counts.get(key, 0)
        # 同じ組み合わせが出るたびに確率 1/(count+1) で採用、最終試行は強制採用
        if count == 0 or attempt == _PAIR_RETRY_MAX or random.random() < 1 / (count + 1):
            break
    apply_draw_result(selected, spin_order, selection_reasons, result)

    return {"round_id": state.round_id, "result": result}


@router.post("/presentation_complete")
def presentation_complete(req: PresentationCompleteRequest):
    if req.round_id != state.round_id:
        return {"ok": False, "reason": "round_id_mismatch"}

    state.phase = "result"
    return {"ok": True}


@router.delete("/history/{round_id}")
def delete_history(round_id: str):
    if state.phase == "spinning":
        raise HTTPException(status_code=400, detail="抽選演出中は削除できません")
    if not delete_history_record(round_id):
        raise HTTPException(status_code=404, detail="指定した抽選結果が見つかりません")
    return {"ok": True}


@router.post("/draw_settings")
def set_draw_settings(req: DrawSettingsRequest):
    if req.miss_threshold < 1:
        raise HTTPException(status_code=400, detail="miss_threshold must be at least 1")
    state.miss_threshold = req.miss_threshold
    state.enable_auto_force = req.enable_auto_force
    state.auto_forced_players = compute_auto_forced_players(state.forced_players)
    return {"ok": True}


@router.post("/reset")
def reset():
    reset_state()
    return {"ok": True}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            payload = state.model_dump() if hasattr(state, "model_dump") else state.dict()
            await ws.send_json(payload)
            await asyncio.sleep(0.1)
    except Exception:
        pass
