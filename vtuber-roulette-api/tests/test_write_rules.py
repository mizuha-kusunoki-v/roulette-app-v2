"""セッションへの書き込みのルールを、ソースコードから確かめる。

履歴から数える集計 (参加回数・ミス回数・対戦カードの回数) を書き込むのは logic._store_tally だけ
(logic.py の「抽選結果と履歴の削除を状態に反映する」を参照)。ほかの場所で書き込むと、履歴との食い違いが起きうる。
"""

import ast
from pathlib import Path

DERIVED = {
    "participation_counts",
    "miss_counts",
    "pair_counts",
}
WRITERS = {"_store_tally"}
# セッションを表す変数名 (logic などの関数は引数 session で受け取る)
SESSION_NAMES = {"session", "state"}
SOURCES = sorted((Path(__file__).parent.parent / "roulette").glob("*.py"))


def writes_outside_writers(path: Path) -> list[str]:
    found = []

    def visit(node: ast.AST, function: str | None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for target in targets:
            # session.<名前> = ... と session.<名前>[...] = ... の両方を見る
            while isinstance(target, ast.Subscript):
                target = target.value
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in SESSION_NAMES
                and target.attr in DERIVED
                and function not in WRITERS
            ):
                found.append(f"{path.name}:{node.lineno} {function} writes {target.value.id}.{target.attr}")
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(ast.parse(path.read_text(encoding="utf-8")), None)
    return found


def test_values_derived_from_history_are_written_only_by_the_two_writers():
    found = [w for path in SOURCES for w in writes_outside_writers(path)]
    assert found == []
