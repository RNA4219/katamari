# 付録D: Trim（圧縮）設計詳細
**Status: 2025-10-19 JST**

## D-1. 戦略オプション
1) **Sliding Window（M0）**: 最後のNターン保持（計算量O(n)）。実装容易、語彙流失に弱い。  
2) **Semantic Clustering（M1）**: 意味クラスタごと要約→要点を残す（埋め込み＋k-means）。  
3) **Memory/RAG Hybrid（M2.5）**: 永続メモリ（Postgres/ベクトルDB）から関連要点のみ再構成。

## D-2. 保持率推定（M1）
- `semantic_retention = cosine(emb(before), emb(after))`
- 目標: **≥0.85**（ユースケース依存で調整）
- Trim 実行時に埋め込みを算出し、`/metrics` に `-1.0〜1.0` のレンジで実測値を送出する。欠損や埋め込み取得失敗時は `null`（JSON）で記録し、ダッシュボード側も欠損扱いに揃える。

### チェックリスト（保持率観測）
- [ ] Trim 後の埋め込みが正常に計算され、`semantic_retention` が `-1.0〜1.0` の範囲で `/metrics` に出力される。
- [ ] 埋め込み失敗・欠損時に `semantic_retention` が `null` として記録され、`scripts/perf/collect_metrics.py` が欠損を保持する。
- [ ] ダッシュボード／ログ解析は `null` を欠損値として扱い、負値を異常値ではなく実測として保存する設定になっている。

## D-3. 制御パラメタ
- `target_tokens`（UIのスライダ 1k–8k）
- `min_turns`（最低保持ターン数。現行実装では未対応／将来導入予定）
- `priority_roles`（system/user優先。現行実装では未対応／将来導入予定）

## D-4. フィードバック
- UIには `compress_ratio` を表示し、保持率は `/metrics`・Guardrails ログで実測値として共有する（UI 表示は意思決定待ち）。
- ダッシュボード連携時は保持率を `-1.0〜1.0` のレンジでグラフ化し、`null` は欠損処理とする運用を徹底する。

### TODO / Follow-up
- [ ] UI に保持率を提示する場合は、`null` や負値の扱いと説明テキストを定義して UX を検証する。
