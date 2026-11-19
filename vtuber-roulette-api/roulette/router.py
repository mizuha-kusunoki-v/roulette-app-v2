import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .changes import state_changes
from .logic import (
    ForcedLimitError,
    active_organizers,
    add_participant,
    apply_draw_result,
    build_result,
    compute_matchup_key,
    configure_organizers,
    delete_history_record,
    draw_blocker,
    new_record,
    remove_participant,
    replace_participants,
    reset_state,
    save_settings,
    select_players,
    set_excluded,
    set_forced,
    state,
)
from .messages import describe_draw_block, forced_limit_exceeded
from .protocol import (
    DrawRequest,
    ParticipantRequest,
    PresentationCompleteRequest,
    ReplaceParticipantsRequest,
    SaveOrganizersRequest,
    SaveSettingsRequest,
    SessionState,
    SetExcludedRequest,
    SetForcedRequest,
)
from .snapshot import build_session_state

_PAIR_RETRY_MAX = 10

router = APIRouter()


def _require_participant(name: str) -> None:
    if name not in state.participants:
        raise HTTPException(status_code=404, detail=f"参加者「{name}」が見つかりません")


@router.put("/participants")
def put_participants(req: ReplaceParticipantsRequest):
    replace_participants(req.names)
    return {"ok": True}


@router.post("/participants/add")
def post_participant_add(req: ParticipantRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="参加者名を入力してください")
    if name in state.participants:
        raise HTTPException(status_code=409, detail=f"参加者「{name}」はすでにいます")
    add_participant(name)
    return {"ok": True}


@router.post("/participants/remove")
def post_participant_remove(req: ParticipantRequest):
    _require_participant(req.name)
    remove_participant(req.name)
    return {"ok": True}


@router.post("/participants/forced")
def post_participant_forced(req: SetForcedRequest):
    _require_participant(req.name)
    # プロトコルではチーム指定なしを "any"、内部では "none" で持つ
    team = None if req.forced is None else ("none" if req.forced == "any" else req.forced)
    try:
        set_forced(req.name, team)
    except ForcedLimitError as e:
        raise HTTPException(status_code=400, detail=forced_limit_exceeded(e.limit))
    return {"ok": True}


@router.post("/participants/excluded")
def post_participant_excluded(req: SetExcludedRequest):
    _require_participant(req.name)
    set_excluded(req.name, req.excluded)
    return {"ok": True}


@router.put("/organizers")
def put_organizers(req: SaveOrganizersRequest):
    configure_organizers(
        req.organizer_mode,
        [o.name for o in req.organizers],
        [o.name for o in req.organizers if o.active],
    )
    return {"ok": True}


@router.put("/settings")
def put_settings(req: SaveSettingsRequest):
    if req.miss_threshold < 1:
        raise HTTPException(status_code=400, detail="救済閾値は1以上にしてください")
    save_settings(req.miss_threshold, req.enable_auto_force)
    return {"ok": True}


@router.post("/draw")
def draw(req: DrawRequest):
    block = draw_blocker(req.mode)
    if block is not None:
        raise HTTPException(status_code=400, detail=describe_draw_block(block))

    organizers = active_organizers()
    for attempt in range(_PAIR_RETRY_MAX + 1):
        selection = select_players(req.mode)
        result = build_result(req.mode, selection, organizers)
        count = state.pair_counts.get(compute_matchup_key(result), 0)
        # 同じ組み合わせが出るたびに確率 1/(count+1) で採用、最終試行は強制採用
        if count == 0 or attempt == _PAIR_RETRY_MAX or random.random() < 1 / (count + 1):
            break
    apply_draw_result(
        new_record(
            round_id=str(uuid.uuid4()),
            drawn_at=datetime.now(timezone.utc).isoformat(),
            result=result,
            selection=selection,
            organizers=organizers,
            participants=state.participants,
        )
    )

    # 結果は /session と /ws/session で届くので、ここでは回の ID だけを返す (内部のモデルを外に出さない)
    return {"round_id": state.round_id}


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


@router.post("/reset")
def reset():
    reset_state()
    return {"ok": True}


async def _push(ws: WebSocket, build: Callable[[], BaseModel]) -> None:
    """接続直後に build() の結果を送り、その後は内容が変わったときだけ送る。"""
    last_sent = None
    while True:
        # 状態を読む前に version を取っておく。読んだ後の変更は wait_after がすぐ返すので取りこぼさない
        version = state_changes.version
        payload = build().model_dump(mode="json")
        if payload != last_sent:
            await ws.send_json(payload)
            last_sent = payload
        await state_changes.wait_after(version)


async def _wait_disconnect(ws: WebSocket) -> None:
    """クライアントは何も送ってこないので、受信は切断を知るためだけに使う。"""
    while True:
        await ws.receive_text()  # 切断されると WebSocketDisconnect が上がる


async def _serve(ws: WebSocket, build: Callable[[], BaseModel]) -> None:
    await ws.accept()
    push = asyncio.create_task(_push(ws, build))
    listen = asyncio.create_task(_wait_disconnect(ws))
    done, pending = await asyncio.wait({push, listen}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        error = task.exception()
        if error is not None and not isinstance(error, WebSocketDisconnect):
            raise error


# ── プロトコル (サーバーから送る状態) ─────────────────────────────────────────


@router.get("/session")
def get_session() -> SessionState:
    return build_session_state()


@router.websocket("/ws/session")
async def session_websocket(ws: WebSocket):
    await _serve(ws, build_session_state)
