from export_openapi import OPENAPI_PATH, render


def test_committed_openapi_matches_the_api():
    # 失敗したら `uv run python export_openapi.py` で書き出し直し、フロントの型も生成し直す
    assert OPENAPI_PATH.read_text(encoding="utf-8") == render()
