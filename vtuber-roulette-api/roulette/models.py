from dataclasses import dataclass
from typing import Dict, List, Literal

from pydantic import BaseModel

OrganizerMode = Literal["single", "double"]
DrawMode = Literal["standard_3", "standard_4", "hosts_vs_duo", "hosts_split_pairs"]


class ResultTeam(BaseModel):
    label: str
    players: List[str]


class RouletteResult(BaseModel):
    kind: DrawMode
    teams: List[ResultTeam]


class DrawRecord(BaseModel):
    round_id: str
    drawn_at: str  # ISO8601
    result: RouletteResult
    selected: List[str]  # 抽選で選ばれた参加者 (主催を除く)
    organizers: List[str]  # 抽選時点の有効な主催
    participants: List[str]  # 抽選時点の参加者
    reasons: Dict[str, str] = {}


class RouletteState(BaseModel):
    participants: List[str] = []
    organizer_mode: OrganizerMode = "single"
    organizers: List[str] = []
    selected_organizer_indices: List[int] = [0]
    forced_players: List[str] = []
    forced_player_teams: Dict[str, str] = {}
    miss_threshold: int = 3
    enable_auto_force: bool = False
    auto_forced_players: List[str] = []
    excluded_players: List[str] = []
    participation_counts: Dict[str, int] = {}
    pair_counts: Dict[str, int] = {}
    prev_players: List[str] = []
    last_players: List[str] = []
    spin_order: List[str] = []
    miss_counts: Dict[str, int] = {}
    last_selection_reasons: Dict[str, str] = {}
    result: RouletteResult | None = None
    round_id: str | None = None
    phase: Literal["idle", "spinning", "result"] = "idle"
    history: List[DrawRecord] = []


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
