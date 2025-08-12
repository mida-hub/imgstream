# code quality check

- コード品質は下記のコマンドを使ってチェックしてください
- src 配下のファイルを更新した時はコード品質をチェックしてください
- tests 配下のファイルは ruff と mypy の対象外としてください

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
