# Katamari 機能仕様書 v1
**Status: 2025-10-19 JST / Initial**

## 1. 画面仕様（Chainlit UI）
- **チャット領域**：ユーザー/アシスタントメッセージ、Stepタイムライン（draft→critique→final）
- **Settings**（右上）項目：
  - `model`（セレクト）：`gpt-5-*`, `gemini-2.5-*`
  - `chain`（single/reflect）
  - `trim_tokens`（1k–8k, step=256）
  - `persona_yaml`（複数行）
  - `show_debug`（bool）
- **キーバインド**：Enter送信 / Shift+Enter改行（Chainlit標準）

## 2. ユースケース詳細
### UC-01 チャット（single）
1. 入力 → Settingsを読み出し → Persona→Trim 前処理 → 推論要求（SSE）
2. 逐次トークン表示（Message or Step）
3. 最後の応答を履歴に格納

### UC-02 Reflectチェーン
1. 入力 → `["draft","critique","final"]` を順次実行
2. 各Stepの入出力をSSE表示、最後に最終応答をMessageへ複製

### UC-03 Persona適用
- Settings更新イベントでYAML→Systemにコンパイルし、セッション先頭に反映（禁則ログは別Message）

### UC-04 Trim
- 目標トークンに収まるよう「最後Nターン保持」→圧縮率をMessage表示（保持率表示は未実装・計画中）

### UC-05 進化（M2）
- 複数プロンプト候補を生成→BERTScore→ROUGE→ルールで評価→上位選抜→次世代生成 ※M2予定・現状未実装。

## 3. エラー/例外
- SSE切断時：指数バックオフ（1,2,4s）で最大3回再接続（※2025-10-22 現在未実装。対応計画は今後起票予定の Task Seed「SSE自動再接続実装」で管理する）
- Persona YAMLパース失敗：既定Systemにフォールバックし、issuesを通知
- モデル未設定：`gpt-5-main` にフォールバック

## 4. 権限/認証
- M1：Header Auth（`Authorization: Bearer <token>`）
- M1.5：OAuth（Chainlit設定に準拠）
- **注記（2025-10-19 現在）**：Header Auth/OAuth は未実装であり、現行リリースは Chainlit 既定の無認証挙動を採用している。導入計画は [`TASK.2025-10-19-0002.md`](../TASK.2025-10-19-0002.md) を参照。

## 5. ログ/メトリクス
- ログ：`req_id, user_id?, model, chain_id, token_in/out, latency_ms, compress_ratio`
  - **注記（2025-10-22 更新）**：`katamari.request` ロガーから JSON 形式で構造化ログ（`req_id`/`model`/`token_in`/`token_out`/`compress_ratio`/`step_latency_ms`/`retryable`）を出力する。詳細手順は `RUNBOOK.md` を参照。
- メトリクス（現行 `/metrics`）：`compress_ratio`, `semantic_retention`
  - `semantic_retention` は Trim 後の埋め込みから算出した実測値であり、欠損時は `/metrics` では `NaN`、CLI/JSON (`scripts/perf/collect_metrics.py`) では `null` を返却する。
- メトリクス（拡張計画中）：`requests_total`, `latency_ms_p95`, `sse_first_token_ms`, `trim_compress_ratio`
