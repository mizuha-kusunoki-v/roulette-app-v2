"""重み付き抽選の確率が、draw_config の式どおりになっているか。

手動強制と、一番長く外れている人のうち 1 人を入れたあと、残りの枠を重みで引く (前回出た人は、ほかで埋まらないときだけ)。
結果 (誰が出るか + チーム分け) の確率は「引いた人の exp(点数) の積 × exp(-PAIR_PENALTY × その対戦カードが出た回数)」に比例する。
点数 = WAIT_WEIGHT × 連続で外れた回数 + DEFICIT_WEIGHT × 中央値より少ない参加回数 (自動強制 ON のとき)。
select_players は状態を変えないので、同じ状態から何千回も引いて割合を見る。
"""

import math
from collections import Counter

import pytest

from roulette import logic
from tests import harness
from tests.builders import SessionBuilder, players
from tests.simulation import draw

DRAWS = 4000


def tolerance(p: float, n: int = DRAWS) -> float:
    """二項分布の標準偏差の 5 倍。"""
    return 5 * math.sqrt(p * (1 - p) / n)


def left_out_share(mode="standard_4") -> Counter:
    """DRAWS 回引いて、各参加者が選ばれなかった割合。"""
    session = harness.session()
    out: Counter = Counter()
    for _ in range(DRAWS):
        picked = set(logic.select_players(session, mode).players)
        out.update(p for p in harness.participants() if p not in picked)
    return Counter({p: n / DRAWS for p, n in out.items()})


@pytest.fixture
def three_of_four():
    """5 人で 4 人抽選。P00 は一番長く外れている (2 回) ので確定で入り、残り P01〜P04 の 4 人から 3 人を引く。

    4 人から 3 人を引くとき、ある人が外れる確率は 1 / その人の重み に比例する。P02〜P04 は点数 0 (重み 1)。
    """
    return SessionBuilder().participants(5)


def p01_left_out(score: float) -> float:
    """P01 の点数が score、P02〜P04 が 0 のとき、P01 が外れる確率。"""
    return math.exp(-score) / (math.exp(-score) + 3)


def test_one_more_miss_makes_a_player_e_to_the_weight_times_as_likely(three_of_four):
    harness.use(three_of_four.counts(miss={"P00": 2, "P01": 1}).build())

    share = left_out_share()

    assert share["P00"] == 0  # 一番長く外れている人は確定
    expected = p01_left_out(logic.WAIT_WEIGHT * 1)
    assert abs(share["P01"] - expected) < tolerance(expected), share


@pytest.mark.parametrize("auto_force", [False, True])
def test_participation_below_the_median_counts_only_with_auto_force(three_of_four, auto_force):
    # 参加回数の中央値は 2。P01 は 2 回少ない
    participation = {p: 2 for p in players(5)} | {"P01": 0}
    harness.use(three_of_four.settings(auto_force=auto_force).counts(participation=participation, miss={"P00": 2}).build())

    share = left_out_share()

    expected = p01_left_out(logic.DEFICIT_WEIGHT * 2 if auto_force else 0.0)
    assert abs(share["P01"] - expected) < tolerance(expected), share


@pytest.mark.parametrize("path", ["enumerate", "sample"])
def test_a_matchup_drawn_before_is_e_to_the_penalty_times_less_likely(path, monkeypatch):
    # 4 人で 4 人抽選。毎回全員出るので、変わるのはチーム分け (3 通り) だけ
    if path == "sample":
        monkeypatch.setattr(logic, "ENUM_LIMIT", 0)
    harness.use(SessionBuilder().participants(4).build())
    first = draw("standard_4")
    seen = frozenset([frozenset(first.team_a), frozenset(first.team_b)])

    session = harness.session()
    hits = 0
    for _ in range(DRAWS):
        s = logic.select_players(session, "standard_4")
        hits += frozenset([frozenset(s.team_a), frozenset(s.team_b)]) == seen

    # 1 回出たカードの重みは exp(-penalty)、まだ出ていない 2 通りは 1
    q = math.exp(-logic.PAIR_PENALTY)
    expected = q / (q + 2)
    assert abs(hits / DRAWS - expected) < tolerance(expected), hits / DRAWS


def lineup_shares(session, mode) -> Counter:
    counts: Counter = Counter()
    for _ in range(DRAWS):
        s = logic.select_players(session, mode)
        counts[(frozenset(s.team_a), frozenset(s.team_b))] += 1
    return Counter({k: n / DRAWS for k, n in counts.items()})


def test_sampling_gives_the_same_chances_as_enumerating_every_lineup(monkeypatch):
    # 組み合わせが多いとき (ENUM_LIMIT 超え) の道を、全部列挙する道と比べる。
    # 6 人で 4 人抽選を 30 回: 前回出た 4 人から 2 人を足すので、外れた回数で重みが変わり、
    # 同じ対戦カードが何度も出て減点も効く
    harness.use(SessionBuilder().participants(6).settings(miss_threshold=10).build())
    for _ in range(30):
        draw("standard_4")
    session = harness.session()

    enumerated = lineup_shares(session, "standard_4")
    monkeypatch.setattr(logic, "ENUM_LIMIT", 0)
    sampled = lineup_shares(session, "standard_4")

    assert len(enumerated) > 10  # 比べる意味がある程度には結果がばらけている
    for key in set(enumerated) | set(sampled):
        a, b = enumerated.get(key, 0.0), sampled.get(key, 0.0)
        p = (a + b) / 2
        # 2 つの割合の差の標準偏差の 5 倍
        assert abs(a - b) < 5 * math.sqrt(2 * p * (1 - p) / DRAWS) + 1e-3, (key, a, b)
