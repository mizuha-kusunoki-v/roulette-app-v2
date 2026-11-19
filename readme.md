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
- **自動強制抽選**：参加回数が中央値から大きく下回るプレイヤーを優先選出
- **ミスカウント**：N回連続で外れたプレイヤーを強制抽選（閾値設定可）
- **除外設定**：特定プレイヤーを一時的に抽選対象から外す
- **重複ペア抑制**：同じ対戦組み合わせが出た回数に応じて確率的に再抽選（最大10回）

### その他
- 抽選履歴の一覧表示・削除
- スロット演出アニメーション（長さは `draw_config.py` の `PRESENTATION_DURATION_MS`。既定 5 秒）
- OBS 用ビュワーページ（`/viewer/result`）
- WebSocket によるリアルタイム状態同期（切れたら自動で繋ぎ直す）

---

## フォルダ構成

```
roulette-app-v2/
├── vtuber-roulette/             # フロントエンド (React + Vite)
│   ├── index.html               # エントリー HTML
│   ├── vite.config.ts           # Vite 設定 (開発サーバーは 127.0.0.1 の port 3000)
│   └── src/
│       ├── AdminApp.tsx         # 管理画面
│       ├── App.tsx              # ルーティング (管理画面 / OBS ビュワー)
│       ├── components/          # 管理画面の部品
│       ├── viewer/              # OBS ビュワー (スロット演出と結果表示)
│       ├── session/             # 状態の受け取り (古い状態の破棄・WebSocket の再接続) と、抽選演出の間の判定
│       ├── utils/               # 表示用の小さな関数
│       ├── api/
│       │   ├── client.ts        # 操作 API の呼び出し
│       │   ├── endpoint.ts      # 接続先 (VITE_API_BASE)
│       │   └── schema.ts        # OpenAPI から生成した型 (手で編集しない)
│       └── types.ts             # 生成した型に名前を付けたもの
│
├── vtuber-roulette-api/         # バックエンド (FastAPI)
│   ├── main.py                  # アプリの組み立て (composition root: create_app)
│   ├── draw_config.py           # 自動強制抽選・抽選演出の長さの設定
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
| `http://localhost:3000/` または `http://127.0.0.1:3000/` | 管理画面（配信者操作用） |
| `http://localhost:3000/viewer/result` または `http://127.0.0.1:3000/viewer/result` | OBS ブラウザソース用ビュワー |
| `http://localhost:8000/docs` | API ドキュメント (Swagger UI) |

---

## 抽選パラメータ調整

`vtuber-roulette-api/draw_config.py` で自動強制抽選の挙動を調整できます。

```python
# 参加回数が中央値より AUTO_FORCE_MEDIAN_GAP 以上少ないと自動強制対象
AUTO_FORCE_MEDIAN_GAP = 2

# 1回の抽選で自動強制する最大人数（0 = 無制限）
AUTO_FORCE_MAX_PER_DRAW = 2

# スロット演出の長さ（ミリ秒）。画面はこの値を状態 (presentation_duration_ms) から受け取る
PRESENTATION_DURATION_MS = 5000
```

---

## API 概要

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/session` | セッションの状態（プロトコル）を取得 |
| WS | `/ws/session` | セッションの状態を、接続時と、書き込み系の API が終わるたびに送る |
| PUT | `/participants` | 参加者リストを置き換える（CSV 取り込み） |
| POST | `/participants/add` | 参加者を1人追加 |
| POST | `/participants/remove` | 参加者を1人削除 |
| POST | `/participants/forced` | 手動強制の設定・チーム指定・解除 |
| POST | `/participants/excluded` | 除外の切り替え |
| PUT | `/organizers` | 主催モードと主催（候補と選択）を保存 |
| PUT | `/settings` | 抽選設定（救済閾値・自動強制）を保存 |
| POST | `/draw` | 抽選を実行 |
| DELETE | `/history/{round_id}` | 指定した抽選履歴を削除 |
| POST | `/reset` | 全状態をリセット |

参加者の名前は URL に入れず、本文（JSON）で送ります。名前に「/」が入るとパスとして解釈されるためです。

---

## フロントとのプロトコル

バックエンドは内部の状態をそのまま送らず、`vtuber-roulette-api/roulette/protocol.py` で決めた形（`SessionState`）にして送ります。
抽選できるか・優先対象かといった、抽選のルールから導く値もバックエンドが計算して送ります。フロントでは計算し直しません。

### 抽選の確定と演出

抽選は出した時点で確定します。バックエンドは演出の終わりを待たず、ビュワーから完了通知を受け取ることもありません（演出の途中でも、次の抽選・履歴の削除・リセットはできます）。
演出は画面側の見せ方です。

- ビュワー：読み込んで最初に受け取った状態は、そのまま（最新の結果）表示します。読み込んだあとに届いた回だけをスロット演出し、終わったらその回の結果を表示します。演出の途中でさらに新しい回が届いたら、その回で最初からやり直します。
- 管理画面：読み込んだあとに届いた回（自分の抽選も、ほかの管理画面の抽選も）を見つけたら、演出の長さの間だけ、抽選・履歴の削除・リセットの 3 つのボタンを止めます（主催設定・抽選設定・参加者の操作は止めません）。止めている間はこの画面のタイマーで数えるので、必ず元に戻ります。
- 演出の長さは `presentation_duration_ms` で、バックエンド（`draw_config.py`）だけが決めます。

### 状態の新しさ（revision）

`SessionState.revision` は `{instance_id, version}` で、`GET /session` と `/ws/session` のすべての状態に付きます。
`version` は書き込み系の API が 1 回終わるたびに増えます（失敗した書き込みでも増えます。`/ws/session` はそのたびに状態を送ります）。
画面は、同じ `instance_id` では `version` が大きい状態だけを採用し、遅れて届いた古い状態（管理画面の `GET /session` の応答が、あとの WebSocket の状態より遅れた場合など）を捨てます。
サーバーを起動し直すと `version` は 0 に戻りますが、`instance_id` が起動ごとに変わるので、`instance_id` が違うときは比べずに届いた状態を採用します。

### 接続の復帰

`/ws/session` が切れたら（サーバーの再起動、スリープ、通信の途切れ）、管理画面とビュワーは 1 秒から最大 10 秒まで間隔を空けて繋ぎ直し、繋がったら `GET /session` で状態を読み直します。管理画面は、最初に繋がるまでと切れている間、画面の上にその旨を表示します（ビュワーは配信に映るので表示しません）。

### 契約

API の形は `vtuber-roulette-api/openapi.json` に書き出してコミットし、フロントの型（`vtuber-roulette/src/api/schema.ts`）はそこから生成します。
API やプロトコルのモデルを変えたときは、両方を更新してコミットしてください。

```bash
cd vtuber-roulette-api
uv run python export_openapi.py   # openapi.json を書き出す（古いままだと uv run pytest が失敗する）

cd ../vtuber-roulette
npm run gen:api                   # schema.ts を生成する（npm run build でも実行される）
```
