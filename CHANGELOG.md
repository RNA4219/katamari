# Changelog

このプロジェクトの顕著な変更はこのファイルで管理します。本 changelog は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) の形式と [セマンティック バージョニング](https://semver.org/spec/v2.0.0.html) を採用しています。

> PR 作成時は必ず `[Unreleased]` を更新し、リリース確定時に該当エントリを各バージョン見出しへ移動します。

## 運用ルール
- 詳細な手順は [`README.md#変更履歴の更新ルール`](README.md#%E5%A4%89%E6%9B%B4%E5%B1%A5%E6%AD%B4%E3%81%AE%E6%9B%B4%E6%96%B0%E3%83%AB%E3%83%BC%E3%83%AB) を参照。
- PR では `[Unreleased]` の適切な分類に追記し、不要な分類は削除する。
- 各エントリの先頭に 4 桁ゼロ埋めの通番（例: `0001`）を付け、既存の最大値から 1 ずつ増やす。
- リリース時に対応バージョン見出しへ移し、日付を YYYY-MM-DD 形式で記録する。

## [1.0.0-frozen] - 2026-03-10

### Added
- 0008: ルートフォルダ整理（TASK.*.md を docs/tasks/ に移動、重複 .env.sample を削除）
- 0009: マルチプロバイダー対応（OpenAI, Anthropic, Google Gemini, OpenRouter, Alibaba Cloud）
- 0010: Windows用起動スクリプト start.bat（ポート自動検出機能付き）
- 0011: M1.5 OAuth認証実装（条件付きデコレータ登録、テスト8件追加）

### Security
- 0012: .gitignore に .env を追加し、シークレットの誤コミットを防止

### Note
このリリースをもってプロジェクトを凍結します。今後の開発・メンテナンスは行いません。

## [Unreleased]

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [0.1.0] - 2024-05-26

### Added
- 0001: ロードマップと仕様索引のハブとして `docs/ROADMAP_AND_SPECS.md` を追加。
