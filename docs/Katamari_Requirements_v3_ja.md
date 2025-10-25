# Katamari 要件定義 v3（Forkベース：Chainlit）
**Intent: KATAMARI-AIO-0001**  
**Status: Final v3 – 2025-10-19 JST**

## 固定事項（確定）
- **開始日**：2025/10/19（日）
- **名称**：katamari／UIタイトル：**Katamari (Chainlit Fork)**
- **ENV 名**：`OPENAI_API_KEY`, `GOOGLE_GEMINI_API_KEY`（旧称 `GEMINI_API_KEY` 互換あり）, `DEFAULT_PROVIDER=openai`（将来のマルチプロバイダー切り替え用プレースホルダー／現状未使用）, `DEFAULT_MODEL=gpt-5-main`
- **モデル初期セット**：
  - **GPT-5 系**：`gpt-5-main` / `gpt-5-main-mini` / `gpt-5-thinking` / `gpt-5-thinking-mini` / `gpt-5-thinking-nano` / `gpt-5-thinking-pro`
  - **Gemini 2.5 系**：`gemini-2.5-*` 一式
- **評価器の実装順（難→易）**：**BERTScore → ROUGE → ルールベース** ※M2予定・現状未実装。
- **Upstream**：Chainlit/chainlit（Apache-2.0）最新安定タグを追従

## 0. 概要 / 目的
LLM入出力の基盤機能（前処理・多段推論・人格YAML・最適化）を、**Chainlit実質フォーク**で最短構築する。CLIではなく**軽量リッチUI**（Chainlit）を前面に据え、以下をプラガブルに接続：
- **context-trimmer**（トークン節約）
- **ai-persona-compiler**（YAML→System）
- **prethought-analyzer**（意図/制約/期待の分解）
- **multistep-controller**（draft→critique→final）
- **prompt-evolution**（M2：BERTScore/ROUGE/ルールで評価し進化）※M2予定・現状未実装。

## 1. スコープ
### 1.1 含む
- ChainlitチャットUI（Streaming/Steps/Chat Settings）
- 前処理API：persona-compiler / context-trimmer / prethought
- 実行API：multistep（reflectチェーン）
- 進化API：prompt-evolution（M2以降）
- `/metrics`（Prometheus）と`/healthz` の提供（`/api/models` は計画中），最小ログ

### 1.2 含まない
- 重厚な認証（M1.5でOAuthまで）
- 課金・請求管理
- 画像/音声/アニメ系

## 2. 主要ユースケース
1) Prethought→Persona→Trim→推論→SSE表示  
2) Reflectチェーン：draft→critique→final をStepで可視化  
3) Persona YAML→Systemの即時適用  
4) 履歴肥大化時のTrim（圧縮率・保持率表示）※保持率表示は未実装（計画中）
5) 進化（M2）：評価→最良プロンプト更新

## 3. 機能要件（FR）
- **FR-01**：SSEストリーム（初回トークン p95 ≤ 1.0s）
- **FR-02**：Settings集約：model / chain / trim_tokens / persona_yaml / show_debug
- **FR-03**：Persona YAML→System（禁則チェックログ付）
- **FR-04**：Trim（最後Nターン保持）＋圧縮率表示
- **FR-05**：chain=single|reflect（3段Step表示）
- **FR-06**：ログ：`req_id, model, token_in/out, compress_ratio, step_latency_ms`
  - **注記（2025-10-22 更新）**：`src/core_ext/logging.py` の `StructuredLogger` と `src/app.py` の `REQUEST_LOGGER` が要件フィールド（`req_id`/`model`/`token_in`/`token_out`/`compress_ratio`/`step_latency_ms`/`retryable`/`latency_ms`）を JSON で出力する。検証は `tests/app/test_logging.py` で自動化済み。
- **FR-07**：`/healthz`・`/metrics`（M1以降）
- **FR-08（M2）**：`/evolve`（BERTScore→ROUGE→ルール順） ※M2予定・現状未実装。

