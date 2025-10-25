# 付録A: 用語集・記法（Katamari）
**Status: 2025-10-19 JST**

- **Prethought（前思考）**: 目的・制約・視点・期待など、入力を解釈する前段の構造化。
- **Persona**: YAMLで定義するアシスタントの口調・禁則・補足ノート。System Promptへコンパイル。
- **Trim**: 会話履歴の圧縮。目標トークン以下に収め、保持率を高く保つ。
- **Reflect Chain**: `draft → critique → final` の段階推論。
- **Retention（保持率）**: 圧縮前後の意味類似度（0.0–1.0）。M1 で埋め込み類似度を導入済みで、`/metrics` から実測値を取得する（Header 認証導入まではネットワーク制御で保護）。
- **Evaluator**: 出力品質評価器（BERTScore / ROUGE / ルール）。※M2予定・現状未導入。
- **Provider**: OpenAI/Gemini 等のモデル提供者。抽象クライアント層で吸収。
- **SSE**: Server-Sent Events。ストリーミングでトークンを増分表示。
- **p95 初回トークン**: リクエスト開始から最初のトークン受信までの95パーセンタイル。
