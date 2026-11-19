"""抽選ロジックの評価用シミュレーションと評価関数。

抽選は API と同じ入口 (router.draw) から呼ぶので、重複ペア抑制の再抽選も含めて評価できる。
状態はモジュールのグローバル (logic.state) なので、各テストの前に conftest がリセットする。
"""

import math
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence

from roulette import logic, router
from roulette.logic import get_team_slots, state
from roulette.models import DrawMode, DrawRequest

HOST_MODES: tuple[DrawMode, ...] = ("hosts_vs_duo", "hosts_split_pairs")


def players(n: int) -> List[str]:
    return [f"P{i:02d}" for i in range(n)]


def setup_session(
    n: int,
    mode: DrawMode = "standard_4",
    *,
    auto_force: bool = False,
    miss_threshold: int = 3,
    excluded: Sequence[str] = (),
    forced: Sequence[str] = (),
    forced_teams: Dict[str, str] | None = None,
) -> None:
    """n 人の参加者で抽選できる状態にする。主催はモードに合わせて自動で置く。"""
    logic.reset_state()
    state.participants = players(n)
    if mode in HOST_MODES:
        state.organizer_mode = "double"
        state.organizers = ["Host1", "Host2"]
        state.selected_organizer_indices = [0, 1]
    elif mode == "standard_3":
        state.organizers = ["Host1"]
    state.enable_auto_force = auto_force
    state.miss_threshold = miss_threshold
    state.excluded_players = list(excluded)
    state.forced_players = list(forced)
    state.forced_player_teams = dict(forced_teams or {p: "none" for p in forced})


def slots(mode: DrawMode) -> int:
    a, b = get_team_slots(mode)
    return a + b


@dataclass
class Round:
    """1 回の抽選の前後の情報。評価関数はこれの列を受け取る。"""

    before: Dict  # 抽選前の state (model_dump)
    selected: List[str]  # [チームA..., チームB...] の順
    team_a: List[str]
    team_b: List[str]
    reasons: Dict[str, str]


def draw(mode: DrawMode) -> Round:
    before = state.model_dump()
    router.draw(DrawRequest(mode=mode))
    a_slots, _ = get_team_slots(mode)
    selected = list(state.last_players)
    return Round(
        before=before,
        selected=selected,
        team_a=selected[:a_slots],
        team_b=selected[a_slots:],
        reasons=dict(state.last_selection_reasons),
    )


def run(mode: DrawMode, rounds: int) -> List[Round]:
    return [draw(mode) for _ in range(rounds)]


# ── 評価関数 ──────────────────────────────────────────────────────────────────


def max_miss_streak(history: Iterable[Round], candidates: Sequence[str]) -> int:
    """candidates の誰かが連続で外れた回数の最大値。"""
    streak = {p: 0 for p in candidates}
    worst = 0
    for r in history:
        for p in candidates:
            streak[p] = 0 if p in r.selected else streak[p] + 1
            worst = max(worst, streak[p])
    return worst


def worst_median_gap(history: Iterable[Round], candidates: Sequence[str]) -> float:
    """各抽選の後で「参加回数の中央値 - 最小値」が最も開いたときの値。"""
    counts = {p: 0 for p in candidates}
    worst = 0.0
    for r in history:
        for p in r.selected:
            if p in counts:
                counts[p] += 1
        values = list(counts.values())
        worst = max(worst, statistics.median(values) - min(values))
    return worst


def matchup_repeat_sd() -> float:
    """同じ対戦カードが出た回数のばらつき (標準偏差)。小さいほど偏りが少ない。"""
    return statistics.pstdev(Counter(state.pair_counts).values())


def fair_wait_bound(n_candidates: int, mode: DrawMode, miss_threshold: int) -> int:
    """連続で外れる回数の上限の目安。

    全員を順番に回すと ceil(n / 枠) 回に 1 回は出番が来る。ミス回数の保証は miss_threshold 回で効く。
    どちらか遅い方に、同時に保証対象が重なったときの 1 回分を足す。
    """
    return max(miss_threshold, math.ceil(n_candidates / slots(mode))) + 1


@dataclass
class Scenario:
    n: int
    mode: DrawMode
    auto_force: bool = False
    miss_threshold: int = 3
    excluded: List[str] = field(default_factory=list)
    forced: List[str] = field(default_factory=list)
    forced_teams: Dict[str, str] = field(default_factory=dict)
