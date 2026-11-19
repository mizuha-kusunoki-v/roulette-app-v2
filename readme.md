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
- スロット演出アニメーション（5秒）
- OBS 用ビュワーページ（`/viewer/result`）
- WebSocket によるリアルタイム状態同期

---

## フォルダ構成

```
roulette-app_new/
├── vtuber-roulette/         # フロントエンド (React + Vite)
│   ├── index.html           # エントリー HTML
│   ├── vite.config.ts       # Vite 設定 (開発サーバーは port 3000)
│   └── src/
│       ├── AdminApp.tsx     # 管理画面
│       ├── App.tsx          # OBS ビュワー統合
│       ├── components/      # UI コンポーネント群
│       ├── api/client.ts    # バックエンド API クライアント
│       └── types.ts         # 型定義
│
├── vtuber-roulette-api/     # バックエンド (FastAPI)
│   ├── main.py              # アプリエントリーポイント
│   ├── draw_config.py       # 自動強制抽選のパラメータ設定
│   ├── pyproject.toml       # 依存定義 (uv)
│   ├── uv.lock              # 依存のバージョン固定 (uv が生成)
│   └── roulette/            # 抽選ルーレットモジュール
│       ├── logic.py         # 抽選ロジック
│       ├── models.py        # データモデル
│       └── router.py        # API ルーター
│
├── setup.bat                # 初回セットアップスクリプト (Windows)
└── start.bat                # ワンクリック起動スクリプト (Windows)
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

`vtuber-roulette-api/draw_config.py` で自動強制抽選の挙動を調整できます。

```python
# 参加回数が中央値より AUTO_FORCE_MEDIAN_GAP 以上少ないと自動強制対象
AUTO_FORCE_MEDIAN_GAP = 2

# 1回の抽選で自動強制する最大人数（0 = 無制限）
AUTO_FORCE_MAX_PER_DRAW = 2
```

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
