# 付録G: セキュリティ & プライバシー指針
**Status: 2025-10-19 JST**

- **キー管理**: `OPENAI_API_KEY` / `GOOGLE_GEMINI_API_KEY`（旧称 `GEMINI_API_KEY` 互換） はサーバENVのみ。フロント送出禁止。
- **ログ衛生**: 個人情報（PII）はマスク。必要最小限のフィールドのみ収集。
- **データ保持**: デフォルトはメモリ保持。M2.5以降でDB導入時は保持期間・削除APIを設計。
- **認証**: M1 時点では Bearer Header 認証のみ実装。`Authorization: Bearer <token>` で送付された値が `CHAINLIT_AUTH_SECRET` と一致しない場合、`/healthz` `/metrics` を含む保護エンドポイントは 401 で拒否される。M1.5 で OAuth、以降のマイルストーンで Rate limit を導入予定（いずれも未実装）。
- **通信**: HTTPS / HTTP/2 / Keep-Alive。CORS制限。（現状は Chainlit 既定の HTTP（`chainlit run src/app.py --host 0.0.0.0 --port 8787`）のみで運用しており、HTTPS / HTTP/2 / CORS 対応は将来導入予定）
