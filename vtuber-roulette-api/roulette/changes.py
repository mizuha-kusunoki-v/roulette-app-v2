import asyncio


class StateChanges:
    """状態が変わったかもしれないことを、待っている WebSocket 接続に知らせる。

    notify() は「変わったかもしれない」という合図だけを送る。実際に変わったかどうかは、
    受け取った側が前回送った内容と比べて判断する。
    """

    def __init__(self) -> None:
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

