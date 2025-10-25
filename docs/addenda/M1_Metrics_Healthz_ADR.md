# ADR M1: Health & Metrics Endpoints

- **ステータス**: 承認 (2025-10-19)
- **背景**: M1 マイルストーンで Chainlit ベースのアプリに可観測性を導入する必要がある。
- **決定**:
  - FastAPI ルーターに `GET /healthz` を追加し、200/`{"status":"ok"}` を返却する。
  - `MetricsRegistry` で `compress_ratio` / `semantic_retention` を Gauge として保持し、`GET /metrics` から Prometheus Text Format で露出する（`semantic_retention` は暫定のダミー値を返却し、精度改善ロードマップに沿って差し替える計画）。`scripts/perf/collect_metrics.py` はこれらの値を収集し、保持率が欠損した場合は JSON `null` を出力、-1.0〜1.0 のレンジを守る負値も保持してダッシュボードへ渡す。
- **影響**:
  - Chainlit ルートに副作用なくサブマウントでき、CI テスト (`pytest`) で監視エンドポイントが検証される。
- `/metrics` は暫定で `semantic_retention` にダミー値を出力し、埋め込み導入後に算出精度を検証・更新するロードマップを維持できる。

## 履歴
- 2025-10-21: `/metrics` の `semantic_retention` がダミー値を返す現状と精度向上計画を明記し、関連ドキュメントと整合させた。
