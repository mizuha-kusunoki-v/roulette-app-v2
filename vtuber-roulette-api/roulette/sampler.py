"""重み付きの抽選の道具。乱数と重みだけを見る (session を読まない)。"""

import random
from typing import List, Sequence


def weighted_subset(items: Sequence[str], weights: Sequence[float], k: int, rng: random.Random | None = None) -> List[str]:
    """items から k 人を引く。ある k 人の組が出る確率は、その k 人の重みの積に比例する (近似ではなく正確)。

    「残りの人から j 人選ぶ組の重みの積の総和」を後ろから数えておき、前から 1 人ずつ入れるか決める。
    人数 n に対して n×k 回の計算で済むので、参加者が多くても組み合わせを列挙しなくてよい。
    重みは正の数。戻り値は items の並び順。
    """
    n = len(items)
    if len(weights) != n:
        raise ValueError(f"{n} items but {len(weights)} weights")
    if not 0 <= k <= n:
        raise ValueError(f"cannot pick {k} of {n}")
    if any(not w > 0 for w in weights):
        raise ValueError("weights must be positive")
    rand = rng.random if rng is not None else random.random

    # total[i][j] = items[i:] から j 人選ぶ組の、重みの積の総和 (j 人に足りなければ 0)
    total = [[0.0] * (k + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        total[i][0] = 1.0
    for i in range(n - 1, -1, -1):
        for j in range(1, k + 1):
            total[i][j] = total[i + 1][j] + weights[i] * total[i + 1][j - 1]

    picked: List[str] = []
    j = k
    for i in range(n):
        if j == 0:
            break
        # items[i] を入れる組の重みの総和 / items[i:] から j 人選ぶ組の重みの総和
        # 残りがちょうど j 人なら total[i + 1][j] が 0 なので、必ず入る
        if rand() * total[i][j] < weights[i] * total[i + 1][j - 1]:
            picked.append(items[i])
            j -= 1
    return picked
