# Katamari (Chainlit Fork) – 要件&仕様パック

<!-- LLM-BOOTSTRAP v1 -->
読む順番:
1. docs/birdseye/index.json  …… ノード一覧・隣接関係（軽量）
2. docs/birdseye/caps/<path>.json …… 必要ノードだけ point read（個別カプセル）
3. docs/ROADMAP_AND_SPECS.md …… Birdseye 導線と仕様ハブを照合
4. docs/birdseye/README.md …… Birdseye 整備予定ドキュメント

フォーカス手順:
- 直近変更ファイル±2hopのノードIDを index.json から取得
- 対応する caps/*.json のみ読み込み

補足リンク:
- docs/birdseye/hot.json …… Birdseye ホットスポット一覧
- Guardrails ドキュメント …… [`BLUEPRINT.md`](BLUEPRINT.md) / [`RUNBOOK.md`](RUNBOOK.md) / [`EVALUATION.md`](EVALUATION.md) / [`CHECKLISTS.md`](CHECKLISTS.md)（個人+AI運用向けガードレール）
<!-- /LLM-BOOTSTRAP -->

## 同梱物
- 要件: [`docs/Katamari_Requirements_v3_ja.md`](docs/Katamari_Requirements_v3_ja.md)
- 機能仕様: [`docs/Katamari_Functional_Spec_v1_ja.md`](docs/Katamari_Functional_Spec_v1_ja.md)
- 技術仕様: [`docs/Katamari_Technical_Spec_v1_ja.md`](docs/Katamari_Technical_Spec_v1_ja.md)
- ロードマップ & 仕様索引: [`docs/ROADMAP_AND_SPECS.md`](docs/ROADMAP_AND_SPECS.md)
- OpenAPI: [`docs/openapi/katamari_openapi.yaml`](docs/openapi/katamari_openapi.yaml)
- 設定: [`config/model_registry.json`](config/model_registry.json), [`config/env.example`](config/env.example)
- フォーク運用: [`docs/UPSTREAM.md`](docs/UPSTREAM.md), [`docs/FORK_NOTES.md`](docs/FORK_NOTES.md)
- ADR: [`docs/adr/README.md`](docs/adr/README.md)
- Day8 HUB / Guardrails / Blueprint 群（導線まとめ: [`docs/ROADMAP_AND_SPECS.md#day8-sequence`](docs/ROADMAP_AND_SPECS.md#day8-sequence)）: `third_party/Day8/workflow-cookbook/HUB.codex.md`, `third_party/Day8/workflow-cookbook/GUARDRAILS.md`, `third_party/Day8/workflow-cookbook/BLUEPRINT.md`

## 主要導線
- 要件・仕様ハブ: [`docs/ROADMAP_AND_SPECS.md`](docs/ROADMAP_AND_SPECS.md)
- 詳細要件: [`docs/Katamari_Requirements_v3_ja.md`](docs/Katamari_Requirements_v3_ja.md)
- 機能仕様: [`docs/Katamari_Functional_Spec_v1_ja.md`](docs/Katamari_Functional_Spec_v1_ja.md)
- 技術仕様: [`docs/Katamari_Technical_Spec_v1_ja.md`](docs/Katamari_Technical_Spec_v1_ja.md)
- OpenAPI: [`docs/openapi/katamari_openapi.yaml`](docs/openapi/katamari_openapi.yaml)
- 変更履歴: [`CHANGELOG.md`](CHANGELOG.md)（形式: Keep a Changelog / 更新フロー: [`CHANGELOG.md#運用ルール`](CHANGELOG.md#%E9%81%8B%E7%94%A8%E3%83%AB%E3%83%BC%E3%83%AB) ・ [`README.md#変更履歴の更新ルール`](README.md#%E5%A4%89%E6%9B%B4%E5%B1%A5%E6%AD%B4%E3%81%AE%E6%9B%B4%E6%96%B0%E3%83%AB%E3%83%BC%E3%83%AB)）
- タスクシード: `TASK.*.md`（完了済みタスクは [`CHANGELOG.md#unreleased`](CHANGELOG.md#unreleased) へ移し、重複を解消）
- フォーク運用: [`docs/UPSTREAM.md`](docs/UPSTREAM.md), [`docs/FORK_NOTES.md`](docs/FORK_NOTES.md)
- Day8 初回導線（HUB → Guardrails → Blueprint）: HUB（[`third_party/Day8/workflow-cookbook/HUB.codex.md`](third_party/Day8/workflow-cookbook/HUB.codex.md)）→ Guardrails（[`third_party/Day8/workflow-cookbook/GUARDRAILS.md`](third_party/Day8/workflow-cookbook/GUARDRAILS.md)）→ Blueprint 群（[`third_party/Day8/workflow-cookbook/BLUEPRINT.md`](third_party/Day8/workflow-cookbook/BLUEPRINT.md) ほか）／導線概要: [`docs/ROADMAP_AND_SPECS.md#day8-sequence`](docs/ROADMAP_AND_SPECS.md#day8-sequence)

## ローカル起動手順

### 前提

- Python 3.11 系（`python -m venv` が利用できること）
- `pip` / `GNU Make`

### Step 1: 依存インストールと初期セットアップ

1. 作業ディレクトリで仮想環境を作成し、アクティブ化する。
2. リポジトリを取得してルートディレクトリ（`katamari/`）に移動する。
3. `.env` を [`config/env.example`](config/env.example) からコピーし、後述の環境変数表を参考に値を設定する。
4. `make dev` を実行して Python 依存関係を一括でインストールする（内部的には `pip install -r requirements.txt` を呼び出す）。

```bash
python -m venv .venv
source .venv/bin/activate
git clone git@github.com:<your-org>/katamari.git
cd katamari
cp config/env.example .env
make dev
```

- GNU Make が利用できない環境では `pip install -r requirements.txt` を直接実行してもよい。
- 依存パッケージを更新する際も同じコマンド（`make dev`）を再実行する。

### Step 2: アプリのローカル起動

1. `.env` に必要な値を設定した状態で `make run` を実行する。
2. Chainlit が `http://localhost:8787` で立ち上がる。ポートを変更したい場合は `chainlit run src/app.py --host 0.0.0.0 --port <port>` を直接実行するか、`Makefile` の `run` ターゲットを調整する。
3. 停止するときは実行ターミナルで `Ctrl + C` を送る。

```bash
make run
```

## 環境変数一覧

`.env` の初期値は [`config/env.example`](config/env.example) を参照してください。サンプルとの差分を最小限に保ちながら、必要に応じて [`README_PERSONAS_THEMES.md`](README_PERSONAS_THEMES.md) も参照してください。

| 種別 | 名称 | 用途 | 設定例 | 備考 |
| ---- | ---- | ---- | ------ | ---- |
| 必須 | `OPENAI_API_KEY` | OpenAI プロバイダー利用時の API キー | `OPENAI_API_KEY=sk-...` | `.env` のみで管理し、Git には含めない |
| 任意 | `GOOGLE_GEMINI_API_KEY` | Google Gemini プロバイダー利用時の API キー | `GOOGLE_GEMINI_API_KEY=...` | Gemini API を利用する場合のみ |
| 任意 | `GEMINI_API_KEY` | 旧名称。既存デプロイ互換用 | `GEMINI_API_KEY=...` | 既存環境からの移行時に保持 |
| 任意 | `DEFAULT_PROVIDER` | 既定で使用する LLM プロバイダー識別子 | `DEFAULT_PROVIDER=openai` | 将来のマルチプロバイダー切り替え用プレースホルダー（現状未使用） |
| 任意 | `DEFAULT_MODEL` | 起動時に選択される LLM モデル ID | `DEFAULT_MODEL=gpt-5-main` | `.env` 未設定時はアプリ既定値を利用 |
| 任意 | `CHAINLIT_AUTH_SECRET` | Chainlit セッション署名用シークレット | `CHAINLIT_AUTH_SECRET=change-me` | 本番は十分な長さに変更 |
| 任意 | `PORT` | Chainlit を手動で起動するときの待ち受けポート | `PORT=8787` | `make run` は既定で 8787 を指定。必要なら `chainlit run ... --port` を利用 |
| 任意 | `LOG_LEVEL` | Chainlit ログ出力レベル | `LOG_LEVEL=info` | `debug`/`warning` などを指定可 |
| 任意 | `SEMANTIC_RETENTION_PROVIDER` | 会話保持率メトリクス算出時の埋め込みプロバイダー | `SEMANTIC_RETENTION_PROVIDER=openai` | 指定時は下記モデル設定も併用 |
| 任意 | `SEMANTIC_RETENTION_OPENAI_MODEL` | OpenAI 埋め込みモデル名 | `SEMANTIC_RETENTION_OPENAI_MODEL=text-embedding-3-large` | OpenAI プロバイダー指定時に利用 |
| 任意 | `SEMANTIC_RETENTION_GEMINI_MODEL` | Google Gemini 埋め込みモデル名 | `SEMANTIC_RETENTION_GEMINI_MODEL=text-embedding-004` | Gemini プロバイダー指定時に利用 |
| 任意 | `GOOGLE_API_KEY` | Gemini 埋め込み生成用 API キー（会話保持率用） | `GOOGLE_API_KEY=...` | `SEMANTIC_RETENTION_PROVIDER=google_gemini` 時に必要 |

> まず `.env` に必須項目を入力し、環境に合わせて任意項目を追加してください。

### `.env` 設定例

```dotenv
OPENAI_API_KEY=sk-...
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-5-main
CHAINLIT_AUTH_SECRET=change-me
PORT=8787
LOG_LEVEL=info
```

## テーマ切り替え

1. Chainlit UI 右上の **Settings → Theme** から `themes/` 配下のプリセット（`.theme.json`）を選ぶか、**Theme → Import JSON** でカスタムファイルを読み込む。
2. 追加のテーマ設計やペルソナ連携の手順は [`README_PERSONAS_THEMES.md`](README_PERSONAS_THEMES.md) を参照し、必要に応じて `public/theme.json` や `personas/` 配下の設定と同期する。

- 本パックは「katamari」の要件定義・機能仕様・技術仕様・OpenAPI・初期設定を含むドキュメント集です。
- まずは `docs/Katamari_Requirements_v3_ja.md` をご確認ください。

## Docker イメージの利用

リポジトリ同梱の `Dockerfile` は `chainlit run src/app.py` を既定コマンドとして公開しています。

```bash
# ビルド
docker build -t katamari:dev .

# 起動 (ポートは PORT 環境変数で変更可能)
docker run --rm -e PORT=8787 -p 8787:8787 katamari:dev
```

GitHub Container Registry への公開フローは [docs/addenda/H_Deploy_Guide.md](docs/addenda/H_Deploy_Guide.md) を参照してください。
## 運用エンドポイント

- `GET /healthz`: Chainlit アプリの Liveness。`{"status":"ok"}` を返却。
- `GET /metrics`: Prometheus Text Format (`compress_ratio`, `semantic_retention`) を露出。

## 変更履歴の更新ルール

1. PR で顕著な差分が出たら、必ず [`CHANGELOG.md`](CHANGELOG.md) の `[Unreleased]` に追記する。
2. 記法は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) を踏襲し、`Added`/`Changed`/`Deprecated`/`Removed`/`Fixed`/`Security` の分類に整理する（不要な分類は削除可）。
3. 各エントリの先頭に 4 桁ゼロ埋めの通番（例: `0001`）を付与し、既存の最大値から 1 ずつ繰り上げる。
4. リリース確定時は `[Unreleased]` のエントリを新しいバージョン見出しへ移し、セマンティックバージョンと日付を付けてタグ作成と同じコミットで確定する。
5. README やロードマップ、`TASK.*.md` の完了済みタスクは `[Unreleased]` の該当分類へ移し、リリース時に対応バージョンへ転記する。
6. PR を送信する直前に [`CHANGELOG.md#運用ルール`](CHANGELOG.md#%E9%81%8B%E7%94%A8%E3%83%AB%E3%83%BC%E3%83%AB) を再確認し、通番・分類・移管漏れがないかチェックする。
