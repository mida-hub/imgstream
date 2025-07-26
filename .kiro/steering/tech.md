# code quality check

コード品質は下記のコマンドを使ってチェックしてください

```bash
ENVIRONMENT=production uv run pytest
ENVIRONMENT=production uv run black
ENVIRONMENT=production uv run ruff
ENVIRONMENT=production uv run mypy
```
