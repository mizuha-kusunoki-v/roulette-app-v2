import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from starlette.requests import HTTPConnection
from pydantic import BaseModel

from .changes import StateChanges
from .logic import (
    ForcedLimitError,
    active_organizers,
    add_participant,
    apply_draw_result,
    configure_organizers,
    delete_history_record,
    draw_blocker,
    find_participant,
    matchup_key,
    new_round,
    remove_participant,
    replace_participants,
    save_settings,
    select_players,
    set_excluded,
    set_forced,
)
from .models import RouletteState
from .messages import describe_draw_block, forced_limit_exceeded
from .protocol import (
    DrawRequest,
    DrawResponse,
    ParticipantRequest,
    ReplaceParticipantsRequest,
    Revision,
    SaveOrganizersRequest,
    SaveSettingsRequest,
    SessionState,
    SetExcludedRequest,
    SetForcedRequest,
)
from .snapshot import build_session_state

_PAIR_RETRY_MAX = 10

router = APIRouter()


def current_session(conn: HTTPConnection) -> RouletteState:
    """リクエスト (WebSocket を含む) のアプリが持つセッション。置き場所は composition root (main.create_app) が決める。"""
    return conn.app.state.session


Session = Depends(current_session)


def _require_participant(session: RouletteState, name: str) -> None:
    if find_participant(session, name) is None:
        raise HTTPException(status_code=404, detail=f"参加者「{name}」が見つかりません")


@router.put("/participants")
def put_participants(req: ReplaceParticipantsRequest, session: RouletteState = Session):
    replace_participants(session, req.names)
    return {"ok": True}


@router.post("/participants/add")
def post_participant_add(req: ParticipantRequest, session: RouletteState = Session):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="参加者名を入力してください")
    if find_participant(session, name) is not None:
        raise HTTPException(status_code=409, detail=f"参加者「{name}」はすでにいます")
    add_participant(session, name)
    return {"ok": True}


@router.post("/participants/remove")
def post_participant_remove(req: ParticipantRequest, session: RouletteState = Session):
    _require_participant(session, req.name)
    remove_participant(session, req.name)
    return {"ok": True}


@router.post("/participants/forced")
def post_participant_forced(req: SetForcedRequest, session: RouletteState = Session):
    _require_participant(session, req.name)
    # プロトコルではチーム指定なしを "any"、内部では "none" で持つ
    team = None if req.forced is None else ("none" if req.forced == "any" else req.forced)
    try:
        set_forced(session, req.name, team)
    except ForcedLimitError as e:
        raise HTTPException(status_code=400, detail=forced_limit_exceeded(e.limit))
    return {"ok": True}


@router.post("/participants/excluded")
def post_participant_excluded(req: SetExcludedRequest, session: RouletteState = Session):
    _require_participant(session, req.name)
    set_excluded(session, req.name, req.excluded)
    return {"ok": True}


@router.put("/organizers")
def put_organizers(req: SaveOrganizersRequest, session: RouletteState = Session):
    configure_organizers(
        session,
        req.organizer_mode,
        [o.name for o in req.organizers],
        [o.name for o in req.organizers if o.active],
    )
    return {"ok": True}


@router.put("/settings")
def put_settings(req: SaveSettingsRequest, session: RouletteState = Session):
    if req.miss_threshold < 1:
        raise HTTPException(status_code=400, detail="救済閾値は1以上にしてください")
    save_settings(session, req.miss_threshold, req.enable_auto_force)
    return {"ok": True}


@router.post("/draw")
def draw(req: DrawRequest, session: RouletteState = Session) -> DrawResponse:
    block = draw_blocker(session, req.mode)
    if block is not None:
        raise HTTPException(status_code=400, detail=describe_draw_block(block))

    organizers = active_organizers(session)
    for attempt in range(_PAIR_RETRY_MAX + 1):
        selection = select_players(session, req.mode)
        count = session.pair_counts.get(matchup_key(session, req.mode, selection, organizers), 0)
        # 同じ組み合わせが出るたびに確率 1/(count+1) で採用、最終試行は強制採用
        if count == 0 or attempt == _PAIR_RETRY_MAX or random.random() < 1 / (count + 1):
            break
    new = new_round(
        session,
        round_id=str(uuid.uuid4()),
        drawn_at=datetime.now(timezone.utc).isoformat(),
        mode=req.mode,
        selection=selection,
        organizers=organizers,
    )
    apply_draw_result(session, new)

    # 結果は /session と /ws/session で届くので、ここでは回の ID だけを返す (内部のモデルを外に出さない)
    return DrawResponse(round_id=new.round_id)


@router.delete("/history/{round_id}")
def delete_history(round_id: str, session: RouletteState = Session):
    if not delete_history_record(session, round_id):
        raise HTTPException(status_code=404, detail="指定した抽選結果が見つかりません")
    return {"ok": True}


@router.post("/reset")
def reset(request: Request):
    # セッションを作り直して差し替える (エンドポイントはリクエストのたびにアプリから受け取るので、それで足りる)
    request.app.state.session = request.app.state.session_factory.create()
    return {"ok": True}


def build_state(conn: HTTPConnection) -> SessionState:
    """今の状態にその新しさの印 (Revision) を付けて返す。GET /session と /ws/session が同じ組み立てを使う。

    呼ぶ側が状態の鍵 (main.create_app の state_lock) を持っている間に呼ぶ。GET /session はミドルウェアが、
    /ws/session は _push が鍵を取る。鍵の中では書き込みが起きないので、印と状態はいつも同じ時点のものになる。
    """
    changes: StateChanges = conn.app.state.changes
    revision = Revision(instance_id=changes.instance_id, version=changes.version)
    return build_session_state(current_session(conn), revision)


async def _push(ws: WebSocket, build: Callable[[], BaseModel], changes: StateChanges, lock: asyncio.Lock) -> None:
    """接続直後に build() の結果を送り、その後は書き込みの通知のたびに送る (内容が前回と同じでも送る)。

    組み立てる間は、HTTP のリクエストと同じ鍵 (main.create_app の state_lock) を持つ。書き込みの途中を読まず、
    組み立てた状態と version はいつも同じ時点のものになる。送るのは鍵を放してから (遅い接続が書き込みを止めないように)。
    """
    while True:
        async with lock:
            version = changes.version
            payload = build().model_dump(mode="json")
        await ws.send_json(payload)
        # 組み立てた後の書き込みは version を進めるので、wait_after がすぐ返して取りこぼさない
        await changes.wait_after(version)


async def _wait_disconnect(ws: WebSocket) -> None:
    """クライアントは何も送ってこないので、受信は切断を知るためだけに使う。"""
    while True:
        await ws.receive_text()  # 切断されると WebSocketDisconnect が上がる


async def _serve(ws: WebSocket, build: Callable[[], BaseModel], changes: StateChanges, lock: asyncio.Lock) -> None:
    await ws.accept()
    push = asyncio.create_task(_push(ws, build, changes, lock))
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
def get_session(request: Request) -> SessionState:
    return build_state(request)


@router.websocket("/ws/session")
async def session_websocket(ws: WebSocket):
    # リセットでセッションが差し替わるので、送るたびにアプリから取り出す
    await _serve(ws, lambda: build_state(ws), ws.app.state.changes, ws.app.state.state_lock)
