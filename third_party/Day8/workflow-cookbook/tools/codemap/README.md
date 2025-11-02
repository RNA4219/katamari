# codemap ツール

`codemap.update` は Birdseye のインデックスおよびカプセルを再生成するコマンドです。現時点ではローカル実行を前提としており、以下の手順で最新化します。

## 依存

- Python 3.11 以上
- 追加の外部ライブラリは不要（標準ライブラリのみで実行できます）

## 実行手順

1. （任意）仮想環境を作成し、有効化します。
2. リポジトリルートで次のコマンドを実行します。

   ```bash
   python third_party/Day8/workflow-cookbook/tools/codemap/update.py --targets docs,src --emit index+caps
   ```

   - `--targets` には再生成したい Birdseye リソースをカンマ区切りで指定します。
   - `--emit` には出力したい成果物（`index` / `caps` / `index+caps`）を指定します。
3. 実行後、以下の成果物が更新されます。
   - `docs/birdseye/index.json`
   - `docs/birdseye/caps/*.json`

## Birdseye 再生成スクリプト

`update.py` は Birdseye の再生成処理を司るエントリーポイントです。現状は雛形実装であり、各ターゲットの解析や JSON 生成ロジックを実装する必要があります。詳細な処理を追加する際は、既存の例外設計・型安全方針に従って実装してください。解析対象のファイル拡張子の検証も追加されており、サポート外のパス（例: `.json`）を指定した場合は例外を送出して既存成果物を保護します。

- CLI エントリ: `python third_party/Day8/workflow-cookbook/tools/codemap/update.py ...`
- 未実装箇所は `TODO` コメントで明示しています。今後の拡張時に置き換えてください。
