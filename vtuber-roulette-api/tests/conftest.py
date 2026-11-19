import random

import pytest

from roulette import router
from tests import harness


@pytest.fixture(autouse=True)
def fresh_state():
    """テストごとに新しいアプリ (とセッション) を使い、乱数も固定する。"""
    harness.start()
    random.seed(0)
    retry_max = router._PAIR_RETRY_MAX
    yield
    router._PAIR_RETRY_MAX = retry_max
