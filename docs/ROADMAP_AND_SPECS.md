# Katamari ロードマップ & 仕様書インデックス

本ドキュメントは、リポジトリ内に散在する Markdown/ソース構成を横断的に参照できるようにする統合ハブです。優先タスク、仕様書、実装領域の対応関係をここから辿れます。

## 1. 上位ドキュメントの索引

| 区分 | ファイル | 目的 / 主な内容 |
| --- | --- | --- |
| ビジョン・要件 | `docs/Katamari_Requirements_v3_ja.md` | 対象ユーザー、価値、非機能要件、M1〜M3の到達目標。 |
| 機能仕様 | `docs/Katamari_Functional_Spec_v1_ja.md` | ユースケース別フロー、画面要素、チェーン挙動。 |
| 技術仕様 | `docs/Katamari_Technical_Spec_v1_ja.md` | システム構成、API、データフロー、例外ハンドリング方針。 |
| OpenAPI | `docs/openapi/katamari_openapi.yaml` | HTTP インターフェース定義 (`/metrics`, `/healthz` 予定含む)。 |
| 追加リファレンス | `docs/addenda/*.md` | UI モック、プロバイダ比較、テストケース、構成ファイル解説など。 |
| マイルストーン DoD | `docs/adr/0004-m1-metrics-and-retention.md` ほか [ADR #0004〜#0007](adr/README.md) | M1〜M2.5 の到達基準と DoD チェックリスト。 |
| フォーク運用 | `docs/UPSTREAM.md`, `docs/FORK_NOTES.md`<br>[ADR #0001](adr/0001-use-chainlit-subtree.md) | Chainlit subtree の取得・差分吸収手順。 |
| リリース & セキュリティ | `docs/Release_Checklist.md`, `docs/Security_Review_Checklist.md` | 準備→検証→リリース順のチェックリスト、受入証跡・CI 結果確認・影響範囲同期・CHANGELOG/NOTICE 更新を含む品質ゲート。 |
| Guardrails 連動ドキュメント | `BLUEPRINT.md`, `RUNBOOK.md`, `EVALUATION.md`, `CHECKLISTS.md`, `TASK.*.md` | Guardrails フローに沿った設計・運用・評価・追跡の基盤文書。 |
| Day8 HUB→Guardrails | `third_party/Day8/workflow-cookbook/HUB.codex.md` → `third_party/Day8/workflow-cookbook/GUARDRAILS.md` | Day8 観測ハブから統制基準へ進む推奨導線（役割: HUB が全体俯瞰、GUARDRAILS が安全策定）。 |
| Day8 HUB | `third_party/Day8/workflow-cookbook/HUB.codex.md` | 観測ハブとして Day8 オペレーション全体の入口を提示する役割ドキュメント。 |
| Day8 Guardrails | `third_party/Day8/workflow-cookbook/GUARDRAILS.md` | HUB からのインサイトを受けて統制基準・安全策を定義する役割ドキュメント。 |
| Day8 Blueprint | `third_party/Day8/workflow-cookbook/BLUEPRINT.md` | Guardrails を適用した運用ブループリント（実装設計）。 |

> Guardrails 連動ドキュメントの概要（いずれも個人+AI 運用に必要なガードレールを網羅）
> - [BLUEPRINT.md](../BLUEPRINT.md): Persona/Trim/Reflect チェーンの責務分離・再試行方針・個人/AI 共同運用の境界を整理。
> - [RUNBOOK.md](../RUNBOOK.md): 「準備→実行→検証」の実務手順とトラブルシュート、AI からの提案を受ける際の確認ステップを定義。
> - [EVALUATION.md](../EVALUATION.md): 成果の受入判定フローとメトリクス、ガードレール逸脱時のエスカレーション手順を明文化。
> - [CHECKLISTS.md](../CHECKLISTS.md): Dev→PR→Release→Ops の帽子を被り替えながら自己チェックするためのテンプレート。
> - [TASK.<YYYY-MM-DD>-0001.md](../TASK.2025-10-19-0001.md): 初期 Task Seed。目的・要件・想定コマンド・評価ログ連携を記録し、フォローアップを管理。
> - Guardrails 原典: [third_party/Day8/workflow-cookbook/GUARDRAILS.md](../third_party/Day8/workflow-cookbook/GUARDRAILS.md)。各節の目的・
>   スコープ・AC を参照し、上記ドキュメント更新時は整合性を必ず確認する。

### ADR インデックス（コア判断とマイルストーン）
- ADR の作成・更新手順は [CONTRIBUTING.md#ADR を追加・更新する手順](../CONTRIBUTING.md#adr-を追加・更新する手順) を参照してください（`Metadata` セクションの記入と DoD 整合チェックを含む。作成日は正確な日付が不明な場合は省略可）。
- **基盤方針**
  - [ADR #0001: Chainlit リポジトリを git subtree として取り込む](adr/0001-use-chainlit-subtree.md)
  - [ADR #0002: Token カウントに tiktoken を採用する](adr/0002-tokenization-with-tiktoken.md)
  - [ADR #0003: LLM プロバイダ抽象インターフェースを定義する](adr/0003-provider-interface.md)
- **マイルストーン DoD**
  - [ADR #0004: M1 メトリクスと保持率基盤を整備する](adr/0004-m1-metrics-and-retention.md)
  - [ADR #0005: M1.5 OAuth とトークンガバナンスを導入する](adr/0005-m1-5-oauth-and-token-governance.md)
  - [ADR #0006: M2 プロンプト進化コアループを実装する](adr/0006-m2-evolution-core-loop.md)
  - [ADR #0007: M2.5 ハイブリッドメモリと永続化を整備する](adr/0007-m2-5-persistence-and-hybrid-memory.md)

## 2. 実装モジュールと対応仕様

| 実装ディレクトリ | 主担当機能 | 関連仕様 / 参考資料 |
| --- | --- | --- |
| `src/app.py` | Chainlit アプリ本体、ステップ実行、UI 設定。 | 技術仕様 3章、`addenda/B_UI_Mock.md`、`addenda/J_Runbook.md` |
| `src/core_ext/` | トリミング、ペルソナ解析、マルチステップ制御などの拡張。 | `addenda/D_Trim_Design.md`<br>`addenda/C_Persona_Schema.md`<br>[ADR #0002](adr/0002-tokenization-with-tiktoken.md) |
| `src/providers/` | OpenAI/Gemini など LLM プロバイダ抽象化。 | `addenda/F_Provider_Matrix.md`<br>[ADR #0003](adr/0003-provider-interface.md) |
| `themes/` | Chainlit テーマ JSON。 | `README_PERSONAS_THEMES.md`<br>`addenda/B_UI_Mock.md` |
| `tests/` | Pytest ベースの検証群。 | `docs/addenda/I_Test_Cases.md` |
| `config/` | モデル登録、環境変数サンプル。 | `docs/addenda/L_Config_Reference.md` |

## 3. ロードマップ（推奨進行順）

1. **ドキュメント整備**  
   - [`LICENSE`](../LICENSE) を Apache-2.0 に更新し [`NOTICE`](../NOTICE) を追加。
   - `docs/UPSTREAM.md` に subtree 運用手順を追記。  
   - `README.md` を起動手順・ENV・テーマ説明付きに拡充。  
   - `CONTRIBUTING.md` / `CODE_OF_CONDUCT.md` / `CODEOWNERS` を最終化。  
   - `.gitattributes` で改行統一。  
   - `docs/adr/` にテンプレート ([ADR #0000](adr/0000-template.md)) とコア決定（[ADR #0001](adr/0001-use-chainlit-subtree.md) / [ADR #0002](adr/0002-tokenization-with-tiktoken.md) / [ADR #0003](adr/0003-provider-interface.md)）を整備し、最新状態を維持する（手順は [CONTRIBUTING.md#ADR を追加・更新する手順](../CONTRIBUTING.md#adr-を追加・更新する手順) を参照）。
   - マイルストーン DoD を定義した [ADR #0004〜#0007](adr/README.md) を維持し、達成状況をロードマップと同期。

2. **CI・自動化基盤**  
   - `.github/workflows/ci.yml` で lint (ruff), test (pytest), audit (pip-audit) を条件付き実行化。  
   - Secrets がある場合のみプロバイダ統合テストを実行。  
   - `.github/workflows/release.yml` でタグ push 時に GHCR へ Docker イメージを公開。

3. **実装フェーズ**  
   - `context_trimmer` を `tiktoken` ベースへ置換（±5% 精度）。  
  - `semantic_retention` 指標を埋め込み類似度から算出し、`/metrics` で実測値を露出（`-1.0〜1.0` を維持し、欠損は JSON `null`）。UI 表示は任意であり、共有先はダッシュボード/Guardrails ログが基本となる。
    - `scripts/perf/collect_metrics.py` で `/metrics` または Chainlit ログから収集する際、保持率は `-1.0〜1.0` レンジを尊重し、欠損は JSON `null` として書き出す。ダッシュボード連携時は `null` を欠損扱い、負値は異常値ではなく実測シグナルとして保存する。
   - `/metrics` / `/healthz` エンドポイントを追加。  
   - Gemini Provider（stream 対応）を実装。  
   - 以降、OAuth・評価 UI・Prompt evolution など M2 系機能へ拡張。

## 4. 参照クイックリンク

- 実装開始時は `CONTRIBUTING.md` と `CODE_OF_CONDUCT.md` を必読。
- テスト駆動で進める場合は `tests/` を先に追加し、`I_Test_Cases.md` を参照。
- Subtree 同期は `docs/UPSTREAM.md` → `scripts/` の補助スクリプトを活用。
- アーキテクチャ判断は `docs/adr/README.md` と各 ADR（例: [ADR #0001](adr/0001-use-chainlit-subtree.md) / [ADR #0002](adr/0002-tokenization-with-tiktoken.md) / [ADR #0003](adr/0003-provider-interface.md) / [ADR #0004〜#0007](adr/README.md)）を参照。
- 運用時のチェックは `Release_Checklist.md`（受入証跡/影響範囲/ラベル/CHANGELOG/NOTICE 同梱）と `Security_Review_Checklist.md` を使用。
- <a id="day8-sequence"></a>Day8 系資料の推奨参照順: `third_party/Day8/workflow-cookbook/HUB.codex.md`（観測ハブ）→ `third_party/Day8/workflow-cookbook/GUARDRAILS.md`（統制基準）→ `third_party/Day8/workflow-cookbook/BLUEPRINT.md` 群（運用設計）を推奨シーケンスとして維持する。
- Birdseye 更新手順は [`docs/birdseye/README.md`](birdseye/README.md) を参照し、`index.json` → `caps/*.json` → `hot.json` の順で読み込む。`git log --name-only --since="30 days ago" | sort | uniq -c` などで直近の接触頻度を確認し、index に含まれる優先ノードを抽出して Hot リストへ理由付きで列挙する。すべての JSON で `generated_at` とノードの `mtime` を揃え、関連する Capsule の `deps_in/out` とテストコマンドを同期する。更新結果や検証ログは直近の Task Seed（例: [`TASK.2025-10-19-0001.md`](../TASK.2025-10-19-0001.md)）へ記録し、Guardrails チェックリストと合わせてレビューする。
- CHANGELOG 更新手順: [`README.md#変更履歴の更新ルール`](../README.md#%E5%A4%89%E6%9B%B4%E5%B1%A5%E6%AD%B4%E3%81%AE%E6%9B%B4%E6%96%B0%E3%83%AB%E3%83%BC%E3%83%AB)（完了済みタスクは `[Unreleased]` に移管し、ロードマップや `TASK.*.md` の重複を解消する）。

本ハブは開発フェーズ毎に更新し、未作成 ADR や追加仕様が発生した際は本書内のロードマップを最新化してください。

## ライセンスと配布物チェック

- [`LICENSE`](../LICENSE)
- Chainlit 由来の告知と本フォークの改変概要をまとめた [`NOTICE`](../NOTICE)
- リリース成果物（バイナリ / Docker イメージ / アーカイブ）には `LICENSE` と `NOTICE` を必ず同梱し、手順は [`docs/Release_Checklist.md`](Release_Checklist.md) を参照
- `NOTICE` の内容（派生元告知・著作権表記・主要改変点）が最新かを確認し、配布前に更新した場合は Release PR で周知する

## 5. Guardrails ドキュメント更新フロー

1. 設計変更を検討したら `BLUEPRINT.md` で影響範囲と担当ロールを確認し、目的・スコープ・I/O・AC を見直したドラフトへ落とし込んで個人運用で実施可能な手順へ分解する。
2. 実装・運用手順の変更は `RUNBOOK.md` と `CHECKLISTS.md` を同時に更新し、準備→実行→検証 / Dev→PR→Release→Ops の順序と担当ロールのチェック項目を維持する（同一人物でも帽子を被り替えてレビューする）。
3. 受入条件や計測指標の変更は `EVALUATION.md` と Task Seed（`TASK.<YYYY-MM-DD>-0001.md` など）に同期し、証跡取得コマンドや個人実行で得たログへのリンクを追記する。
4. 変更差分を Pull Request にまとめ、[`CONTRIBUTING.md#guardrails-ドキュメント更新フロー`](../CONTRIBUTING.md#guardrails-%E3%83%89%E3%82%AD%E3%83%A5%E3%83%A1%E3%83%B3%E3%83%88%E6%9B%B4%E6%96%B0%E3%83%95%E3%83%AD%E3%83%BC) のレビュー手順に従って証跡確認とチェックリスト更新を行う。
5. Birdseye 図および Guardrails 原典（`third_party/Day8/workflow-cookbook/HUB.codex.md` / `third_party/Day8/workflow-cookbook/GUARDRAILS.md` / `third_party/Day8/workflow-cookbook/BLUEPRINT.md`）を照合し、役割や手順の齟齬がないことを最終確認する。
