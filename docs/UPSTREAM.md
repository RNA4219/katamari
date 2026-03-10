# UPSTREAM 取り込み方針（Katamari）
- Upstream: Chainlit/chainlit（Apache-2.0）
- 追従ポリシー: 最新安定タグを週次でチェックし取り込み
- 直近開始日時: 2025-10-19 JST
- 差分は [`src/core_ext/`](../src/core_ext/) に隔離、`src/app.py` は薄い配線のみ。

## Git subtree 運用手順

### 初回導入（`git subtree add`）
1. upstream remote を登録
   ```bash
   git remote add chainlit https://github.com/Chainlit/chainlit.git
   git fetch chainlit --tags
   ```
2. 取り込み対象タグを確認（例: `v1.2.3`）
   ```bash
   git tag -l 'v*' --sort=-v:refname | head
   ```
3. [`upstream/chainlit`](../upstream/chainlit/) にサブツリーを追加
   ```bash
   git subtree add --prefix=upstream/chainlit chainlit v1.2.3 --squash
   ```
4. 競合が発生した場合は一旦 `git status` で対象ファイルを洗い出し、[`src/core_ext/`](../src/core_ext/) 側を優先しつつ最小修正で整合。

### 更新取り込み（`git subtree pull`）
1. `scripts/sync_chainlit_subtree.sh` のドライランで実行内容を確認
   ```bash
   scripts/sync_chainlit_subtree.sh \
    --prefix upstream/chainlit \
     --repo https://github.com/Chainlit/chainlit.git \
     --tag v1.2.4 \
     --dry-run
   ```
   - `--repo` はリモート名または URL、`--prefix` はサブツリー配置先を指定する。
   - fetch 元を既存リモートに固定したい場合は `--remote upstream` のように上書きする。
2. 出力に問題がなければ `--dry-run` を外して同期
   ```bash
   scripts/sync_chainlit_subtree.sh \
    --prefix upstream/chainlit \
     --repo https://github.com/Chainlit/chainlit.git \
     --tag v1.2.4
   ```
3. 競合発生時は以下の手順で解消
   ```bash
   git mergetool  # or 手動編集
   git add <conflicted-files>
   git commit --amend --no-edit
   ```
   - [`src/core_ext/`](../src/core_ext/) 外へ波及しない差分に抑制
   - 必要に応じて upstream 側修正内容をコメントで明示

> メモ: GitHub Actions [`ci.yml`](../.github/workflows/ci.yml) の `pytest` ジョブで `tests/scripts/test_sync_chainlit_subtree.py` を実行し、ドライラン挙動を継続検証する。Task Seed からの導線は [`TASK.2025-10-19-0001.md`](tasks/TASK.2025-10-19-0001.md) を参照。

## 週次チェック運用フロー

- **担当**: リポジトリオーナー（実施責任） + AI アシスタント（差分整理・記録補助）。外部メンバーは想定しない。
- **スケジュール**: 毎週火曜 09:30 JST に開始し、同日 12:00 JST までに記録を確定。都合により前倒し・後ろ倒しする場合は `docs/UPSTREAM_WEEKLY_LOG.md` の該当エントリに理由と再開予定を残す。
- **実施手順**:
  1. `docs/UPSTREAM_WEEKLY_LOG.md` の最新エントリを複製し、日付・担当・進捗欄を更新する。
  2. `git fetch chainlit --tags` と `git tag -l 'v*' --sort=-v:refname | head` で最新タグを把握し、候補をログ欄に控える。
  3. Release Note の要点と想定影響を AI に要約させ、主要論点をログへ転記する。
  4. `git diff <prev_tag>..<target_tag>` で影響領域を確認し、[`src/core_ext/`](../src/core_ext/) へ波及する論点をログの「差分メモ」に整理する。
  5. テスト・動作確認の要否を判断し、実施内容と結果をログの専用欄にまとめる。
  6. チェックリストを参照しながらログを埋め、完了後に AI に整合チェックを依頼する。

### 差分検証チェックリスト（リポジトリ内完結）
- [ ] `docs/UPSTREAM_WEEKLY_LOG.md` に該当週のエントリを作成し、日付・担当・対象タグ候補・比較元タグを記入
- [ ] `docs/UPSTREAM_WEEKLY_LOG.md` のリリースノート要約欄に breaking change の有無と対処方針を記入
- [ ] 同エントリの差分メモ欄に [`src/core_ext/`](../src/core_ext/) 影響点と依存更新の要否を記入
- [ ] テスト・検証欄に実施可否と結果（未実施理由含む）を記入
- [ ] 「レビュー記録」欄を設け、自己レビュー所見と AI レビュー所見、後続タスクが必要なら `docs/TASKS.md` 等リポジトリ内ドキュメントへのリンクを記入

## 差分隔離方針とレビュー

| レイヤ | 内容 | Chainlit 更新時の扱い | レビュー観点 |
| --- | --- | --- | --- |
| [`upstream/chainlit`](../upstream/chainlit/) | Upstream ソースのミラー | `git subtree` でタグ単位取り込み。直接編集禁止 | Upstream 差分の妥当性、`--squash` による履歴圧縮確認 |
| `src/core_ext/patches` | 独自パッチ（必要最小限） | Chainlit 側で未解決の issue を暫定補正（必要に応じて当該ディレクトリを作成） | Patch 適用順序と upstream へのフィードバック計画 |
| `src/app.py` / `src/` | 自前コード | [`src/core_ext/`](../src/core_ext/) の公開 API のみ利用 | 依存逆流が無いこと、例外設計遵守 |

### レビューフロー
1. 担当者が自己レビューを実施し、`docs/UPSTREAM_WEEKLY_LOG.md` の「レビュー記録」欄に自己レビュー完了時刻と確認内容を残す
2. AI アシスタントにログと差分を共有し、AI 所見を同欄へ追記してもらう（不足事項・追加検証の指摘を含む）
3. 担当者が AI 所見を反映して差分とログを更新し、再自己レビューの結果を同欄に追記して完了印とする
4. マージ後は翌営業日までに当該エントリへリリース状況を追記し、必要なフォローアップをリポジトリ内ドキュメント（例: [`docs/TASKS.md`](./TASKS.md#upstream-follow-up)）へ記録する
