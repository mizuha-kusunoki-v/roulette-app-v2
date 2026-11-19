from dataclasses import dataclass
from typing import Dict, List, Literal

from uuid import uuid4

from pydantic import BaseModel, Field

OrganizerMode = Literal["single", "double"]
DrawMode = Literal["standard_3", "standard_4", "hosts_vs_duo", "hosts_split_pairs"]


class ResultTeam(BaseModel):
    label: str
    players: List[str]


class RouletteResult(BaseModel):
    kind: DrawMode
    teams: List[ResultTeam]


class Round(BaseModel):
    """抽選の 1 回分。履歴はこれの配列で、最新の回は履歴の最後の要素。

    人は参加者の ID で記録する (集計は ID で数える)。表示と書き出しのために、ID → 名前も記録する。
    """

    round_id: str
    drawn_at: str  # ISO8601
    result: RouletteResult  # 表示用のチーム分け (名前)
    selected: List[str]  # 抽選で選ばれた参加者の ID (チームA → チームB の順。主催を除く)
    organizers: List[str]  # 抽選時点の有効な主催 (名前)
    participants: List[str]  # 抽選時点の参加者の ID
    names: Dict[str, str]  # 参加者の ID → 名前 (抽選時点)
    reasons: Dict[str, str] = {}  # 参加者の ID → 選ばれた理由
    matchup: str  # 対戦カードのキー (参加者は ID、主催は名前。重複ペア抑制で数える)


ForcedTeam = Literal["none", "A", "B"]  # "none" はチーム指定なし


class Participant(BaseModel):
    # 人を見分ける ID。消して同じ名前で入れ直すと新しい ID になる (別の参加者として 0 から数える)
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    forced: ForcedTeam | None = None  # None は手動強制なし
    excluded: bool = False


class Organizer(BaseModel):
    name: str
    active: bool = False  # 主催として選ばれている (主催モードの人数まで)


class RouletteState(BaseModel):
    # 利用者が入力した値
    participants: List[Participant] = []
    organizer_mode: OrganizerMode = "single"
    organizers: List[Organizer] = []
    miss_threshold: int = 3
    enable_auto_force: bool = False
    # 抽選の履歴。最新の回、その前の回はここから取り出す
    history: List[Round] = []
    # 履歴から数える集計 (logic._store_tally だけが書き込む。数え直すと遅いので保存する)
    # 今の参加者の分だけを名前で持つ (今の参加者の中では名前と ID が 1 対 1)。数えるときは ID で数える
    participation_counts: Dict[str, int] = {}
    pair_counts: Dict[str, int] = {}
    miss_counts: Dict[str, int] = {}



# ── 抽選の途中で使う値 ────────────────────────────────────────────────────────


@dataclass
class Selection:
    """1 回の抽選で選ばれた人。チームごとの並びと、選ばれた理由。"""

    team_a: List[str]
    team_b: List[str]
    reasons: Dict[str, str]

    @property
    def players(self) -> List[str]:
        """[チームA..., チームB...] の順。"""
        return self.team_a + self.team_b


@dataclass(frozen=True)
class Tally:
    """抽選の履歴から数える集計値。"""

    participation_counts: Dict[str, int]
    miss_counts: Dict[str, int]
    pair_counts: Dict[str, int]  # 対戦カード (compute_matchup_key) ごとの回数


@dataclass(frozen=True)
class DrawConstraints:
    """抽選モードの制約。判定 (logic.draw_blocker) と抽選 (logic.select_players) の両方がこれを使う。"""

    slots: Dict[str, int]  # チームごとの枠 {"A": n, "B": m}
    fixed: Dict[str, List[str]]  # チーム指定ありの手動強制 {"A": [...], "B": [...]}
    forced_any: List[str]  # チーム指定なしの手動強制
    pool: List[str]  # 手動強制以外で枠を埋められる人 (除外中でない参加者)

    @property
    def total_slots(self) -> int:
        return sum(self.slots.values())

    @property
    def forced(self) -> List[str]:
        return self.fixed["A"] + self.fixed["B"] + self.forced_any


# ── 抽選できない理由 (logic.draw_blocker が返す) ──────────────────────────────
# 文言は持たない。利用者向けの文言は messages.py が組み立てる。


@dataclass(frozen=True)
class ModeNotAvailable:
    """今の主催モードでは使えない抽選モード。"""


@dataclass(frozen=True)
class OrganizersRequired:
    required: int
    active: int


@dataclass(frozen=True)
class TeamForcedOverSlots:
    team: Literal["A", "B"]
    forced: int
    slots: int


@dataclass(frozen=True)
class TooManyForced:
    forced: int
    slots: int


@dataclass(frozen=True)
class NotEnoughParticipants:
    needed: int
    eligible: int


DrawBlock = ModeNotAvailable | OrganizersRequired | TeamForcedOverSlots | TooManyForced | NotEnoughParticipants
