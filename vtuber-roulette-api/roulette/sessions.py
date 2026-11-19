from .models import RouletteState


class SessionFactory:
    """新しい抽選セッションを作る。セッションを作るのはここだけ。

    アプリの起動 (main.create_app) とリセット (POST /reset) の両方がこれを使う。
    初期値を変えたいときは、ここ (または RouletteState の既定値) を変える。
    """

    def create(self) -> RouletteState:
        return RouletteState()
