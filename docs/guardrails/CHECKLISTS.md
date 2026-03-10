# CHECKLISTS

## 目的
- Katamari の開発・レビュー・リリース・運用で必要な確認項目を集約し、Guardrails とロードマップ要件を **個人運用** でも漏れなく満たす。
- DoD 達成状況を可視化し、未完了項目を Task Seed に連携する。

## 担当ロール
- 個人運用者（開発・レビューの帽子）: フェーズごとのチェック項目を Issue / PR / Task Seed に転記し、進捗を可視化する。
- 個人運用者（マネージャー帽子）: ガードレール遵守状況を確認し、フォローアップを Task Seed に落とし込む。
- 個人運用者（Ops 帽子）: 運用フェーズのチェックリストを活用し、Runbook との整合を維持する。

## スコープ
### In Scope
- 開発 (Dev)、レビュー (PR)、リリース (Release)、運用 (Ops) フェーズのチェック項目。
- Guardrails が求める最小差分・自己検証手順の記録。
- Task Seed / `EVALUATION.md` と連携したフォローアップ管理。

### Out of Scope
- 組織全体のコンプライアンスチェック。
- マーケティングや営業資料のレビュー。

## 使い方
1. 対象フェーズ開始時に該当セクションをコピーし、Issue / PR / Task に貼り付ける。個人運用では Task Seed に転記してもよい。
2. 各項目の実施時に証跡（ログ、CI 結果、スクリーンショット）を残す。
3. 未完了項目は Task Seed に転記し、`EVALUATION.md` で DoD 判定に利用する。
4. `third_party/Day8/workflow-cookbook/GUARDRAILS.md` の該当フェーズ（Dev/PR/Release/Ops）に定義されたチェックと乖離がないか確認する。

## ガードレール項目
- 各フェーズで AI 補助を受ける場合、人間が承認した証跡（コメントや Task Seed）を残す。
- 変更は最小差分で進め、未対応の大きな差分は新規 Task Seed またはチェックリスト項目として切り出す。
- Birdseye / Guardrails 文書を更新した日は共通タイムスタンプとし、関連するチェックリストにリンクを記載する。
- 公開 API 変更や例外ポリシー変更が必要な場合は、`BLUEPRINT.md`・`RUNBOOK.md`・`EVALUATION.md` を同時に更新する。
- チェック項目は `docs/ROADMAP_AND_SPECS.md` のフェーズ定義と整合性を保ち、齟齬があれば即時修正する。

## チェックリスト
### Development
- [ ] テストを先に追加し、`pytest` / `pnpm run test`（必要に応じて `cd upstream/chainlit`）が成功した。
- [ ] `mypy --strict` と `ruff` を通過（またはスキップ理由を記録）。
- [ ] 公開 API 変更がない、または段階移行フラグを設定した。
- [ ] Birdseye index/caps を更新し、該当ノードの要約を最新化した。
- [ ] AI 提案を採用した実装は人間が検証した証跡を Task Seed に残した。
- [ ] 認証実装時に暫定注記（`README.md` / `docs/Katamari_*` / `H_Deploy_Guide`）を撤回し、[`TASK.2025-10-19-0002.md`](docs/tasks/TASK.2025-10-19-0002.md) のチェックを完了した。
- [x] ログ実装（FR-06 / Functional Spec 5章）に着手する際は [`TASK.2025-10-21-0003.md`](docs/tasks/TASK.2025-10-21-0003.md) を参照し、暫定注記の撤回と `katamari.request` 構造化ログ（`tests/app/test_logging.py`）の検証を完了した。

### Pull Request / Review
- [ ] 変更理由と影響範囲を `docs/ROADMAP_AND_SPECS.md` の該当項目にリンクした。
- [ ] Task Seed を更新し、レビュー観点を共有した。
- [ ] Guardrails の最小読込手順をレビュアーが再現できるよう案内した。
- [ ] Guardrails PR チェック項目と差異がないことを確認した。
- [ ] AI からのレビュー提案を採用した場合は採否理由を記録した。

### Release
- [ ] `docs/Release_Checklist.md` の優先項目（受入証跡・影響範囲・ラベル・CHANGELOG・`NOTICE`/`LICENSE` 同梱）がすべて `PASS`。
- [ ] 受入基準の証跡を `EVALUATION.md` や PR に添付し、レビュー時に参照できる。
- [ ] 影響範囲（依存モジュール・運用手順・インフラ）を再確認し、必要な同期ドキュメントを更新した。
- [ ] PR に `type:*` / `semver:*` ラベルを付与し、リリースノート分類を確定した。
- [ ] `CHANGELOG.md` にリリース内容を追記し、タグ発行準備ができている。
- [ ] 配布物へ [`LICENSE`](LICENSE) / [`NOTICE`](NOTICE) を同梱する手順が `RUNBOOK.md` と一致する。
- [ ] GHCR へのビルド/公開手順が `RUNBOOK.md` と一致する。
- [ ] AI による自動化案を導入する際は人間が安全性確認を行い、`RUNBOOK.md` に反映した。

### Ops / Incident
- [ ] 障害対応ログが `RUNBOOK.md` に沿って記録されている。
- [ ] 再発防止策が Task Seed または Issue で管理されている。
- [ ] セキュリティインシデントを `docs/Security_Review_Checklist.md` に追記した。
- [ ] Guardrails Ops 項目の参照結果を Task Seed に反映した。
- [ ] AI からの復旧案を採用する際は人間が検証し、結果を `RUNBOOK.md` と Task Seed に反映した。

## 参照
- [docs/ROADMAP_AND_SPECS.md](../ROADMAP_AND_SPECS.md)
- [docs/Release_Checklist.md](../Release_Checklist.md)
- [docs/Security_Review_Checklist.md](../Security_Review_Checklist.md)
- [third_party/Day8/workflow-cookbook/GUARDRAILS.md](../../third_party/Day8/workflow-cookbook/GUARDRAILS.md)
