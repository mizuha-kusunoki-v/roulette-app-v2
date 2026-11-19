"""API の OpenAPI スキーマを openapi.json に書き出す。

openapi.json はフロントとの契約 (プロトコル) で、フロントの型はここから生成する。
API やプロトコルのモデルを変えたら、これを実行して openapi.json もコミットする:

    uv run python export_openapi.py
"""

import json
from pathlib import Path

from main import app

OPENAPI_PATH = Path(__file__).with_name("openapi.json")


def render() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    OPENAPI_PATH.write_text(render(), encoding="utf-8", newline="\n")
    print(f"wrote {OPENAPI_PATH}")
