# TASK.2025-10-21-0003

## 目的
- Functional Spec v1（第5章）および要件定義 v3（FR-06）で定義されたログ出力要件を実装し、現状の未達成状態を解消する。
- `req_id` などの計測フィールドを統一して収集し、将来の `/metrics` 拡張と運用監視に備える。

## 背景
- 現在の Chainlit 派生実装にはログ出力（`req_id, user_id?, model, chain_id, token_in/out, latency_ms, compress_ratio, step_latency_ms`）が存在せず、仕様とのギャップが生じている。
- 仕様書には暫定注記を追加済みだが、実装完了時に撤回する必要がある。

## 要件
- 推論リクエスト単位で上記フィールドを JSON or structured logging で記録する。出力先はローカルファイルまたは標準出力でよいが、後続で集約できる形にする。
- 例外時も `req_id` とエラー種別を残し、再試行可否を既存エラー設計に倣って区別する。
- `/metrics` 拡張との整合を確保するため、トークン数は Trim/Persona 処理後の値を採用する。
- 実装完了後、Functional Spec / Requirements / CHECKLISTS の暫定注記を撤回する。

## チェックリスト
- [ ] `pytest` / `cd upstream/chainlit && pnpm run test` でログ出力のユニットテスト・統合テストを追加し、`req_id` と token カウントが一致することを確認した。
- [ ] `mypy --strict` / `ruff` を通過し、型安全なログフォーマット定義を導入した。
- [ ] エラー時のログ出力が既存例外階層と整合することを確認した。
- [ ] Functional Spec / Requirements / CHECKLISTS の暫定注記を撤回し、実装手順を `RUNBOOK.md` に追記した。
- [ ] `/metrics` との連携（必要ならダミー値）を評価し、フォローアップがあれば新規 Task Seed に切り出した。

## 参照
- `docs/Katamari_Functional_Spec_v1_ja.md`
- `docs/Katamari_Requirements_v3_ja.md`
- `CHECKLISTS.md`
- `RUNBOOK.md`
