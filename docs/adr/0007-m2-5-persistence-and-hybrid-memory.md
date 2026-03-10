# ADR-0007: M2.5 ハイブリッドメモリと永続化を整備する

## Context
- 背景: M2.5 では会話履歴と評価結果を永続化し、再利用・回帰分析できるハイブリッドメモリ基盤が求められる。
- 課題: 現状は揮発性メモリのみで、長期学習や多ユーザー同時利用に耐えない。
- 参考資料: [`docs/Katamari_Technical_Spec_v1_ja.md`](../Katamari_Technical_Spec_v1_ja.md) の Persistence 章、`docs/katamari_wbs.csv` の M2.5 タスク群。

## Decision
- 方針: ベクトルストア＋リレーショナル DB の二層構成を採用し、メタデータと埋め込みを分離管理する。Chainlit セッション終了時に同期タスクを実行する。
- 採用理由: 推論高速化と検索精度を両立しながら、監査要件を満たす履歴保存を実現するため。
- 運用: ストア更新はイベント駆動で行い、失敗時は再試行ポリシーを `RetryableStorageError` と `FatalStorageError` で区別する。

## Consequences
- 影響範囲: `src/core_ext/memory/` に永続化レイヤが追加され、DB/ベクトルストア接続設定が `config/` に増える。インフラ側でバックアップ運用が必要。
- 利点: 過去履歴を活用した応答精度向上と、評価結果の再分析が可能になる。
- リスク/フォローアップ: ストレージコストとレイテンシが増大するため、TTL・圧縮ポリシーを定期見直しする。PII を扱わないようサニタイズ手順を徹底する。
- 現状: `src/core_ext/memory/` ディレクトリとIn-memory実装が完了。PostgreSQL実装とバックアップ・リストア手順は今後の課題。

## Status
- ステータス: 実装中 (In-memory完了、PostgreSQL実装は今後の課題)
- 最終更新日: 2025-03-10

## DoD
- [x] 会話メタデータと埋め込みが別ストアに保存され、統合クエリで再構築できる統合テストが存在する。
  - `tests/core_ext/test_memory.py` に `TestMemoryStore` クラスで統合テストを実装済み。
  - `InMemoryMetadataStore`, `InMemoryMessageStore`, `InMemoryEmbeddingStore` の各ストアが独立動作。
  - `MemoryStore.save_conversation_with_messages()` と `get_full_conversation()` で統合クエリを提供。
- [x] 永続化処理が失敗した際の再試行制御と Fatal エラーの遮断がユニットテストで検証されている。
  - `StorageError`, `RetryableStorageError`, `FatalStorageError` を `storage.py` に定義。
  - `tests/core_ext/test_memory.py::TestStorageErrors` でエラー分類をテスト検証済み。
- [ ] バックアップ・リストア手順が `RUNBOOK.md` または関連ドキュメントに追記されている。
- [x] ストレージ設定（接続情報・TTL・圧縮方針）が `config/` とドキュメントで同期されている。
  - `config/env.example` に `MEMORY_STORAGE_BACKEND`, PostgreSQL接続情報, TTL設定を追加済み。
- [ ] PII サニタイズとアクセス監査ログの要件を満たす証跡が残っている。
- フォローアップ: `TASK.2025-10-19-0002.md` で進行管理し、実装完了時点で上記 DoD を満たしたうえで Consequences の注記を削除する。
