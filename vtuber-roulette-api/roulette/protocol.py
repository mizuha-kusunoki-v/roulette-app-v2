"""フロントとバックエンドの間のプロトコル (サーバーから送る状態と、画面から送る操作のメッセージの形)。

ここにはメッセージの形だけを置き、内部の状態 (models)・抽選のルール (logic) には依存しない。
内部と同じ名前の型 (RouletteResult など) も、ここで別に定義する。
内部の状態からこの形を組み立てるのは snapshot.py、ルールから導く値の計算は logic.py が受け持つ。
内部の持ち方を変えても、この形を保てばフロントは壊れない。
"""

from typing import Dict, List, Literal

from pydantic import BaseModel

DrawMode = Literal["standard_3", "standard_4", "hosts_vs_duo", "hosts_split_pairs"]
OrganizerMode = Literal["single", "double"]
Phase = Literal["idle", "spinning", "result"]
SelectionReason = Literal["manual_check", "miss_3", "median_gap", "random", "exception_prev_round"]
ForcedTeam = Literal["any", "A", "B"]


class ResultTeam(BaseModel):
    label: str
    players: List[str]


class RouletteResult(BaseModel):
    kind: DrawMode
    teams: List[ResultTeam]


# 抽選履歴の 1 回分。画面で JSON に書き出すときもこの形になる
# (クラスの docstring は OpenAPI の説明に入って契約が変わるので、コメントで書く)
class DrawRecord(BaseModel):
    round_id: str
    drawn_at: str  # ISO8601
    result: RouletteResult
    selected: List[str]  # 抽選で選ばれた参加者 (主催を除く)
    organizers: List[str]  # 抽選時点の有効な主催
    participants: List[str]  # 抽選時点の参加者
    reasons: Dict[str, str] = {}


class Organizer(BaseModel):
    name: str
    active: bool  # 今の主催モードで主催として選ばれている


class ParticipantStatus(BaseModel):
    name: str
    participation_count: int
    miss_count: int
    forced: ForcedTeam | None  # None = 手動強制なし、"any" = チーム指定なし
    excluded: bool
    auto_forced: bool  # 次の抽選で自動強制 (参加回数の中央値差) の対象
    due: bool  # 次の抽選でミス回数の保証の対象


class Settings(BaseModel):
    miss_threshold: int
    enable_auto_force: bool
    forced_limit: int  # 手動強制にできる最大人数


class DrawOption(BaseModel):
    mode: DrawMode
    available: bool
    unavailable_reason: str | None


class SelectionGroup(BaseModel):
    reason: SelectionReason
    players: List[str]


class CurrentRound(BaseModel):
    round_id: str
    result: RouletteResult
    # 選ばれた理由ごとの参加者。Dict にしないのは、OpenAPI から生成した型で理由が列挙型として残るようにするため
    selections: List[SelectionGroup]


class SessionState(BaseModel):
    phase: Phase
    organizer_mode: OrganizerMode
    organizers: List[Organizer]
    participants: List[ParticipantStatus]
    settings: Settings
    draw_options: List[DrawOption]  # 今の主催モードで使える抽選モードだけを並べる
    current_round: CurrentRound | None
    previous_round_players: List[str]  # 最新の回の 1 つ前の回に出た人 (管理画面の「前回参加者」)
    history: List[DrawRecord]


# ── 画面から送る操作 ─────────────────────────────────────────────────────────
# 参加者の名前は URL に入れず本文で送る (名前に "/" が入るとパスとして解釈されるため)


class ReplaceParticipantsRequest(BaseModel):
    names: List[str]


class ParticipantRequest(BaseModel):
    name: str


class SetForcedRequest(BaseModel):
    name: str
    forced: ForcedTeam | None  # None で解除


class SetExcludedRequest(BaseModel):
    name: str
    excluded: bool


class SaveOrganizersRequest(BaseModel):
    organizer_mode: OrganizerMode
    organizers: List[Organizer]  # 並び順を保つ。active は主催モードの人数まで有効


class SaveSettingsRequest(BaseModel):
    miss_threshold: int
    enable_auto_force: bool


class DrawRequest(BaseModel):
    mode: DrawMode


class PresentationCompleteRequest(BaseModel):
    round_id: str
