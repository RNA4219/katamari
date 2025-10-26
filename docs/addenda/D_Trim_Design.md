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
- [x] Trim 後の埋め込みが正常に計算され、`semantic_retention` が `-1.0〜1.0` の範囲で `/metrics` に出力される。（`scripts/perf/collect_metrics.py` の `_is_valid_metric` が上下限を検証し、異常値は採用しない）
- [x] 埋め込み失敗・欠損時に `semantic_retention` が `null` として記録され、`scripts/perf/collect_metrics.py` が欠損を保持する。（`SEMANTIC_RETENTION_FALLBACK` を `None` に固定し、HTTP/ログ両方が欠損でも `null` を明示出力）
- [x] ダッシュボード／ログ解析は `null` を欠損値として扱い、負値を異常値ではなく実測として保存する設定になっている。（CLI は負値をそのまま保持しつつ `null` を欠損として書き出すため、既存ダッシュボード設定と整合）

現行実装（`scripts/perf/collect_metrics.py` と `/metrics` ハンドラの組合せ）が上記 3 項目を満たしており、保持率計測と欠損処理は運用中のパイプラインで検証済み。最新の Trim リリースでも追加対応は不要であることを確認した。

## D-3. 制御パラメタ
- `target_tokens`（UIのスライダ 1k–8k）
- `min_turns`（最低保持ターン数。現行実装で対応済みで、直近ターンから逆順に走査して最低ターン数ぶんの対話ペアを確保した上でトリムする。`src/core_ext/context_trimmer.trim_messages` は `_group_conversation_turns` でターン単位に分割し、`min_turns` 指定回数ぶんを保持した状態で予算を超える場合のみさらに古いターンを削除する）
- `priority_roles`（system/user優先。現行実装では未対応／将来導入予定）

## D-4. フィードバック
- UIには `compress_ratio` を表示し、保持率は `/metrics`・Guardrails ログで実測値として共有する（UI 表示は意思決定待ち）。
- ダッシュボード連携時は保持率を `-1.0〜1.0` のレンジでグラフ化し、`null` は欠損処理とする運用を徹底する。

### TODO / Follow-up
- [ ] UI に保持率を提示する場合は、`null` や負値の扱いと説明テキストを定義して UX を検証する。
