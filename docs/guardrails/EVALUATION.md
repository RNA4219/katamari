# EVALUATION

## 目的
- Katamari の成果物が仕様・非機能要件・Guardrails を満たしているか、**個人運用** でも自分で判断できる枠組みを提供する。
- 受入可否を明確にし、差分が残る場合は Task Seed へフォローアップを連携する。

## 担当ロール
- 個人運用者（QA 帽子）: 受入判定を行い、DoD 達成状況を記録する。
- 個人運用者（Reviewer 帽子）: Guardrails の指標との整合を確認し、差分をタスク化する。
- 個人運用者（オーナー帽子）: 判定結果をロードマップと照合し、次フェーズへの承認を行う。

## スコープ
### In Scope
- `docs/Katamari_Requirements_v3_ja.md` / `docs/Katamari_Functional_Spec_v1_ja.md` に基づく機能評価。
- 非機能（性能・セキュリティ・可観測性）指標の測定と合否判断。
- Task Seed とチェックリストで定義された DoD の追跡。

### Out of Scope
- PMF の評価やビジネス指標の測定。
- SLA/アラートの常時監視（SRE 評価に委譲）。

## 評価ステップ
1. `RUNBOOK.md` に従って環境を起動し、`pytest` / `pnpm run test`（必要に応じて `cd upstream/chainlit`）/ `ruff` / `mypy --strict` を実行する。Cypress ベースの Node E2E テストは `pnpm run test` で統合的に実施する。個人環境ではログ保存先とファイルパスを Task Seed に記入する（例: `pnpm run test` の結果を `/tmp/katamari-pnpm-test.log` に保存）。
2. `scripts/perf/collect_metrics.py` や Chainlit ログから性能指標を取得し、要件値と比較する。例: `python scripts/perf/collect_metrics.py --metrics-url http://127.0.0.1:8787/metrics --output /tmp/katamari-metrics.json`
3. `docs/Release_Checklist.md` と `docs/Security_Review_Checklist.md` の結果を確認し、未完了項目があれば Task Seed に登録する。
4. 判定結果を Issue / PR / `CHANGELOG.md` に記録し、必要なら `RUNBOOK.md`・`CHECKLISTS.md` を更新する。
5. `third_party/Day8/workflow-cookbook/GUARDRAILS.md` の「EVALUATION」節で定義された指標と比較し、差異があれば補足を記録する。

## 指標
- 機能: Persona 切替、Trim/Reflect、多段推論の成功率。
- 性能: SSE p95、UI 反映遅延、トークン削減率（`docs/Katamari_Requirements_v3_ja.md` の数値）。
- セキュリティ: リリース / セキュリティチェックリストの完了状況。
- 再現性: Birdseye 図と Task Seed の証跡が最新コミット以降であること。

## ガードレール項目
- 受入判定は必ず人間が実施し、AI から提案された評価観点は補助情報として扱う。
- 指標が閾値を下回った場合は `RUNBOOK.md` の検証手順を再実行し、フォローアップを Task Seed に登録する。
- 重大な逸脱は `CHECKLISTS.md` の該当フェーズへ反映し、再発防止策を記録する。
- `third_party/Day8/workflow-cookbook/GUARDRAILS.md` の EVALUATION 節で定義された Acceptance を引用し、理由と共に合否を記載する。
- 自己検証ログ（lint/type/test/perf）はローカルパスを明示し、共有が必要な場合は匿名化して添付する。

## 受入基準
- 主要ユーザーフローが設計通り完遂し、指標が要件内である。
- チェックリストの必須項目が `PASS` か `N/A`（理由付き）で記録されている。
- 未達成項目は Task Seed にフォローアップが登録され、対応計画が明記されている。
- Guardrails EVALUATION の Acceptance 条件を満たさない場合は差分理由が明記されている。

## チェック項目
- [ ] Lint / type / test / `pnpm run test` の結果ログを保管し、Task Seed に記録した。
- [ ] 性能指標（SSE p95、UI 遅延、トークン削減率）を測定し、要件と比較した（`scripts/perf/collect_metrics.py` の出力を Task Seed に添付）。
- [ ] セキュリティ / リリースチェックリストをレビューし、未完了項目を Task Seed に転記した。
- [ ] 判定結果を `docs/ROADMAP_AND_SPECS.md` の対象フェーズへ反映した。
- [ ] Guardrails EVALUATION 節（`third_party/Day8/workflow-cookbook/GUARDRAILS.md`）と本書のガードレール項目が一致する。
- [ ] AI から提案された評価観点を採用した場合、人間の判定と差分理由を記録した。

## 参照
- [docs/ROADMAP_AND_SPECS.md](docs/ROADMAP_AND_SPECS.md)
- [docs/Release_Checklist.md](docs/Release_Checklist.md)
- [docs/Security_Review_Checklist.md](docs/Security_Review_Checklist.md)
- [third_party/Day8/workflow-cookbook/GUARDRAILS.md](third_party/Day8/workflow-cookbook/GUARDRAILS.md)
