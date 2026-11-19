# VTuber ルーレットアプリ

配信用のチーム対戦メンバー抽選ツールです。  
React (Vite) フロントエンド + FastAPI バックエンドの構成で動作します。

---

## 機能概要

### ルーレット抽選
| モード | 人数 | 内容 |
|---|---|---|
| `standard_3` | 1v2 | 主催1人 + 抽選1人 vs 抽選2人 |
| `standard_4` | 2v2 | 抽選2人 vs 抽選2人 |
| `hosts_vs_duo` | 2v2 | 主催2人 vs 抽選2人 |
| `hosts_split_pairs` | 2v2 | 主催2人がそれぞれ抽選1人とペア |

### 抽選制御
- **手動強制抽選**：特定の参加者を必ず選出（チームA/B固定も可能）
- **除外設定**：特定プレイヤーを一時的に抽選対象から外す
- **前回参加者の休み**：前回出た人は、ほかの人で枠が埋まるなら選出しない
- **最長の未選出者の確定**：一番長く連続で外れている人のうち 1 人は必ず選出（同じ回数の人が複数いれば、その中からランダム）
- **重み付き抽選**：残りの枠は、連続で外れた回数が多いほど出やすく、同じ対戦組み合わせは出た回数に応じて出にくくなる重みで抽選
- **自動強制抽選**（ON のとき）：参加回数が中央値より少ないほど出やすくする（必ず選ぶわけではない）

### その他
- 抽選履歴の一覧表示・削除
- スロット演出アニメーション（5秒）
- OBS 用ビュワーページ（`/viewer/result`）
- WebSocket によるリアルタイム状態同期

---

## フォルダ構成

```
roulette-app-v2/
├── vtuber-roulette/             # フロントエンド (React + Vite)
│   ├── index.html               # エントリー HTML
│   ├── vite.config.ts           # Vite 設定 (開発サーバーは port 3000)
│   └── src/
│       ├── AdminApp.tsx         # 管理画面
│       ├── App.tsx              # ルーティング (管理画面 / OBS ビュワー)
│       ├── components/          # 管理画面の部品
│       ├── viewer/              # OBS ビュワー (スロット演出と結果表示)
│       ├── utils/               # 表示用の小さな関数
│       ├── api/
│       │   ├── client.ts        # 操作 API の呼び出し
│       │   ├── endpoint.ts      # 接続先 (VITE_API_BASE)
│       │   └── schema.ts        # OpenAPI から生成した型 (手で編集しない)
│       └── types.ts             # 生成した型に名前を付けたもの
│
├── vtuber-roulette-api/         # バックエンド (FastAPI)
│   ├── main.py                  # アプリの組み立て (composition root: create_app)
│   ├── draw_config.py           # 自動強制抽選のパラメータ設定
│   ├── export_openapi.py        # openapi.json を書き出す
│   ├── openapi.json             # フロントとの契約 (書き出してコミットする)
│   ├── pyproject.toml           # 依存定義 (uv)
│   ├── uv.lock                  # 依存のバージョン固定 (uv が生成)
│   ├── roulette/
│   │   ├── models.py            # 内部の状態 (参加者・主催・履歴・集計) と抽選で使う値
│   │   ├── logic.py             # 抽選のルールと操作 (セッションを引数で受け取る)
│   │   ├── protocol.py          # フロントとのプロトコル (送る状態・受け取る操作の形)
│   │   ├── snapshot.py          # 内部の状態からプロトコルの状態を組み立てる
│   │   ├── messages.py          # 利用者に見せる文言
│   │   ├── sessions.py          # セッションを作る (SessionFactory)
│   │   ├── changes.py           # 状態の変化を WebSocket に知らせる
│   │   └── router.py            # API と WebSocket のエンドポイント
│   └── tests/                   # uv run pytest (builders.py と harness.py だけが内部の状態の形を知る)
│
├── setup.bat                    # 初回セットアップスクリプト (Windows)
└── start.bat                    # ワンクリック起動スクリプト (Windows)
```

---

## セットアップ

