"""テスト用のセッションビルダー。テストに必要な状態を宣言的に作る。

参加者・主催・設定・除外・手動強制は、画面と同じ操作の関数 (logic) で組み立てる。
画面の操作では作れない値 (参加回数・ミス回数・最新の回に出た人) だけを直接入れる。
テストの中で、セッションの組み立て方 (内部の状態の形) を知っているのはここと harness.py だけ。
"""

from typing import Dict, List

from roulette import logic
from roulette.models import DrawMode, OrganizerMode, ResultTeam, Round, RouletteResult, RouletteState
from roulette.sessions import SessionFactory

HOST_MODES: tuple[DrawMode, ...] = ("hosts_vs_duo", "hosts_split_pairs")


def players(n: int) -> List[str]:
    return [f"P{i:02d}" for i in range(n)]


class SessionBuilder:
    def __init__(self) -> None:
        self._participants: List[str] = []
        self._organizer_mode: OrganizerMode = "single"
        self._organizers: List[str] = []
        self._active_organizers: List[str] = []
        self._auto_force = False
        self._excluded: List[str] = []
        self._forced: Dict[str, str] = {}
        self._participation: Dict[str, int] | None = None
        self._miss: Dict[str, int] | None = None
        self._last_round: List[str] | None = None

    def participants(self, n_or_names: int | List[str]) -> "SessionBuilder":
        self._participants = players(n_or_names) if isinstance(n_or_names, int) else list(n_or_names)
        return self

    def organizers(self, mode: OrganizerMode, names: List[str], active: List[str] | None = None) -> "SessionBuilder":
        """主催の候補と、そのうち選ぶ人 (省略すると全員)。"""
        self._organizer_mode = mode
        self._organizers = list(names)
        self._active_organizers = list(names if active is None else active)
        return self

    def organizers_for(self, mode: DrawMode) -> "SessionBuilder":
        """抽選モードに合わせた主催を置く (主催 2 人の抽選は Host1・Host2、3 人抽選は Host1)。"""
        if mode in HOST_MODES:
            return self.organizers("double", ["Host1", "Host2"])
        if mode == "standard_3":
            return self.organizers("single", ["Host1"])
        return self

    def settings(self, *, auto_force: bool = False) -> "SessionBuilder":
        self._auto_force = auto_force
        return self

    def excluded(self, *names: str) -> "SessionBuilder":
        self._excluded += list(names)
        return self

    def forced(self, name: str, team: str = "none") -> "SessionBuilder":
        """手動強制。team は "none" (チーム指定なし) / "A" / "B"。"""
        self._forced[name] = team
        return self

    def counts(self, *, participation: Dict[str, int] | None = None, miss: Dict[str, int] | None = None) -> "SessionBuilder":
        """参加回数・ミス回数 (書いていない人は 0)。画面の操作では作れないので直接入れる。"""
        if participation is not None:
            self._participation = dict(participation)
        if miss is not None:
            self._miss = dict(miss)
        return self

    def last_round(self, names: List[str]) -> "SessionBuilder":
        """最新の回に出た人。その人たちが出た回を 1 件、履歴に足す (集計は counts で決めた値のまま)。"""
        self._last_round = list(names)
        return self

    def build(self) -> RouletteState:
        session = SessionFactory().create()
        logic.replace_participants(session, self._participants)
        if self._organizers:
            logic.configure_organizers(session, self._organizer_mode, self._organizers, self._active_organizers)
        logic.save_settings(session, self._auto_force)
        for name in self._excluded:
            logic.set_excluded(session, name, True)
        for name, team in self._forced.items():
            logic.set_forced(session, name, team)
        if self._participation is not None:
            session.participation_counts = {p: self._participation.get(p, 0) for p in logic.participant_names(session)}
        if self._miss is not None:
            session.miss_counts = {p: self._miss.get(p, 0) for p in logic.participant_names(session)}
        if self._last_round is not None:
            id_of = {p.name: p.id for p in session.participants}
            ids = [id_of[p] for p in self._last_round]
            session.history = session.history + [
                Round(
                    round_id="builder-last-round",
                    drawn_at="2026-01-01T00:00:00+00:00",
                    result=RouletteResult(kind="standard_4", teams=[ResultTeam(label="チームA", players=list(self._last_round))]),
                    selected=ids,
                    organizers=[],
                    participants=[p.id for p in session.participants],
                    names={p.id: p.name for p in session.participants},
                    reasons={i: "random" for i in ids},
                    matchup="builder-last-round",
                    presented=True,
                )
            ]
        return session
