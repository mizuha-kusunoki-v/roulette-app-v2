"""アプリの組み立て (composition root)。

セッションと変更通知はグローバル変数に持たず、ここで作って app.state に置く。
router のエンドポイントは、リクエストのアプリからそれを受け取る (roulette.router.current_session)。
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from roulette.changes import StateChanges
from roulette.router import router as roulette_router
from roulette.sessions import SessionFactory


def create_app(session_factory: SessionFactory | None = None) -> FastAPI:
    factory = session_factory or SessionFactory()

    app = FastAPI()
    app.state.session_factory = factory
    app.state.session = factory.create()
    app.state.changes = StateChanges()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def notify_state_changes(request: Request, call_next):
        # 状態を書き換えるのは GET 以外の API だけなので、その後に /ws へ知らせる。
        # 失敗したリクエストでも知らせてよい（変わっていなければ /ws 側が送らない）。
        response = await call_next(request)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            await request.app.state.changes.notify()
        return response

    app.include_router(roulette_router)
    return app


# uvicorn main:app で起動するアプリ
app = create_app()
