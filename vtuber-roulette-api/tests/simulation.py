"""抽選ロジックの評価用シミュレーションと評価関数。

抽選は API と同じ入口 (router.draw) から呼ぶので、重複ペア抑制の再抽選も含めて評価できる。
状態は操作 (logic の操作関数) で作り、結果は tests/harness.py を通して名前で読む。
状態はモジュールのグローバルなので、各テストの前に conftest がリセットする。
"""

import math
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence

from roulette import logic, router
from roulette.logic import get_team_slots
from roulette.models import DrawMode
from roulette.protocol import DrawRequest
from tests import harness

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
    """n 人の参加者で抽選できる状態を、画面と同じ操作で作る。主催はモードに合わせて置く。

    forced_teams は "none" (チーム指定なし) / "A" / "B"。
    """
    session = harness.new_session()
    logic.replace_participants(session, players(n))
    if mode in HOST_MODES:
        logic.configure_organizers(session, "double", ["Host1", "Host2"], ["Host1", "Host2"])
    elif mode == "standard_3":
        logic.configure_organizers(session, "single", ["Host1"], ["Host1"])
    logic.save_settings(session, miss_threshold, auto_force)
    for p in excluded:
        logic.set_excluded(session, p, True)
    teams = forced_teams or {}
    for p in forced:
        logic.set_forced(session, p, teams.get(p, "none"))


def slots(mode: DrawMode) -> int:
    a, b = get_team_slots(mode)
    return a + b


@dataclass
class Round:
    """1 回の抽選の前後の情報。評価関数はこれの列を受け取る。"""

    before: harness.Before
    selected: List[str]  # [チームA..., チームB...] の順
    team_a: List[str]
    team_b: List[str]
    reasons: Dict[str, str]


def draw(mode: DrawMode) -> Round:
    before = harness.before()
    router.draw(DrawRequest(mode=mode), harness.session())
    a_slots, _ = get_team_slots(mode)
    record = harness.latest_record()
    return Round(
        before=before,
        selected=record.selected,
        team_a=record.selected[:a_slots],
        team_b=record.selected[a_slots:],
        reasons=record.reasons,
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
    return statistics.pstdev(Counter(harness.pair_counts()).values())


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
