# RUNBOOK

## 目的
- Katamari の起動・検証・障害対応を標準化し、Guardrails とロードマップで定義された要件を逸脱せずに **個人運用** でも再現できるようにする。
- 変更の影響範囲を即座に把握できるよう、起動から復旧までの手順と証跡取得方法を一人で辿れる形で記録する。

## 担当ロール
- 個人運用者（SRE 帽子）: 障害対応と復旧の一次手順を把握し、証跡を残す。
- 個人運用者（DevOps 帽子）: 起動・検証の標準シーケンスを維持し、CI との整合をチェックする。
- 個人運用者（メンテナー帽子）: 運用変更がガードレール手順と矛盾しないかをレビューする。

## スコープ
### In Scope
- ローカル / CI 環境でのアプリ起動と Persona/Trim/Reflect チェーン動作確認。
- SSE 遅延やログ監視、Provider 設定の切替、基本的な障害復旧フロー。
- Guardrails が要求する最小読込・自己検証プロセスの実施。

### Out of Scope
- 24/7 SRE 運用や SLA 監視（別途 Runbook を策定）。
- プロバイダ課金や秘密情報の管理（`docs/addenda/G_Security_Privacy.md` を参照）。

## 手順
Guardrails の「準備→実行→検証」順で進める。

## ガードレール項目
- AI アシスタントから提案を受けた手順は、必ず人が検証し Task Seed に採用可否と判断根拠を記載する。
- `make dev` など副作用の大きいコマンドは仮想環境内で実行し、`RUNBOOK.md` の手順変更はガードレール最小差分原則で行う。
- Secrets を扱う操作は `.env` ローカル管理に限定し、履歴に残さないことを再確認する。
- 障害発生時は `EVALUATION.md` の指標と `CHECKLISTS.md` Ops セクションを同時に更新し、個人+AI の役割分担を明示する。
- Birdseye や Guardrails 文書の更新を伴う場合は同日のコミットにまとめ、`docs/ROADMAP_AND_SPECS.md` へリンクする。

