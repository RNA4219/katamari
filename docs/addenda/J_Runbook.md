# 付録J: 障害時復旧（Runbook）
**Status: 2025-10-19 JST**

1. **SSEが途切れる**: リバースプロキシのバッファ設定確認（HTTP/2、flush、timeout）。
2. **初回トークン遅延**: 近接リージョン・*-miniへ切替、温度低下、Keep-Alive確認。
3. **OAuth失敗**: OAuth は未実装のため現状は想定外（Header Auth の再試行のみ）。導入計画は [`TASK.2025-10-19-0002.md`](../tasks/TASK.2025-10-19-0002.md) を参照し、完了後にRunbookを更新する。
4. **保持率低下**: Semantic 戦略は未提供。`trim_tokens` の再調整や要約プロンプトの改善で圧縮率を回復させる。
