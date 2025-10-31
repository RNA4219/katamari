# Changelog

このプロジェクトの顕著な変更はこのファイルで管理します。本 changelog は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) の形式と [セマンティック バージョニング](https://semver.org/spec/v2.0.0.html) を採用しています。

> PR 作成時は必ず `[Unreleased]` を更新し、リリース確定時に該当エントリを各バージョン見出しへ移動します。

## 運用ルール
- 詳細な手順は [`README.md#変更履歴の更新ルール`](README.md#%E5%A4%89%E6%9B%B4%E5%B1%A5%E6%AD%B4%E3%81%AE%E6%9B%B4%E6%96%B0%E3%83%AB%E3%83%BC%E3%83%AB) を参照。
- PR では `[Unreleased]` の適切な分類に追記し、不要な分類は削除する。
- 各エントリの先頭に 4 桁ゼロ埋めの通番（例: `0001`）を付け、既存の最大値から 1 ずつ増やす。
- リリース時に対応バージョン見出しへ移し、日付を YYYY-MM-DD 形式で記録する。

## [Unreleased]

### Added
- 0005: CHANGELOG を Keep a Changelog 形式で整備し、README/ロードマップから更新手順へ導線を追加。
### Changed
- 0002: CHANGELOG のエントリに通番を付けるルールを追加。
- 0003: README とロードマップに CHANGELOG 更新導線とタスク移管ルールを明文化。
- 0004: README の主要導線にタスク移管の導線を追記し、完了タスクの CHANGELOG 反映を必須化。
- 0006: OpenAI ストリームの再試行を 1s→2s→4s の backoff と `katamari.request` 計測に対応させ、ログ/RUNBOOK を更新。
### Deprecated
### Removed
### Fixed
### Security

## [0.1.0] - 2024-05-26

### Added
- 0001: ロードマップと仕様索引のハブとして `docs/ROADMAP_AND_SPECS.md` を追加。
