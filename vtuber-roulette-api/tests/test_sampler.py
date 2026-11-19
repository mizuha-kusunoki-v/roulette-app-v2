"""weighted_subset: k 人の組が、重みの積に比例する確率で出るか。"""

import itertools
import math
import random
import time
from collections import Counter

import pytest

from roulette.sampler import weighted_subset

DRAWS = 40_000


def frequencies(items, weights, k, seed=0):
    rng = random.Random(seed)
    counts = Counter(tuple(weighted_subset(items, weights, k, rng)) for _ in range(DRAWS))
    return {combo: n / DRAWS for combo, n in counts.items()}


def expected(items, weights, k):
    w = dict(zip(items, weights))
    products = {combo: math.prod(w[p] for p in combo) for combo in itertools.combinations(items, k)}
    total = sum(products.values())
    return {combo: v / total for combo, v in products.items()}


@pytest.mark.parametrize(
    "weights, k",
    [
        ([1, 2, 3, 4, 5], 2),
        ([1, 2, 3, 4, 5], 3),
        ([0.05, 1, 1, 20, 1, 1], 2),  # 重みの差が大きい
        ([1, 1, 1, 1, 1, 1], 4),  # 同じ重みなら一様
    ],
)
def test_each_combination_comes_up_in_proportion_to_its_weight_product(weights, k):
    items = [f"P{i}" for i in range(len(weights))]

    got = frequencies(items, weights, k)
    want = expected(items, weights, k)

    assert set(got) <= set(want)
    for combo, p in want.items():
        # 二項分布の標準偏差の 5 倍まで (40000 回で、確率 0.1 なら ±0.0075)
        tolerance = 5 * math.sqrt(p * (1 - p) / DRAWS) + 1e-3
        assert abs(got.get(combo, 0.0) - p) < tolerance, (combo, got.get(combo, 0.0), p)


def test_picks_k_distinct_items_in_their_original_order():
    items = [f"P{i:02d}" for i in range(12)]
    rng = random.Random(1)
    for k in range(13):
        picked = weighted_subset(items, [1.0 + i for i in range(12)], k, rng)
        assert len(picked) == k
        assert picked == [p for p in items if p in picked]


def test_rejects_impossible_requests():
    with pytest.raises(ValueError):
        weighted_subset(["A", "B"], [1, 1], 3)
    with pytest.raises(ValueError):
        weighted_subset(["A", "B"], [1], 1)
    with pytest.raises(ValueError):
        weighted_subset(["A", "B"], [1, 0], 1)


def test_many_participants_do_not_need_enumeration():
    # 1000 人から 4 人 (組み合わせは 400 億通り) でも、1 回 1 秒もかからない
    items = [f"P{i:04d}" for i in range(1000)]
    weights = [1.0 + (i % 7) for i in range(1000)]
    start = time.perf_counter()
    weighted_subset(items, weights, 4, random.Random(0))
    assert time.perf_counter() - start < 1.0
