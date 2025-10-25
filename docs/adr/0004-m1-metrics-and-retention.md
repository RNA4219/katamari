# ADR-0004: M1 メトリクスと保持率基盤を整備する

## Context
- 背景: M1 マイルストーンでは圧縮後の意味損失や保持率を可視化し、初期運用の健全性を測定する必要がある。
- 課題: 現状の Chainlit には `/metrics` や `/healthz` が存在せず、可観測性と SLA 担保が困難。
- 参考資料: [`docs/Katamari_Requirements_v3_ja.md`](../Katamari_Requirements_v3_ja.md) の FR-07, AC-04、`docs/katamari_wbs.csv` の M1-1〜M1-4。

## Decision
- 方針: prethought スコアと保持率算出を実装し、API (`/metrics`, `/healthz`) と Header 認証で保護されたメトリクス出力を整備する。埋め込み類似度による `semantic_retention` は本番環境で算出・収集されており、`compress_ratio` と合わせて Prometheus 形式で露出する。Header 認証と prethought 指標のエクスポートは未導入のため、運用ではネットワーク制御とログで補完している。
- 採用理由: 初期ユーザーに対する品質保証と運用判断をメトリクスベースで行うため。AC-04 が要求するヘッダー認証はフォローアップとして残し、M1 では観測値の可視化を優先する。
- 適用範囲: `src/core_ext/` の計測ロジックと `src/app.py` のエンドポイント追加、Chainlit UI での保持率表示検討までを対象とする。

## Consequences
- 影響範囲: Prometheus 収集基盤が埋め込み由来の `semantic_retention` と `compress_ratio` を直接参照でき、Ops/PM が共通の数値で議論できる。prethought 指標は未集計のためログ観測で補完している。Header 認証が未導入のため、当面はネットワークレベルの遮断とアクセス監査でリスクを抑制する。
- 利点: `/healthz` による可観測性向上で運用オンコールのレスポンスが安定する。実測保持率を導入したことで圧縮アルゴリズム改善の効果検証が即座に可能になった。
- リスク/フォローアップ: メトリクス追加が Chainlit 本体に影響するため、アップストリーム差分管理を ADR-0001 の subtree 運用と整合させる。Header 認証導入と prethought 指標露出をフォローアップタスクとして追跡する。

## Status
- ステータス: 承認済み
- 最終更新日: 2025-10-24
- 補足理由: 埋め込み保持率の本番収集が開始された。Header 認証と prethought 指標は未導入のため、追跡タスクとリスクを明示する。

## DoD
- [x] `/metrics` が 200 OK を返し、`compress_ratio` と埋め込み由来の `semantic_retention` を Prometheus 形式で出力する統合テストが存在する。
- [ ] `/healthz` の readiness/liveness 判定に応じて 200/503 を返すユニットテストが整備されている。
- [ ] Header 認証の有効トークン/無効トークンで 200/401 を確認するテストが CI に追加されている。未達成（実装後にチェック）。
- [ ] prethought・保持率算出ロジックの単体テストが AC-04 の閾値要件を検証している。未達成（実装後にチェック）。
- [ ] `CHAINLIT_AUTH_SECRET` の設定追加がドキュメントとサンプル設定に反映されている。