## 4. 非機能（NFR）
- UI反映遅延 ≤ 300ms（SSE→描画）
- SSE自動再接続（指数バックオフ、最大3回）※計画中。2025-10-22 現在は未実装であり、対応方針は今後起票予定の Task Seed「SSE自動再接続実装」を参照。
- 認証：M1 Header Auth → M1.5 OAuth（`CHAINLIT_AUTH_SECRET`）
- **注記（2025-10-19 現在）**：Header Auth/OAuth は未実装で、現行リリースは Chainlit 既定の無認証挙動。対策タスクは [`TASK.2025-10-19-0002.md`](../TASK.2025-10-19-0002.md) を参照。
- Upstream追従：週次、差分は `core_ext/` に隔離

## 5. データモデル（抜粋）
```ts
type Role = "system" | "user" | "assistant";
interface Message { role: Role; content: string; }
interface ChainSpec { id: string; name: string; steps: string[]; } // ["draft","critique","final"]
# Persona YAML
name: string
style: string
forbid: [string, ...]
notes: |
  ...
# Trim Response
{ messages: Message[], metrics: { input_tokens:number, output_tokens:number, compress_ratio:number, semantic_retention?:number /* Trim 後の埋め込み類似度を実測で格納（-1.0〜1.0）。欠損時は `null` を許容 */ }, note?: string }
```

## 6. 受け入れ基準（AC）
- AC-01：Settings更新→即System差替・ログ出力
- AC-02：Trim実行→`compress_ratio` 表示（0.3–0.8）※保持率は UI 未表示だが `/metrics` では埋め込み由来の実測値（`-1.0〜1.0`、欠損時 `null`）を提供
- AC-03：reflect 3段の順序でストリーム可視化
- AC-04：M1でHeader Auth→M1.5でOAuth有効化
- **注記（2025-10-19 現在）**：上記認証要件は未着手のため、当面は Chainlit 既定の無認証挙動を継続する。対応後に本注記を撤回すること（[`TASK.2025-10-19-0002.md`](../TASK.2025-10-19-0002.md)）。
- AC-05：Apache-2.0遵守（LICENSE/NOTICE/変更点）

## 7. マイルストーン / 工数（1名）
- **M0（6h）**：Settings/SSE/Trim/Persona簡易/Reflect/最小ログ（`/healthz`・`/metrics` 実装）
- **M1（8h）**：prethought・保持率推定（埋め込み）・`/metrics`・Header Auth・Healthz ※保持率は UI 未表示／`/metrics` は実測値（`-1.0〜1.0`、欠損時 `null`）
- **M1.5（4–6h）**：OAuth・厳密トークンカウント・UI微調整
- **M2（12–16h）**：prompt-evolution（BERTScore→ROUGE→ルール）・スコアボード ※M2予定・現状未実装。
- **M2.5（8–12h 任意）**：Postgres永続化
- **M3（6–8h）**：Docker/Helm/CI・FORK_NOTES/UPSTREAM整備
**合計**：36–46h（約4.5〜6営業日）

## 8. OSS未使用（フルスクラッチ）の場合の工数
- M1.5相当：46–62h
- M3相当合算：80–110h
→ フォーク（Chainlit）で**半分以下**に圧縮。

## 9+. 追加章（Addenda）
- 付録A: 用語集・記法 → `docs/addenda/A_Glossary.md`
- 付録B: UIモック → `docs/addenda/B_UI_Mock.md`
- 付録C: Persona YAML スキーマ → `docs/addenda/C_Persona_Schema.md`
- 付録D: Trim 設計詳細 → `docs/addenda/D_Trim_Design.md`
- 付録E: 評価器詳細 → `docs/addenda/E_Evaluator_Details.md`
- 付録F: Provider互換表 → `docs/addenda/F_Provider_Matrix.md`
- 付録G: セキュリティ&プライバシー → `docs/addenda/G_Security_Privacy.md`
- 付録H: デプロイガイド → `docs/addenda/H_Deploy_Guide.md`
- 付録I: テストケース集 → `docs/addenda/I_Test_Cases.md`
- 付録J: 障害時復旧（Runbook） → `docs/addenda/J_Runbook.md`
- 付録K: アクセシビリティ/UX → `docs/addenda/K_Accessibility_UX.md`
- 付録L: 設定リファレンス → `docs/addenda/L_Config_Reference.md`
- 付録M: バージョニング&リリース → `docs/addenda/M_Versioning_Release.md`
