# code quality check

- コード品質は下記のコマンドを使ってチェックしてください
- src 配下のファイルを更新した時はコード品質をチェックしてください

```bash
ENVIRONMENT=production uv run pytest
uv run black
uv run ruff
uv run mypy
```
