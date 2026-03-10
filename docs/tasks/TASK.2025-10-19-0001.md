# TASK.2025-10-19-0001

## 目的
- 個人+AI 運用で必須となる Guardrails ドキュメント（BLUEPRINT/RUNBOOK/EVALUATION/CHECKLISTS）を初期整備し、日次運用の基点を提供する。
- Task Seed をハブにして目的・要件・証跡コマンドを明示し、AI 補助を受けた判断でも人が即時追跡できる状態を作る。

## 要件
- BLUEPRINT/RUNBOOK/EVALUATION/CHECKLISTS を個人+AI 運用向けガードレールとして更新し、再試行可否や責務分担を明示する。
- README と `docs/ROADMAP_AND_SPECS.md` から上記ドキュメントへの導線を追加し、最小読込手順に組み込む。
- Guardrails 文書の更新理由と AI 提案採否を Task Seed に記録し、Birdseye 更新と同日にコミットする。
- Lint/Type/Test（`ruff`/`mypy --strict`/`pytest`/`pnpm run test`）の実行計画を RUNBOOK に揃え、結果ログ保存先を Task Seed で管理する。
- 評価時に参照する指標とチェックリストの差分が発生した場合は直ちに Task Seed にフォローアップを追加し、後続タスクへ切り出す。

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

## フォローアップ
- Guardrails の「テスト先行・最小差分」原則に従い、未解決項目は後続 Task Seed または Issue に分割する。
- Birdseye index/caps を更新し、CI・リリース関連ノードの可視化を維持する。
- Guardrails 文書更新の差分と今後のタスクを Task Seed 内で管理する。
- 認証方式導入のフォローアップは [`TASK.2025-10-19-0002.md`](TASK.2025-10-19-0002.md) に集約する。
