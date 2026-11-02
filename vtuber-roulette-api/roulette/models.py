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


# ── リクエストモデル ──────────────────────────────────────────────────────────

class ParticipantsRequest(BaseModel):
    participants: List[str]


class OrganizerConfigRequest(BaseModel):
    organizer_mode: OrganizerMode
    organizers: List[str]
    selected_organizer_indices: List[int] = [0]


class ForcedPlayersRequest(BaseModel):
    forced_players: List[str]
    forced_player_teams: Dict[str, str] = {}


class ExcludedPlayersRequest(BaseModel):
    excluded_players: List[str]


class DrawRequest(BaseModel):
    mode: DrawMode


class PresentationCompleteRequest(BaseModel):
    round_id: str


class DrawSettingsRequest(BaseModel):
    miss_threshold: int
    enable_auto_force: bool
