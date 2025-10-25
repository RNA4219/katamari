# ADR M1: Health & Metrics Endpoints

- **ステータス**: 承認 (2025-10-19)
- **背景**: M1 マイルストーンで Chainlit ベースのアプリに可観測性を導入する必要がある。
- **決定**:
  - FastAPI ルーターに `GET /healthz` を追加し、200/`{"status":"ok"}` を返却する。
  - `MetricsRegistry` で `compress_ratio` / `semantic_retention` を Gauge として保持し、`GET /metrics` から Prometheus Text Format で露出する。`semantic_retention` は Trim 後の埋め込み類似度から算出した実測値を返却し、欠損時は JSON `null` を維持する。`scripts/perf/collect_metrics.py` はこれらの値を収集し、保持率を `-1.0〜1.0` レンジで保存しつつ、負値は実測として扱う。
- **影響**:
  - Chainlit ルートに副作用なくサブマウントでき、CI テスト (`pytest`) で監視エンドポイントが検証される。
- `/metrics` は `semantic_retention` の実測値を返却し、`null` は欠損・負値は実測シグナルとしてダッシュボードに引き継ぐ。

## 履歴
- 2025-10-21: `/metrics` の `semantic_retention` がダミー値を返す現状と精度向上計画を明記し、関連ドキュメントと整合させた。
- 2025-10-23: `semantic_retention` の実測計測・`null` フォールバック・`-1.0〜1.0` レンジ運用を反映。
