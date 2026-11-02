# VTuber ルーレットアプリ

配信用のチーム対戦メンバー抽選ツールです。  
React フロントエンド + FastAPI バックエンドの構成で動作します。

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
- 縛りルーレット（対戦時の縛りをランダム抽選）
- スロット演出アニメーション（5秒）
- OBS 用ビュワーページ（`/viewer/result`）
- WebSocket によるリアルタイム状態同期

---

## フォルダ構成

```
roulette-app_new/
├── vtuber-roulette/         # フロントエンド (React)
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
│   ├── roulette/            # 抽選ルーレットモジュール
│   │   ├── logic.py         # 抽選ロジック
│   │   ├── models.py        # データモデル
│   │   └── router.py        # API ルーター
│   └── restriction/         # 縛りルーレットモジュール
│
└── start.bat                # ワンクリック起動スクリプト (Windows)
```

---

## セットアップ

### 必要なもの
- Python 3.11+
- Node.js 18+

### バックエンド

```bash
cd vtuber-roulette-api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### フロントエンド

```bash
cd vtuber-roulette
npm install
```

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
.venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8000 --reload
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
| GET | `/state` | 現在の状態を取得 |
| POST | `/participants` | 参加者リストを更新 |
| POST | `/organizer_config` | 主催設定を更新 |
| POST | `/forced_players` | 手動強制プレイヤーを設定 |
| POST | `/excluded_players` | 除外プレイヤーを設定 |
| POST | `/draw_settings` | 抽選設定（ミス閾値等）を変更 |
| POST | `/draw` | 抽選を実行 |
| POST | `/presentation_complete` | スロット演出完了を通知 |
| DELETE | `/history/{round_id}` | 指定した抽選履歴を削除 |
| POST | `/reset` | 全状態をリセット |
| WS | `/ws` | WebSocket リアルタイム同期 |