### 必要なもの
- [uv](https://docs.astral.sh/uv/)（`winget install astral-sh.uv`）
  - Python 3.11 は uv が自動で用意するので、別途インストールは不要
- Node.js 20.19+ または 22.12+（Vite 8 の要件）

### Windows（推奨）

ルートの `setup.bat` をダブルクリックすると、バックエンドとフロントエンドの依存がまとめて入ります。

### 手動セットアップ

**バックエンド：**
```bash
cd vtuber-roulette-api
uv sync --locked
```

**フロントエンド：**
```bash
cd vtuber-roulette
npm ci
```

### 依存の追加・更新（バックエンド）

```bash
cd vtuber-roulette-api
uv add <パッケージ名>   # 追加
uv lock --upgrade       # 全依存を最新版に更新
```

`pyproject.toml` と `uv.lock` を両方コミットしてください。

---

## 起動方法

### Windows（推奨）

ルートの `start.bat` をダブルクリック、または：

```bat
start.bat
```

バックエンド（port 8000）とフロントエンド（port 3000）が同時に起動します。

### 手動起動

**バックエンド：**
```bash
cd vtuber-roulette-api
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**フロントエンド：**
```bash
cd vtuber-roulette
npm start
```

---

## アクセス先

| URL | 用途 |
|---|---|
| `http://localhost:3000/` | 管理画面（配信者操作用） |
| `http://localhost:3000/viewer/result` | OBS ブラウザソース用ビュワー |
| `http://localhost:8000/docs` | API ドキュメント (Swagger UI) |

---

## 抽選パラメータ調整

`vtuber-roulette-api/draw_config.py` で抽選の重みを調整できます。組み合わせ（誰が出るか + チーム分け）の出やすさは、
「選ばれる人それぞれの exp(点数) の積 × exp(-PAIR_PENALTY × その対戦組み合わせが過去に出た回数)」に比例します。

```python
# 点数 = WAIT_WEIGHT × 連続で外れた回数 + DEFICIT_WEIGHT × 中央値より少ない参加回数（自動強制 ON のとき）
WAIT_WEIGHT = 3.0
DEFICIT_WEIGHT = 1.0
PAIR_PENALTY = 1.0
```

値を大きくするほど公平になりますが、次に誰が出るか予想しやすくなります。0 にするとその要素を見なくなります。
`AUTO_FORCE_MEDIAN_GAP` と `AUTO_FORCE_MAX_PER_DRAW` は、管理画面の「自動強制対象」の表示と、選ばれた理由の表示だけに使います。

---

## API 概要

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/session` | セッションの状態（プロトコル）を取得 |
| WS | `/ws/session` | セッションの状態を、接続時と変化時に送る |
| PUT | `/participants` | 参加者リストを置き換える（CSV 取り込み） |
| POST | `/participants/add` | 参加者を1人追加 |
| POST | `/participants/remove` | 参加者を1人削除 |
| POST | `/participants/forced` | 手動強制の設定・チーム指定・解除 |
| POST | `/participants/excluded` | 除外の切り替え |
| PUT | `/organizers` | 主催モードと主催（候補と選択）を保存 |
| PUT | `/settings` | 抽選設定（救済閾値・自動強制）を保存 |
| POST | `/draw` | 抽選を実行 |
| POST | `/presentation_complete` | スロット演出完了を通知 |
| DELETE | `/history/{round_id}` | 指定した抽選履歴を削除 |
| POST | `/reset` | 全状態をリセット |

参加者の名前は URL に入れず、本文（JSON）で送ります。名前に「/」が入るとパスとして解釈されるためです。

---

## フロントとのプロトコル

バックエンドは内部の状態をそのまま送らず、`vtuber-roulette-api/roulette/protocol.py` で決めた形（`SessionState`）にして送ります。
抽選できるか・優先対象かといった、抽選のルールから導く値もバックエンドが計算して送ります。フロントでは計算し直しません。

API の形は `vtuber-roulette-api/openapi.json` に書き出してコミットし、フロントの型（`vtuber-roulette/src/api/schema.ts`）はそこから生成します。
API やプロトコルのモデルを変えたときは、両方を更新してコミットしてください。

```bash
cd vtuber-roulette-api
uv run python export_openapi.py   # openapi.json を書き出す（古いままだと uv run pytest が失敗する）

cd ../vtuber-roulette
npm run gen:api                   # schema.ts を生成する（npm run build でも実行される）
```
