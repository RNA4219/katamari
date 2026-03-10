# ADR-0001: Chainlit リポジトリを git subtree として取り込む

## Context
- 背景: Katamari は Chainlit/chainlit をベースに多数の独自拡張を加えている。
- 制約: upstream 追従と独自差分の衝突を最小化しつつ、公式リポジトリへの貢献も継続したい。
- 参考資料: [`docs/UPSTREAM.md`](../UPSTREAM.md), [`docs/FORK_NOTES.md`](../FORK_NOTES.md)。

## Decision
- 方針: `git subtree add --prefix upstream/chainlit https://github.com/Chainlit/chainlit main` で取り込み、以後も `git subtree pull` で同期する。
- 採用理由: subtree は履歴と差分を保ったまま上流の更新を取り込めるため、独自改修と upstream の両立が容易になる。
- 運用: Katamari 側の恒久的変更は `core_ext/`, `providers/`, `themes/` など専用ディレクトリに配置し、`upstream/chainlit/` 直下には直接コミットしない。upstream に還元したい修正は本家 PR を経由する。

## Consequences
- 影響範囲: 差分管理が `git subtree` ログで可視化され、週次同期フロー（`docs/UPSTREAM.md`）と整合する。
- 利点: 独自改修が専用ディレクトリに集約され、upstream 更新時のマージ衝突が減る。
- リスク/フォローアップ: subtree 更新は履歴が膨らむため、タグ単位での取り込みと squash merge 禁止を徹底する必要がある。自動化スクリプトの更新漏れがないよう CI チェックリストへ項目を追加する。

## Status
- ステータス: 承認済み
- 最終更新日: 2025-02-14

## DoD
- [ ] `upstream/chainlit/` を subtree として初期化済みであること。
- [ ] フォーク運用手順（`docs/UPSTREAM.md`, `docs/FORK_NOTES.md`）が本 ADR と整合していること。
- [ ] `scripts/sync_chainlit_subtree.sh --prefix <path> --repo <repository> --tag <tag> [--remote <remote>]` の使い方と `--dry-run` フローが [`docs/UPSTREAM.md`](../UPSTREAM.md#%E6%9B%B4%E6%96%B0%E5%8F%96%E3%82%8A%E8%BE%BC%E3%81%BFgit-subtree-pull) に明文化され、Task Seed（[`TASK.2025-10-19-0001.md`](../tasks/TASK.2025-10-19-0001.md)）から辿れること。
- [ ] CI（[`ci.yml`](../../.github/workflows/ci.yml)）の `pytest` ジョブで `tests/scripts/test_sync_chainlit_subtree.py` を実行し、`--dry-run` のコマンド表示とエラー伝播を継続検証できていること。失敗時はフォローアップ Issue を起票する運用が確立していること。
