# 付録D: Trim（圧縮）設計詳細
**Status: 2025-10-19 JST**

## D-1. 戦略オプション
1) **Sliding Window（M0）**: 最後のNターン保持（計算量O(n)）。実装容易、語彙流失に弱い。  
2) **Semantic Clustering（M1）**: 意味クラスタごと要約→要点を残す（埋め込み＋k-means）。  
3) **Memory/RAG Hybrid（M2.5）**: 永続メモリ（Postgres/ベクトルDB）から関連要点のみ再構成。

## D-2. 保持率推定（M1）
- `semantic_retention = cosine(emb(before), emb(after))`
- 目標: **≥0.85**（ユースケース依存で調整）
- 本番では埋め込み類似度を Chainlit セッションごとに算出し、`/metrics` へ `NaN` 許容でエクスポートする。UI 表示は未導入のため、運用ではダッシュボードで監視する。

## D-3. 制御パラメタ
- `target_tokens`（UIのスライダ 1k–8k）
- `min_turns`（最低保持ターン数。現行実装では未対応／将来導入予定）
- `priority_roles`（system/user優先。現行実装では未対応／将来導入予定）

## D-4. フィードバック
- UIに `compress_ratio` を表示し、`semantic_retention`（M1）は UI コンポーネント追加とアクセス制御導入後に公開する。
- 現在は Prometheus で保持率を可視化しており、Header 認証未導入のため VPN/Firewall で公開範囲を制限している。

### TODO / Follow-up
- [ ] `semantic_retention` を UI 上に表示し、Header 認証導入後にロールベース表示制御を適用する（追跡: ROADMAP `semantic_retention` タスク）。
- [ ] `/metrics` へのアクセス制御として Header 認証を実装し、DoD の 200/401 テストを追加する。
