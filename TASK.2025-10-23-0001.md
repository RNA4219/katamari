# TASK.2025-10-23-0001

## 目的
- Guardrails ドキュメントの保守に向けて、2025-10-23 実施分の差分検証と記録を行う。
- `TASK.2025-10-19-0001.md` で確立した手順を踏襲し、テスト・Lint・型チェック運用を統一する。

## 要件
- BLUEPRINT/RUNBOOK/EVALUATION/CHECKLISTS の差分確認ログを収集し、再試行可否や担当を明示する。
- README と `docs/ROADMAP_AND_SPECS.md` の導線を再確認し、変更があれば Task Seed に記録する。
- Guardrails 文書更新の理由と採否を Task Seed に追記し、Birdseye 更新と同日にコミットする。
- Lint/Type/Test（`ruff`/`mypy --strict`/`pytest`/`pnpm run test`）の実行計画を RUNBOOK と同期し、結果ログの保存先を Task Seed で管理する。
- チェックリスト差分が発生した場合はフォローアップを作成し、後続タスクを準備する。

## 想定コマンド
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-eval.txt  # CI ワークフローのローカル検証
cd upstream/chainlit && pnpm install  # `pnpm run test` を実行する場合に必要
pytest
pnpm run test -- --watch=false  # 正式なテスト実行手順（`pnpm run test -- --watch=false`）
ruff check .
mypy --strict
rg -n "BLUEPRINT" third_party/Day8/workflow-cookbook/GUARDRAILS.md
rg -n "RUNBOOK" third_party/Day8/workflow-cookbook/GUARDRAILS.md
rg -n "EVALUATION" third_party/Day8/workflow-cookbook/GUARDRAILS.md
rg -n "CHECKLIST" third_party/Day8/workflow-cookbook/GUARDRAILS.md
```

## 受入基準
- CI 実行ログで lint/type/test が成功し、Secrets なし環境で統合テストがスキップされる。
- Docker イメージが GHCR に push され、`vX.Y.Z-katamari` 形式のタグで管理される。
- `CHECKLISTS.md` と `RUNBOOK.md` に CI/リリース手順が反映され、`EVALUATION.md` で DoD 判定が可能。
- Guardrails 文書（HUB/BLUEPRINT/RUNBOOK/EVALUATION/CHECKLISTS）の相互参照が更新されている。
- Birdseye 再生成では `third_party/Day8/workflow-cookbook/tools/codemap/update.py` を実行し、±2 hop のノード抽出と UTC ISO8601 の `generated_at`/`mtime` を確認する。

## フォローアップ
- Guardrails の「テスト先行・最小差分」原則に従い、未解決項目は後続 Task Seed または Issue に分割する。
- Birdseye index/caps を更新し、CI・リリース関連ノードの可視化を維持する。
- Guardrails 文書更新の差分と今後のタスクを Task Seed 内で管理する。
- 認証方式導入のフォローアップは [`TASK.2025-10-19-0002.md`](TASK.2025-10-19-0002.md) に集約する。
## ステータス
- 作業日: 2025-10-23
- 優先度: M1 → M1.5 認証移行の決定と実装を同一スプリント内で完了する

## 目的
- Chainlit 既定の無認証状態から Header Auth（M1）を導入し、既存エンドポイントの公開リスクを抑制する。
- Header Auth 稼働後に OAuth（M1.5）へ段階移行し、Secrets 管理と運用手順を整備する。

## 背景
- 現行リリースは `/healthz` `/metrics` を含め無認証で公開されており、暫定ドキュメントでも注意喚起を行っている。
- 認証導入と同時に暫定ドキュメントの注記撤回が必要なため、実装と文書更新を同じタスクで追跡する。

## 成果物
1. Header Auth（Bearer トークン検証）を有効化した Chainlit 構成および実装。
2. OAuth（M1.5）向け Secrets フローと設定反映手順を記述した運用ドキュメント。
3. `/healthz` `/metrics` の公開方針とアクセス制御方針の決定事項。
4. 暫定注記を撤回し最新構成へ更新された README / RUNBOOK / Guardrails 系ドキュメント。

## スコープ
- 対象: `upstream/chainlit`（アプリ・設定）、`docs` / `RUNBOOK.md` / `CHECKLISTS.md` 等の運用文書。
- 非対象: IdP 側の新規構築（別タスク扱い）、既存 API の仕様変更（後方互換維持）。

## 実行ステップ
1. Header Auth の設定を `config.toml` もしくはアプリ初期化コードに追加し、Bearer トークンの検証ロジックを実装する。
2. `pytest` による Header Auth 挙動のユニットテスト・API テストを実装し、不正トークン時の拒否を検証する。
3. OAuth（M1.5）の採用方式を決定し、Secrets 配布・ローテーション手順を `RUNBOOK.md` / `docs/addenda/H_Deploy_Guide.md` に反映する。
4. `/healthz` `/metrics` の公開要否を整理し、必要に応じてネットワーク制御または別ポート切り出しを設計・実装する。
5. 暫定注記（`docs/Katamari_Functional_Spec_v1_ja.md` 等）を撤回し、新構成を記述したドキュメントへ更新する。
6. 上記変更の整合性を確認するため、`pnpm run test`（必要なら `cd upstream/chainlit`）を含む統合テスト/モックを実行し、稼働確認を行う。

## リスクと対策
- **トークン流出**: Secrets を Vault 管理とし、ローテーション手順をドキュメントに明記。
- **OAuth ロールアウト遅延**: Header Auth 完了後に段階導入する計画とし、運用切替ガイドラインを併記。
- **公開エンドポイント停止リスク**: `/healthz` `/metrics` のアクセス制御を段階的に適用し、監視チームと調整。

## チェックリスト
- [ ] Header Auth 実装用 `pytest` テストを追加し、正/誤トークンの挙動を検証した。
- [ ] OAuth 設定の統合テストを `pnpm run test`（必要なら `cd upstream/chainlit`）で実行し、モックまたはステージングで検証した。
- [ ] `/healthz` `/metrics` の公開方針を確定し、アクセス制御を設定または設計書に反映した。
- [ ] 暫定注記を撤回し、README / docs / RUNBOOK の該当箇所を更新した。
- [ ] Guardrails 文書（`RUNBOOK.md` / `CHECKLISTS.md` / `EVALUATION.md`）と最新構成を突合した。

## 参照
- `docs/Katamari_Functional_Spec_v1_ja.md`
- `docs/Katamari_Requirements_v3_ja.md`
- `docs/addenda/H_Deploy_Guide.md`
- `README.md`
- `RUNBOOK.md`
