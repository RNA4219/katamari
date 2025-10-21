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
│  │  └─ evolve.py
│  └─ providers/
│     ├─ openai_client.py
│     └─ google_gemini_client.py
└─ docs / config
```

## 2. Provider 抽象
```python
class ProviderClient(Protocol):
    async def stream(self, model: str, messages: list[dict], **opts) -> AsyncIterator[str]: ...
    async def complete(self, model: str, messages: list[dict], **opts) -> str: ...
```
- Thinking系は `reasoning` パラメタ（例：`{"reasoning":{"effort":"medium","parallel":true}}`）
  - ※ 現状は未対応（M2 以降で段階導入予定）

## 3. 前処理
- **Persona**：YAML→System変換。禁則語検査（正規表現リスト）
- **Trim**：最後Nターン保持（M1で保持率推定：埋め込み類似度 ※保持率算出は未実装・計画中）
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
- `CHAINLIT_AUTH_SECRET`、CORS制限、Rate Limit、HTTPS
  - **現状**：上記の CORS / Rate Limit / HTTPS / `CHAINLIT_AUTH_SECRET` は未導入。詳細は `TASK.2025-10-19-0002.md`（認証導入タスク）を参照。
  - **実装後に更新すべき項目**：
    - 本節の導入状況と設定内容
    - 8章「デプロイ」のプロダクション要件（TLS終端 / Rate Limit 運用）
    - RUNBOOK の運用手順（認証シークレットのローテーション）

## 8. デプロイ
- dev: `chainlit run src/app.py --host 0.0.0.0 --port 8787`
- prod: Docker/Helm（M3）、リバースプロキシでHTTP/2・Keep-Alive

## 9. 受け入れ試験（抜粋）
- Settings反映・Trim圧縮率・Reflect順序・Header/OAuth・メトリクス出力（`semantic_retention` は未実装・計画中）
