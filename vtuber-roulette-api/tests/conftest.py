import random

import pytest

from roulette import logic, router


@pytest.fixture(autouse=True)
def fresh_state():
    """抽選状態はモジュールのグローバルなので、テストごとに初期化して乱数も固定する。"""
    logic.reset_state()
    random.seed(0)
    retry_max = router._PAIR_RETRY_MAX
    yield
    router._PAIR_RETRY_MAX = retry_max
    logic.reset_state()
