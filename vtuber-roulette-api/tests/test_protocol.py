"""プロトコル (protocol.py) が内部から切り離されていることを確かめる。"""

import ast
import typing
from pathlib import Path

from roulette import models, protocol

PROTOCOL = Path(protocol.__file__)


def test_protocol_does_not_import_internal_modules():
    imported = set()
    for node in ast.walk(ast.parse(PROTOCOL.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            imported.add(("." * node.level) + (node.module or ""))
            imported.update(f".{a.name}" for a in node.names if node.level and not node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    internal = {name for name in imported if name.startswith(".") or name.startswith("roulette")}
    assert internal == set()


def test_protocol_vocabulary_matches_the_internal_one():
    # 抽選モードや主催モードを足したら、内部とプロトコルの両方に足す (片方だけだと変換で失敗する)
    assert typing.get_args(protocol.DrawMode) == typing.get_args(models.DrawMode)
    assert typing.get_args(protocol.OrganizerMode) == typing.get_args(models.OrganizerMode)
