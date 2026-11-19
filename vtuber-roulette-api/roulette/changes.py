import asyncio
from uuid import uuid4


class StateChanges:
    """状態が変わったかもしれないことを、待っている WebSocket 接続に知らせる。

    notify() は書き込み系の API が終わるたびに version を進め、待っている接続を起こす。
    起こされた接続は、内容が変わったかどうかによらず今の状態を送る (router._push)。
    待っている間は Condition の上で眠るだけで、CPU は使わない。
    """

    def __init__(self) -> None:
        # サーバーを起動し直すと version は 0 に戻る。画面が古い version と取り違えないよう、起動ごとに変わる ID を持つ
        self.instance_id = uuid4().hex
        self._version = 0
        self._cond = asyncio.Condition()

    @property
    def version(self) -> int:
        return self._version

    async def notify(self) -> None:
        async with self._cond:
            self._version += 1
            self._cond.notify_all()

    async def wait_after(self, version: int) -> int:
        """version より後の合図が来るまで待ち、そのときの version を返す。"""
        async with self._cond:
            await self._cond.wait_for(lambda: self._version != version)
            return self._version

