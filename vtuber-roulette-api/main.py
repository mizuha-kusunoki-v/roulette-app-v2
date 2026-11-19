"""アプリの組み立て (composition root)。

セッションと変更通知はグローバル変数に持たず、ここで作って app.state に置く。
router のエンドポイントは、リクエストのアプリからそれを受け取る (roulette.router.current_session)。

状態の読み書きは、app.state.state_lock を持っている間だけ行う。HTTP のリクエストは下のミドルウェアが
まるごと鍵の中で動かし、WebSocket は状態を組み立てる間だけ同じ鍵を取る (roulette.router._push)。
FastAPI は def のエンドポイントをスレッドで並行に動かすので、鍵がないと書き込みどうしがぶつかって
抽選が消えたり、集計が履歴と食い違ったりする (tests/test_concurrency.py)。
"""

import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from roulette.changes import StateChanges
from roulette.router import router as roulette_router
from roulette.sessions import SessionFactory


# フロントの開発サーバーの住所。localhost と 127.0.0.1 は別のオリジンなので、どちらで開いても使えるよう両方を許可する
FRONTEND_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(session_factory: SessionFactory | None = None) -> FastAPI:
    factory = session_factory or SessionFactory()

    app = FastAPI()
    app.state.session_factory = factory
    app.state.session = factory.create()
    app.state.changes = StateChanges()
    # asyncio.Lock にする。threading.Lock をミドルウェア (イベントループ) で取ると、鍵を待つ間ループが止まり、
    # 鍵を持っているリクエストも終われなくなる (ループに戻れない) ので止まったままになる
    app.state.state_lock = asyncio.Lock()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=FRONTEND_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def one_request_at_a_time(request: Request, call_next):
        # リクエストを 1 つずつ動かす。読むだけの GET も、書き込みの途中を読まないように鍵の中で動かす。
        # 状態を書き換えるのは GET 以外の API だけなので、その後に /ws へ知らせる (失敗したリクエストでも知らせる)。
        # 知らせるのも鍵の中で行う。WebSocket が鍵を取って組み立てる状態と version は、いつも同じ時点のものになる
        async with request.app.state.state_lock:
            response = await call_next(request)
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                await request.app.state.changes.notify()
        return response

    app.include_router(roulette_router)
    return app


# uvicorn main:app で起動するアプリ
app = create_app()
