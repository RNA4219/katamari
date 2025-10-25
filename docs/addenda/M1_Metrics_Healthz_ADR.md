# ADR M1: Health & Metrics Endpoints

- **ステータス**: 承認 (2025-10-19)
- **背景**: M1 マイルストーンで Chainlit ベースのアプリに可観測性を導入する必要がある。
- **決定**:
  - FastAPI ルーターに `GET /healthz` を追加し、200/`{"status":"ok"}` を返却する。
  - `MetricsRegistry` で `compress_ratio` / `semantic_retention` を Gauge として保持し、`GET /metrics` から Prometheus Text Format で露出する。`semantic_retention` は埋め込み類似度による実測値を採用し、欠損時は `NaN` を返却する。
- **影響**:
  - Chainlit ルートに副作用なくサブマウントでき、CI テスト (`pytest`) で監視エンドポイントが検証される。
  - Header 認証が未導入のため、メトリクス公開範囲はネットワークフィルタと監査ログで補完する。

## 履歴
- 2025-10-24: 埋め込み由来の `semantic_retention` を本番採用し、欠損時の `NaN` 送出と Header 認証未導入リスクを追記した。
