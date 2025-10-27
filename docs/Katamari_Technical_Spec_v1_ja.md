# Katamari 技術仕様書 v1
**Status: 2025-10-19 JST / Initial**

## 1. アーキテクチャ
- **Fork**：Chainlit本体（Apache-2.0）最新安定を追従
- **差分**：`src/app.py`（薄い配線）＋ `src/core_ext/`（機能群）＋ `src/providers/`（OpenAI/Gemini）
```
repo
├─ src/
│  ├─ app.py
│  ├─ core_ext/
│  │  ├─ persona_compiler.py
│  │  ├─ context_trimmer.py
│  │  ├─ prethought.py
│  │  ├─ multistep.py
│  │  ├─ logging.py        # 実行ログ集約
│  │  ├─ retention.py
│  │  └─ evolve.py
│  └─ providers/
│     ├─ openai_client.py
│     └─ google_gemini_client.py
└─ docs / config
```

**備考**：`src/core_ext/retention.py` は Trim 実行時に保持率を算出し、`METRICS_REGISTRY` へ実測値（埋め込み類似度）を反映する。

## 2. Provider 抽象
```python
class ProviderClient(Protocol):
    async def stream(self, model: str, messages: list[dict], **opts) -> AsyncIterator[str]: ...
    async def complete(self, model: str, messages: list[dict], **opts) -> str: ...
```
- Thinking系は `_REASONING_DEFAULT` に基づく `reasoning` を既に常時付与しており、`effort` は常に `"medium"` へ初期化される
  - 並列対応モデル（`gpt-5-thinking`, `gpt-5-thinking-pro`、および `config/model_registry.json` で `parallel: true` 指定された ID）は `parallel: true` を維持
  - 並列非対応モデルでは `parallel` を除去し、`effort` のみを継承する
  - ユーザ入力で `reasoning` が渡された場合は当該設定を尊重しつつ、非対応モデルでは `parallel` を削除してシリアル化する

## 3. 前処理
- **Persona**：YAML→System変換。禁則語検査（正規表現リスト）
- **Trim**：最後Nターン保持。保持率は Trim 後の埋め込み類似度から算出し、`semantic_retention` を `/metrics` と CLI (`scripts/perf/collect_metrics.py`) に流す。欠損・計算失敗時は Prometheus では `NaN`、CLI では JSON `null` を返す。
- **Prethought**：`目的/制約/視点/期待` への分解（テンプレプロンプト）

## 4. チェーン制御
- `reflect = ["draft","critique","final"]`
- Step境界で`system`メッセージに段階ヒントを追加（短く・安全に）

## 5. 評価器（M2）
- **BERTScore**：`xlm-roberta-large` 既定（軽量化にfallback用モデルを併設）※M2予定・現状未実装。
- **ROUGE**：`rouge-l`, `rouge-1/2`、日本語は正規化ベースから開始
- **ルール**：語彙一致・構造検査（JSON/Markdown/字数）

## 6. 性能目標
- p95 初回トークン ≤ 1.0s（近接リージョン・*-mini推奨）
- UI反映延滞 ≤ 300ms
- ストリーミング連続 1 分以上（切断率 < 1%）

## 7. セキュリティ
- ENV キーのみ使用、フロント露出なし
- `CHAINLIT_AUTH_SECRET` を共通シークレットとし、`Authorization: Bearer <token>` を要求
  - `/healthz` と `/metrics` は上記ヘッダを検証して 401/200 を切り替える
  - RUNBOOK（`RUNBOOK.md`）ではシークレットのローテーションと Bearer 発行手順を記載済み
- CORS 制限・Rate Limit・HTTPS はプロキシ層での適用を 8章デプロイで管理
- OAuth など追加認証フローは `TASK.2025-10-19-0002.md` で扱う範囲に留め、本仕様では Bearer 認証を基準とする

## 8. デプロイ
- dev: `chainlit run src/app.py --host 0.0.0.0 --port 8787`
- prod: Docker/Helm（M3）、リバースプロキシでHTTP/2・Keep-Alive

## 9. 受け入れ試験（抜粋）
- Settings反映・Trim圧縮率・Reflect順序・Header/Bearer 認証（`CHAINLIT_AUTH_SECRET` に基づく `/healthz`・`/metrics` の 401/200 切替と RUNBOOK 記載手順との整合）・メトリクス出力（`semantic_retention` は埋め込み類似度から算出した実測値を `/metrics` で露出し、欠損時は Prometheus では `NaN`、CLI/JSON では `null` を返す）

[^oauth-task]: OAuth など追加認証方式は `TASK.2025-10-19-0002.md` にて検討する。
