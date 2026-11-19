"""長いセッションを通した公平さの評価。

1 回ごとのルールは守っていても、何十回も続けると偏ることがある。
ここでは評価関数 (tests/simulation.py) の値に上限を置いて、偏りが許容範囲に収まるかを見る。
"""

import random
import statistics

import pytest

from draw_config import AUTO_FORCE_MEDIAN_GAP
from roulette import router
from roulette.logic import state
from tests.simulation import (
    fair_wait_bound,
    matchup_repeat_sd,
    max_miss_streak,
    players,
    run,
    setup_session,
    worst_median_gap,
)

SEEDS = range(5)
ROUNDS = 200


@pytest.mark.parametrize(
    "n, mode",
    [
        (8, "standard_4"),
        (10, "standard_4"),
        (12, "standard_4"),
        (16, "standard_4"),
        (20, "standard_4"),
        (24, "standard_4"),
        (8, "standard_3"),
        (12, "standard_3"),
        (8, "hosts_vs_duo"),
        (12, "hosts_split_pairs"),
    ],
)
@pytest.mark.parametrize("seed", SEEDS)
def test_nobody_waits_much_longer_than_a_fair_rotation(n, mode, seed):
    random.seed(seed)
    setup_session(n, mode)

    history = run(mode, ROUNDS)

    bound = fair_wait_bound(n, mode, state.miss_threshold)
    assert max_miss_streak(history, players(n)) <= bound


def test_position_in_the_participant_list_does_not_decide_who_plays():
    # 保証対象 (ミス回数が規定に達した人) が枠より多い人数。リストの後ろの人も同じだけ出番が来るべき
    setup_session(20)

    run("standard_4", ROUNDS)

    counts = [state.participation_counts[p] for p in players(20)]
    assert max(counts) - min(counts) <= 2, counts


@pytest.mark.parametrize("n", [10, 12, 16])
@pytest.mark.parametrize("seed", SEEDS)
def test_auto_force_keeps_everyone_near_the_median(n, seed):
    random.seed(seed)
    setup_session(n, auto_force=True)

    history = run("standard_4", ROUNDS)

    assert worst_median_gap(history, players(n)) <= AUTO_FORCE_MEDIAN_GAP + 1


@pytest.mark.parametrize("n", [5, 6, 7])
def test_pair_suppression_spreads_matchups_more_evenly(n):
    def average_sd(retry_max: int) -> float:
        router._PAIR_RETRY_MAX = retry_max
        values = []
        for seed in SEEDS:
            random.seed(seed)
            setup_session(n)
            run("standard_4", ROUNDS)
            values.append(matchup_repeat_sd())
        return statistics.mean(values)

    without = average_sd(0)
    with_suppression = average_sd(10)

    assert with_suppression < without * 0.8, (with_suppression, without)
