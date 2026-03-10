# BLUEPRINT

## 目的
- Chainlit ベースの Katamari アシスタント基盤を俯瞰し、前処理・多段推論・評価・UI の構造を **個人運用** でも即座に把握する。
- Guardrails の最小読込順と整合した設計判断を素早く下せるよう、日々のメンテナンスで参照する単一の出発点を提供する。

## 担当ロール
- 個人運用者（設計担当の帽子）: ガードレールとロードマップを踏まえた設計判断の基準点として参照する。
- 個人運用者（実装担当の帽子）: SPI/依存関係の境界を確認し、設計変更時の影響を判断する。
- 個人運用者（計画担当の帽子）: 機能境界と非機能要件の根拠を把握し、ロードマップ調整に反映する。

## スコープ
### In Scope
- Persona → Trim → Reflect チェーンの責務分離とデータフロー。
- `src/app.py`, `src/core_ext/`, `src/providers/` 間の依存関係とエラーハンドリング方針。
- SSE ストリーム、UI 反映遅延、トークン制御を満たす非機能設計根拠。

### Out of Scope
- 各 Provider 実装の詳細ロジック（`docs/addenda/F_Provider_Matrix.md` を参照）。
- 個別テストケースや CI 手順（`RUNBOOK.md`, `CHECKLISTS.md` に委譲）。

## システム像
- Persona 設定 (YAML) を persona_compiler モジュールでシステムプロンプトへ変換し、禁則リストを検査したうえで Trim/Reflect パイプラインに投入する。
- SSE は `src/app.py` をエントリとしてストリームし、UI ではテーマ (`themes/`) の設定で描画を制御する。
- Provider 切替は SPI (`src/providers/`) の共通インターフェースで行い、`third_party/Day8/workflow-cookbook/BLUEPRINT.md` の構成図と整合させる。

## 入出力契約
- **入力**: Persona YAML、ユーザー指示、Provider 選択。フォーマットは `docs/addenda/C_Persona_Schema.md` を参照。
- **出力**: Trim/Reflect 後のレスポンス、SSE ストリーム、評価ログ。`docs/Katamari_Technical_Spec_v1_ja.md` のシーケンス図と一致させる。
- **連携**: 検証手順と評価は `RUNBOOK.md` と `EVALUATION.md` に引き渡し、ロードマップとの対応は `docs/ROADMAP_AND_SPECS.md` を参照する。

## ガードレール項目
- Persona→Trim→Reflect の各段で AI 支援を受ける際は、**人が最終確認する責務**を明示し、再試行可能な手順と再試行不可な手順を区別する。
- Provider 追加や設定変更は SPI (`src/providers/`) を経由し、`docs/addenda/F_Provider_Matrix.md` に記載の互換条件を満たすこと。
- SSE 遅延が閾値（p95 ≤ 1.0s）を超えた場合は `RUNBOOK.md` の検証フェーズで緩和策を実施し、結果を Task Seed に記録する。
- Birdseye のノード（`docs/birdseye/index.json`, `caps/*.json`）へ影響する設計変更は、同日付で更新し変更理由を Task Seed に紐付ける。
- AI が提示した設計案を採用する際は、この BLUEPRINT に整合する根拠（入力/出力契約・再試行可否・影響範囲）を箇条書きで追記する。

## 更新ステップ
1. `docs/ROADMAP_AND_SPECS.md` で対象フェーズと必要な仕様リンクを確認する。
2. Guardrails の「目的→スコープ→I/O→AC→最小フロー」に沿って設計変更をドラフト化し、個人運用で実施可能な粒度に分割する。
3. 設計が運用・評価に影響する場合は `RUNBOOK.md`・`CHECKLISTS.md`・`EVALUATION.md` を同期更新し、同一コミット内で整合を確認する。
4. Birdseye (`docs/birdseye/index.json`, `docs/birdseye/caps/`) を更新し、依存関係が最新になっていることを確認する。単独作業のため更新日は共通タイムスタンプで統一する。
5. `third_party/Day8/workflow-cookbook/GUARDRAILS.md` の「BLUEPRINT」節で定義された目的・スコープ・AC と照合し、本書の更新が指針と矛盾していないか確認する。

## 受入基準
- Persona/Trim/Reflect チェーンのデータフローが `docs/Katamari_Technical_Spec_v1_ja.md` と矛盾しない。
- SSE 初期 p95 ≤ 1.0s、UI 反映遅延 ≤ 300ms の根拠が明記されている。
- Provider 切替方針が `docs/addenda/F_Provider_Matrix.md` の互換ポリシーを満たす。
- Guardrails BLUEPRINT の `Purpose / Scope / AC` に記載された期待値をすべて満たす注記が含まれている。

- [ ] 主要ユースケースの I/O 契約（入力/出力の型と例）が定義されている。
- [ ] 例外パスと再試行可否が `docs/Katamari_Technical_Spec_v1_ja.md` と整合する。
- [ ] Birdseye index/capsule の更新日時が最新コミット以降になっている。
- [ ] Task Seed (`TASK.*.md`) に変更理由とフォローアップが記録されている。
- [ ] Guardrails BLUEPRINT（`third_party/Day8/workflow-cookbook/GUARDRAILS.md`）と本書のガードレール項目が一致する。
- [ ] AI からの提案を採用した設計差分に、人間が確認済みである旨の記録が残っている。

## 参照
- [docs/ROADMAP_AND_SPECS.md](docs/ROADMAP_AND_SPECS.md)
- [docs/Katamari_Functional_Spec_v1_ja.md](docs/Katamari_Functional_Spec_v1_ja.md)
- [docs/Katamari_Technical_Spec_v1_ja.md](docs/Katamari_Technical_Spec_v1_ja.md)
- [third_party/Day8/workflow-cookbook/GUARDRAILS.md](third_party/Day8/workflow-cookbook/GUARDRAILS.md)
