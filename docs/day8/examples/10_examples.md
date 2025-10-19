# サンプル

## test.yml（サブディレクトリ対応）
```yaml
name: test
on:
  push:
    branches: ["**"]
  pull_request:
defaults:
  run:
    working-directory: workflow-cookbook
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests (dummy)
        run: |
          mkdir -p logs
          echo '{"name":"ok","status":"pass","duration_ms":120}' >> logs/test.jsonl
          echo '{"name":"ng","status":"fail","duration_ms":900}' >> logs/test.jsonl
      - name: Upload logs
        uses: actions/upload-artifact@v4
        with:
          name: test-logs
          path: workflow-cookbook/logs
```

## reflection.yml（連動）
```yaml
name: reflection
on:
  workflow_run:
    workflows: ["test"]
    types: [completed]
defaults:
  run:
    working-directory: workflow-cookbook
jobs:
  reflect:
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: write
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: test-logs
          run-id: ${{ github.event.workflow_run.id }}
          path: .

      # アーティファクト取得には permissions.actions: read が必要です。
      # 別リポジトリや手動指定の run を参照する場合は、下記のように repository/run-id/github-token を明示しないと
      # "Artifact not found" エラーになります。ダウンロードには permissions.actions: read が必須で、github-token には
      # actions: read を付与した PAT を渡してください。
      #- uses: actions/download-artifact@v4.1.7
      #  with:
      #    repository: owner/repo
      #    run-id: 1234567890
      #    name: test-logs
      #    path: .
      #    github-token: ${{ secrets.CROSS_REPO_PAT }}
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Analyze logs → report
        run: |
          python scripts/analyze.py
      - name: Commit report
        run: |
          git config user.name "reflect-bot"
          git config user.email "bot@example.com"
          git add reports/today.md
          git commit -m "chore(report): reflection report [skip ci]" || echo "no changes"
          git push || true
```

> `defaults.run.working-directory` で `workflow-cookbook` を指定しているため、アーティファクトは `path: .` でワークスペース直下に展開され、スクリプトは `python scripts/analyze.py` として呼び出します。
> 同じ理由でレポートのステージングは `git add reports/today.md` として実行します。

## analyze.py（骨子）
- JSONLを読み、合格率・p95・失敗数を算出
- Why-Why 草案と Issue 候補を出力
