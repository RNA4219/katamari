# Birdseye 観測ハブ README

## 概要
Birdseye は Guardrails 連携のための観測ハブとして、Katamari リポジトリにおける重要モジュールの依存関係・優先度・検証手順を JSON で記述します。更新差分は `TASK.*.md` 系 Task Seed と同期し、リスクやテスト結果のトレーサビリティを確保します。全体運用フローは [docs/ROADMAP_AND_SPECS.md](../ROADMAP_AND_SPECS.md) と相互参照してください。

## JSON ファイル構成（index.json / caps/*.json / hot.json）
`docs/birdseye/index.json` は観測対象ノードの一覧 (`nodes`) と依存エッジ (`edges`) を保持します。各ノードは `role`（コンポーネント役割）、`caps`（対応する Capsule ファイルパス）、`mtime`（最終更新タイムスタンプ）を持ち、`generated_at` は Birdseye 全体で共有する5桁の連番です。【F:docs/birdseye/index.json†L1-L35】

`docs/birdseye/caps/*.json` には個別モジュールの Capsule を格納します。例として `docs/birdseye/caps/src.app.json` では、`id` と `role` に加え `summary`（役割概要）、`public_api`（外部公開 I/F）、`deps_out`/`deps_in`（依存の流出入）、`tests`（検証コマンド）、`risks`（既知リスク）、`generated_at`（index を含む他ファイルと一貫した連番）が記録されています。【F:docs/birdseye/caps/src.app.json†L1-L27】

`docs/birdseye/hot.json` は優先監視ノード (`entries`) の配列で、各要素が `id` と更新理由 (`reason`) を示します。`generated_at` は index/caps と同一ルールの5桁連番で Hot リストの根拠を明示します。【F:docs/birdseye/hot.json†L1-L12】

## 更新手順
1. **最小読込順の維持**: Birdseye を参照・更新する際は `index.json` → `caps/*.json` → `hot.json` の順で読み込み、親ノードから依存 Capsule、優先ノードへと文脈を深めます。
2. **連番の採番**: すべての Birdseye JSON (`index.json` / `caps/*.json` / `hot.json`) の `generated_at` には `00001` から始まる5桁の連番を用います。既存値を昇順に並べて「古い」値から採番し直し、新規ファイルは最大値の次番を割り当てます。`mtime` は必要に応じて更新しますが、`generated_at` とは独立に扱います。
3. **依存情報の同期**: `index.json` の `edges` と各 Capsule の `deps_out`/`deps_in` を突き合わせ、不整合があれば両方を同時に修正します。Capsule の `tests` セクションが指すコマンドは最新の検証手順へ更新します。
4. **結果の記録**: 更新の背景や検証ログは直近の Task Seed（例: [`TASK.2025-10-19-0001.md`](../../TASK.2025-10-19-0001.md)）に記録し、Guardrails 受入証跡と連動させます。
5. **レビュー連携**: 更新後は Pull Request で本 README と [docs/ROADMAP_AND_SPECS.md](../ROADMAP_AND_SPECS.md) の関連節を参照し、タイムスタンプ・依存関係・テスト記録の整合を確認します。

## Guardrails 連携
- Guardrails 群（`BLUEPRINT.md` / `RUNBOOK.md` / `EVALUATION.md` / `CHECKLISTS.md`）を更新する際は Birdseye で特定された Hot ノードと Capsule のリスクを参照し、必要なドキュメント更新を Task Seed へ記録します。
- Birdseye 更新時は Guardrails のチェックリストに沿ってリスク評価・テスト実行・証跡リンクを残し、`generated_at` の連番が欠番なく昇順であることを確認してからコミットします。
- 詳細な更新要件とワークフローは [docs/ROADMAP_AND_SPECS.md](../ROADMAP_AND_SPECS.md) の「Birdseye 更新フロー」を参照してください。
- Guardrails から直接 Birdseye を参照する際の導線は [docs/BIRDSEYE.md](../BIRDSEYE.md) を確認してください。
