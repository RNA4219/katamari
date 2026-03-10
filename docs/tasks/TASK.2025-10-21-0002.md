# TASK.2025-10-21-0002

## 目的
- Chainlit 既定の無認証状態から Header Auth（M1）→OAuth（M1.5）へ移行し、運用エンドポイントの公開リスクを低減する。

## 背景
- `README.md` や `docs` 系仕様書に、現行リリースが無認証である旨と `/healthz` `/metrics` が公開エンドポイントである旨を追記した。
- 導入方針が固まり次第、アプリ実装とドキュメント注記の撤回を同時に行う必要がある。

## 要件
- Chainlit の `config.toml` またはアプリ実装で Header Auth を有効化し、Bearer トークンの検証ロジックを追加する。
- OAuth 方式（M1.5）の構成・Secrets 取扱い手順を `RUNBOOK.md` / `H_Deploy_Guide` に記載する。
- `/healthz` `/metrics` の公開可否を整理し、必要に応じてネットワーク制御または別ポートへの切り出しを検討する。
- 認証導入後、暫定注記（`docs/Katamari_Functional_Spec_v1_ja.md` など）を撤回し、運用ドキュメントを更新する。

## チェックリスト
- [ ] Header Auth 実装のテスト（`pytest`）を追加し、トークン不正時の挙動を検証した。
- [ ] OAuth 設定の統合テスト（可能なら `cd upstream/chainlit && pnpm run test` もしくはモック）を準備した。
- [ ] `/healthz` `/metrics` の公開方針を決定し、必要に応じてアクセス制御を設定した。
- [ ] ドキュメントに追加した暫定注記を撤回し、最新構成を反映した。
- [ ] Guardrails 文書（`RUNBOOK.md` / `CHECKLISTS.md` / `EVALUATION.md`）と整合させた。

## 参照
- `docs/Katamari_Functional_Spec_v1_ja.md`
- `docs/Katamari_Requirements_v3_ja.md`
- `docs/addenda/H_Deploy_Guide.md`
- `README.md`
