import random

import pytest

from tests import harness


@pytest.fixture(autouse=True)
def fresh_state():
    """テストごとに新しいアプリ (とセッション) を使い、乱数も固定する。"""
    harness.start()
    random.seed(0)
