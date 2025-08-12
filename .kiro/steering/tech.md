# code quality check

- コード品質は下記のコマンドを使ってチェックしてください
- src 配下のファイルを更新した時はコード品質をチェックしてください
- tests 配下のファイルは ruff と mypy の対象外としてください
- pytest では現在下記のテストを無視して実行してください
  - --ignore=tests/e2e
  - --ignore=tests/integration
  - --ignore=tests/performance
  - --ignore=tests/security

```bash
ENVIRONMENT=production uv run pytest
uv run black
uv run ruff
uv run mypy
```

# source code path

main.py など、主なソースコードのパスを共有します
指示を出す時はたいてい src/imgstream は省略されます

- src/imgstream/main.py
- src/imgstream/api
- src/imgstream/models
- src/imgstream/services
- src/imgstream/ui
- src/imgstream/utils

# test code

unittest.mock が使えるシーンでは mock を利用してテストコードを作成してください

## 無効化されているテストディレクトリ

以下のテストディレクトリは現在 pyproject.toml で除外されています：

- `tests/performance/` - パフォーマンステスト（開発初期段階のため無効化）
- `tests/security/` - セキュリティテスト（基本機能実装完了後に有効化予定）
- `tests/e2e/` - E2E テスト（統合テスト環境構築後に有効化予定）
- `tests/integration/` - 統合テスト（開発が一段落したら有効化予定）

必要に応じて pyproject.toml の `addopts` から `--ignore=` を削除して有効化できます。