### 1. 準備
1. `python -m venv .venv && source .venv/bin/activate`
2. Python 依存はリポジトリルートで `make dev`（仮想環境内で `pip install -r requirements.txt` を含む）または `pip install -r requirements.txt` を実行して導入する。
3. Node 依存が必要な変更を行う場合は対象ディレクトリへ移動し、例として `cd upstream/chainlit && pnpm install` を実行する。Node 領域を触らない場合はこの手順をスキップし、リポジトリ直下で誤って `npm install` を実行しないよう注意する。詳細は [CONTRIBUTING.md#開発環境セットアップ](CONTRIBUTING.md#開発環境セットアップ) を参照。
4. リポジトリ直下に `.env` を作成し、[`README.md#環境変数一覧`](README.md#%E7%92%B0%E5%A2%83%E5%A4%89%E6%95%B0%E4%B8%80%E8%A6%A7) と同セクションで案内している [`config/env.example`](config/env.example) を基に Provider キーなどの環境変数を設定する。
5. Birdseye index/caps を確認し、必要であれば `python scripts/birdseye_refresh.py --dry-run` で差分を確認してから `python scripts/birdseye_refresh.py` を実行する。単独作業の場合でも更新日時を共通化し、実行結果を Task Seed に記録する。

### 2. 実行
1. `chainlit run src/app.py --watch --host 0.0.0.0 --port 8787`
2. Persona YAML を `personas/` からロードし、UI で切替を検証する。
3. Chainlit の標準出力を監視し、必要に応じて `LOG_LEVEL` を調整しながら `chainlit run --debug`（または `DEBUG=1 chainlit run ...`）で詳細ログを取得する。標準出力は `mkdir -p logs && chainlit run src/app.py --watch --host 0.0.0.0 --port 8787 --debug | tee logs/chainlit.log` のように `tee` を使って保存し、Trim/Reflect チェーンのトークン削減率を記録する。
4. 構造化ログを確認する。ルートロガーを INFO 以上に設定した状態で `katamari.request` 行を抽出し、`jq` などで JSON を整形する。例：`mkdir -p logs && chainlit run src/app.py --watch --host 0.0.0.0 --port 8787 --debug 2>&1 | tee logs/chainlit.log` の後に `grep "katamari.request" logs/chainlit.log | jq -R 'fromjson'` で `req_id`／`token_in`／`token_out`／`compress_ratio`／`step_latency_ms`／`retryable` を確認し、Runbook 記録に添付する。
5. Provider を切り替え、`docs/addenda/F_Provider_Matrix.md` の互換チェックを行う。

### 3. 検証・障害対応
1. `pytest` / `pnpm run test`（必要に応じて `cd upstream/chainlit`）/ `ruff` / `mypy --strict` を実行し、失敗時は Guardrails の最小差分方針で修正する。Cypress ベースの Node テストは `pnpm run test` で網羅的に実施し、単独検証でもログを保管する。
2. SSE 遅延が閾値を超えた場合、`docs/addenda/J_Runbook.md` のトラブルシュート手順を参照する。
3. 重大障害は `CHANGELOG.md` と Task Seed に記録し、必要なら `RUNBOOK.md` を更新する。記録は自分宛の TODO でもよいが日時と判断根拠を残す。
4. CI キャッシュが未ヒットまたは破損した場合は、GitHub Actions の `Python … job metrics` / `Provider smoke job metrics` / `CI workflow summary` でヒット状況と計測値を確認し、`CACHE_VERSION`（`.github/workflows/ci.yml` 冒頭）をインクリメントしたうえで再実行する。ローカルで `python scripts/cache/hash_lockfiles.py --python requirements.txt --node upstream/chainlit/pnpm-lock.yaml --node upstream/chainlit/frontend/pnpm-lock.yaml` を走らせ、ハッシュが想定どおり変化していることを確認してから PR に含める。

## 最小フロー
1. `docs/ROADMAP_AND_SPECS.md` で対象フェーズと関連タスクを特定する。
2. 「準備→実行→検証」の順に手順を辿り、証跡を `CHECKLISTS.md` の該当フェーズへ転記する。
3. 異常があれば `TASK.*.md` にフォローアップを登録し、再発防止策を検討する。
4. 受入判断を `EVALUATION.md` の AC と照合し、満たない場合は再実行計画を記す。
5. `third_party/Day8/workflow-cookbook/GUARDRAILS.md` の「RUNBOOK」節を参照し、標準手順から逸脱していないかレビューする。

## 受入基準
- 起動直後に Persona 選択と Trim/Reflect チェーンが UI に表示される。
- `ruff`・`mypy --strict`・`pytest`・`pnpm run test`（必要に応じて `cd upstream/chainlit`）が成功、またはスキップ理由が記録されている。
- SSE 遅延とトークン削減率が `docs/Katamari_Requirements_v3_ja.md` の目標を満たす。
- Guardrails RUNBOOK の `Procedure / Acceptance` 記述と矛盾がない。

## チェック項目
- [ ] Secrets を含む `.env` をリポジトリに残していない。
- [ ] Guardrails の最小読込手順（README → index.json → caps）を実施した。
- [ ] Birdseye 更新日時が直近コミット以降になっている。
- [ ] 失敗テストの理由と再実行計画が Task Seed に記録されている。
- [ ] Guardrails RUNBOOK 節（`third_party/Day8/workflow-cookbook/GUARDRAILS.md`）の手順と本書のガードレール項目が一致する。
- [ ] AI から提案された運用手順の採用可否を記録し、判断根拠を Task Seed に残した。
- [ ] Chainlit の標準出力を保存（例: `mkdir -p logs && chainlit run ... --debug | tee logs/chainlit.log`）して Trim/Reflect チェーンのログを取得した証跡がある。

## 参照
- [docs/ROADMAP_AND_SPECS.md](docs/ROADMAP_AND_SPECS.md)
- [docs/addenda/J_Runbook.md](docs/addenda/J_Runbook.md)
- [docs/addenda/H_Deploy_Guide.md](docs/addenda/H_Deploy_Guide.md)
- [third_party/Day8/workflow-cookbook/GUARDRAILS.md](third_party/Day8/workflow-cookbook/GUARDRAILS.md)
