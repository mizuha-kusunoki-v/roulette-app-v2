from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from roulette.changes import state_changes
from roulette.router import router as roulette_router

app = FastAPI()

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
        await state_changes.notify()
    return response


app.include_router(roulette_router)
