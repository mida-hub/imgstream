# 開発ガイド

> **注意**: 基本的なセットアップについては [デプロイメントガイド](DEPLOYMENT_GUIDE.md) を参照してください。このドキュメントは開発固有の詳細をカバーします。

## ローカル開発でのCloud IAP認証問題の解決

ローカル開発環境では、Cloud IAPを通らないため認証エラーが発生します。この問題を解決するため、開発用認証システムを実装しています。

## 解決策

### 1. 開発モード認証

アプリケーションは環境変数 `ENVIRONMENT` の値に基づいて動作モードを切り替えます：

- `development`, `dev`, `local`: 開発モード（Cloud IAPをバイパス）
- `production`: 本番モード（Cloud IAP必須）

### 2. 開発環境での起動方法

#### Docker Composeを使用（推奨）

```bash
# 環境変数ファイルをコピー
cp .env.example .env

# 開発用コンテナを起動
docker-compose --profile dev up imgstream-dev

# ブラウザでアクセス
open http://localhost:8501
```

#### 直接起動

```bash
# 依存関係をインストール
uv sync

# 環境変数を設定
export ENVIRONMENT=development
export DEV_USER_EMAIL=your-email@example.com
export DEV_USER_NAME="Your Name"

# アプリケーションを起動
uv run streamlit run src/imgstream/main.py
```

### 3. 開発認証UI

開発モードでは、サイドバーに開発用認証UIが表示されます：

1. **メールアドレス**: 開発用のメールアドレス
2. **表示名**: 開発用の表示名
3. **ユーザーID**: 開発用のユーザーID

これらの値は環境変数で事前設定できます：

```bash
DEV_USER_EMAIL=developer@example.com
DEV_USER_NAME=Local Developer
DEV_USER_ID=dev-local-001
```

### 4. 環境変数設定

#### 必須設定

```bash
# 開発モードを有効化
ENVIRONMENT=development

# Google Cloud設定
GOOGLE_CLOUD_PROJECT=apps-466614
GCS_REGION=asia-northeast1
GCS_BUCKET=apps-466614-imgstream-photos-dev
```

#### 開発認証設定（オプション）

```bash
DEV_USER_EMAIL=your-email@example.com
DEV_USER_NAME=Your Name
DEV_USER_ID=your-user-id
```

### 5. 開発モードの特徴

#### 視覚的インジケーター
- 画面右上に「🔧 DEV MODE」バッジが表示
- サイドバーに開発モード情報が表示

#### 認証の動作
- Cloud IAPヘッダーをチェックしない
- 開発用ユーザー情報を使用
- 任意のユーザー情報でログイン可能

#### ストレージとデータベース
- 開発用GCSバケットを使用
- ユーザー固有のパスは開発用メールアドレスベース

### 6. トラブルシューティング

#### 認証エラーが続く場合

1. 環境変数 `ENVIRONMENT=development` が設定されているか確認
2. ブラウザのキャッシュをクリア
3. Streamlitアプリケーションを再起動

#### 開発認証UIが表示されない場合

```bash
# 環境変数を確認
echo $ENVIRONMENT

# 開発モードで起動
ENVIRONMENT=development uv run streamlit run src/imgstream/main.py
```

#### ストレージエラーが発生する場合

1. GCS認証情報が設定されているか確認
2. 開発用バケットが存在するか確認
3. サービスアカウントに適切な権限があるか確認

### 7. 本番環境との違い

| 項目 | 開発環境 | 本番環境 |
|------|----------|----------|
| 認証方式 | 開発用UI | Cloud IAP |
| ユーザー情報 | 任意設定可能 | IAPから取得 |
| GCSバケット | `-dev` サフィックス | `-prod` サフィックス |
| ログレベル | DEBUG | INFO |
| エラー表示 | 詳細表示 | ユーザーフレンドリー |

### 8. セキュリティ注意事項

- 開発モードは `ENVIRONMENT` 環境変数でのみ制御
- 本番環境では自動的に無効化
- 開発用認証情報は本番データにアクセス不可
- 開発用バケットは本番バケットと完全分離

### 9. 開発ワークフロー

1. **初回セットアップ**
   ```bash
   cp .env.example .env
   # .envファイルを編集
   docker-compose --profile dev up imgstream-dev
   ```

2. **日常開発**
   ```bash
   # コンテナ起動
   docker-compose --profile dev up imgstream-dev
   
   # ブラウザでアクセス
   open http://localhost:8501
   
   # 開発認証でログイン
   # サイドバーの開発認証UIを使用
   ```

3. **テスト実行**
   ```bash
   # テスト実行
   docker-compose exec imgstream-dev uv run pytest
   
   # コード品質チェック
   docker-compose exec imgstream-dev uv run ruff check .
   docker-compose exec imgstream-dev uv run black .
   docker-compose exec imgstream-dev uv run mypy src/
   ```

この開発環境設定により、Cloud IAPなしでもローカル開発が可能になり、本番環境と同様の機能をテストできます。
