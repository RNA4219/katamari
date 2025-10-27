# ADR-0004: M1 メトリクスと保持率基盤を整備する

## Context
- 背景: M1 マイルストーンでは圧縮後の意味損失や保持率を可視化し、初期運用の健全性を測定する必要がある。
- 課題: 現状の Chainlit には `/metrics` や `/healthz` が存在せず、可観測性と SLA 担保が困難。
- 参考資料: [`docs/Katamari_Requirements_v3_ja.md`](../Katamari_Requirements_v3_ja.md) の FR-07, AC-04、`docs/katamari_wbs.csv` の M1-1〜M1-4。

## Decision
- 方針: prethought スコアと保持率算出を実装し、API (`/metrics`, `/healthz`) と Header 認証で保護されたメトリクス出力を整備する。`semantic_retention` は Trim 後の埋め込み類似度から算出した実測値を露出し、欠損は Prometheus では `NaN` として、CLI/JSON (`scripts/perf/collect_metrics.py`) では `null` として保持する。`scripts/perf/collect_metrics.py` は HTTP と Chainlit ログを突き合わせ、保持率を `-1.0〜1.0` レンジで保存しつつ、欠損は `null` に統一する。Header 認証は M1 で導入済みであり、残タスクは prethought 指標の公開と OAuth 拡張に集約されるため、公開済みメトリクスは当面 `compress_ratio` と実測の `semantic_retention` が中心になる。
- 採用理由: 初期ユーザーに対する品質保証と運用判断をメトリクスベースで行うため。AC-04 が要求するヘッダー認証も M1 で完了させる。
- 適用範囲: `src/core_ext/` の計測ロジックと `src/app.py` のエンドポイント追加、Chainlit UI での保持率表示までを対象とする。

## Consequences
- 影響範囲: Prometheus 収集基盤と UI/ログが保持率・prethought 指標を参照できるようになり、Ops/PM が共通の数値で議論できる。Header 認証は `/metrics` `/healthz` に既に適用済みのため、運用は prethought 指標の公開と OAuth 拡張を待ちながら `compress_ratio` と実測の `semantic_retention` を軸に進める。CLI は `null` を欠損値として返し、Prometheus ダッシュボードは `NaN` を欠損扱いで取り込む。
- 利点: `/healthz` による可観測性向上で運用オンコールのレスポンスが安定する。Header 認証で非公開メトリクスの漏洩リスクを抑制。
- リスク/フォローアップ: メトリクス追加が Chainlit 本体に影響するため、アップストリーム差分管理を ADR-0001 の subtree 運用と整合させる。解析基盤では JSON `null` を欠損扱いで受容し、保持率の負値を異常値ではなくモデル信号として扱えるようスキーマとダッシュボードの閾値設定を更新する前提とする。

## Status
- ステータス: 承認済み
- 最終更新日: 2025-02-14
- 補足理由: 2025-10-21 時点で prethought 指標と OAuth 拡張が未完了である状況を明記し、Header 認証導入済みの現行状態との差分追跡を容易にする。

## DoD
- [x] `/metrics` が 200 OK を返し、`compress_ratio` / `semantic_retention` が Prometheus 形式で出力される統合テストが存在する（prethought 指標の出力は今後の導入に合わせて追記する）。
- [x] `semantic_retention` が `-1.0〜1.0` レンジを維持し、欠損時に JSON `null` を返すことを検証するテストとダッシュボード設定が揃っている。
- [x] `/healthz` の readiness/liveness 判定に応じて 200/503 を返すユニットテストが整備されている。
- [x] Header 認証の有効トークン/無効トークンで 200/401 を確認するテストが CI に追加されている（`tests/app/test_metrics_healthz.py`）。
- [ ] prethought・保持率算出ロジックの単体テストが AC-04 の閾値要件を検証している。未達成（実装後にチェック）。
- [ ] `CHAINLIT_AUTH_SECRET` の設定追加がドキュメントとサンプル設定に反映されている。
