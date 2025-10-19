# Day8（Eight-Day Starter）

Day8 は「観測 → 反省 → 提案」のループを CI に組み込み、安全に改善サイクルを回すためのスターターセットです。自動修正を行わず、レポートと Issue 提案で止めることで OSS プロジェクトでも安全に導入できます。

このリポジトリを把握する際は、以下の LLM-BOOTSTRAP を起点に参照範囲を絞り込んでください。

<!-- LLM-BOOTSTRAP v1 -->
読む順番:
1. docs/birdseye/index.json  …… ノード一覧・隣接関係（軽量）
2. docs/birdseye/caps/<path>.json …… 必要ノードだけ point read（個別カプセル）

フォーカス手順:
- 直近変更ファイル±2hopのノードIDを index.json から取得
- 対応する caps/*.json のみ読み込み
<!-- /LLM-BOOTSTRAP -->

詳細な構成を確認する際は、上記の導線に沿って必要なドキュメントを順番に参照してください。

## リポジトリ構成
- `docs/` Day8 の仕様・運用・ガバナンスドキュメント集（詳細は [`docs/day8/README.md`](docs/day8/README.md) を参照）。
- `governance/` ポリシー定義や CODEOWNERS などの統制設定。
- `workflow-cookbook/logs/` CI で収集した観測ログ。
- `workflow-cookbook/reports/` 反省結果や Issue 提案レポートの出力先。
- `workflow-cookbook/scripts/` ログ解析やレポート生成のユーティリティ。
- `workflow-cookbook/` Day8 を他リポジトリへ導入する際のワークフロー例。

## セットアップ
Day8 を新しいリポジトリへ導入する際は、[`INSTALL.md`](INSTALL.md) の手順に従ってワークフローや初期ファイルをルートに配置してください。GitHub Actions では `test` → `reflection` → `pr_gate` の順で実行され、安全デチューンされた反省レポートを生成します。

## 使い方のヒント
- 初期状態では `workflow-cookbook/reflection.yaml` の `analysis.max_tokens` が 0 のため LLM 呼び出しは抑制されています。必要に応じて `engine` 設定と合わせて有効化してください。
- 生成されたレポート（`workflow-cookbook/reports/` 配下）と提案を確認し、人間が修正 PR を作成する運用を前提としています。

---
**キーワード**: Day8, safe autonomy, propose-only CI, reflective devops
