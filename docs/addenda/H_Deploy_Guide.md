# 付録H: デプロイガイド（簡易）
**Status: 2025-10-19 JST**

## H-1. 開発
```bash
pip install --upgrade "openai>=1.30.0" chainlit google-generativeai numpy pyyaml tiktoken plotly
export OPENAI_API_KEY=sk-...
export GOOGLE_GEMINI_API_KEY=...
# 旧称 `GEMINI_API_KEY` も読み取り互換としてサポートされています。
chainlit run src/app.py --host 0.0.0.0 --port 8787
```

`google-generativeai` は Gemini 利用時に、`openai` は OpenAI 利用時に必須です。特に `openai` は旧版が残っていると AsyncOpenAI が提供されず失敗するため、最低でも 1.30.0 へアップグレードしてください。

上記パッケージ構成は `requirements.txt` と同一です。`plotly` についても `plotly>=5.18.0,<6.0.0` を指定しています。

## H-2. Docker（M3）
```Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
ENV PORT=8787
EXPOSE 8787
ENTRYPOINT ["chainlit","run"]
CMD ["src/app.py","--host","0.0.0.0","--port","8787"]
```

> **運用注意（2025-10-23 現在）**：`/healthz` `/metrics` は HTTP ヘッダー `Authorization: Bearer <CHAINLIT_AUTH_SECRET>` を必須とします。Chainlit UI 側は引き続き未認証のまま公開されるため、監視トークン配布と OAuth 導入タスク（[`TASK.2025-10-19-0002.md`](../../TASK.2025-10-19-0002.md)）の進捗を常時確認してください。

## H-3. GitHub Actions リリースワークフロー（M3）
- ファイル: `.github/workflows/release.yml`
- トリガー: `v*.*.*` 形式のタグに対する `push`
- 処理内容:
  1. `docker/setup-buildx-action@v3` で Buildx をセットアップ
  2. `docker/login-action@v3` で `ghcr.io` に `GITHUB_TOKEN` を用いてログイン
  3. `docker/metadata-action@v5` で `latest` とタグ名のメタデータを生成
  4. `docker/build-push-action@v5` で `ghcr.io/<owner>/<repo>:latest` とタグ名の 2 つを push

> バージョン更新時は必ず `.github/workflows/release.yml` を参照し、手順との乖離がないか確認すること。
