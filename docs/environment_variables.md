# ImgStream 環境変数設定ガイド

## 概要

ImgStreamアプリケーションは、設定を環境変数で管理します。このドキュメントでは、必要な環境変数とその設定方法について説明します。

## 必須環境変数

### Google Cloud Storage 設定

#### `GCS_PHOTOS_BUCKET`
- **説明**: 写真とサムネイルを保存するGCSバケット名
- **例**: `my-app-photos-bucket`
- **用途**:
  - オリジナル写真の保存
  - サムネイル画像の保存
  - 写真関連のメタデータファイル

#### `GCS_DATABASE_BUCKET`
- **説明**: データベースファイルを保存するGCSバケット名
- **例**: `my-app-database-bucket`
- **用途**:
  - DuckDBデータベースファイルの保存
  - データベースバックアップの保存
  - 同期用のデータベースファイル

#### `GOOGLE_CLOUD_PROJECT`
- **説明**: Google Cloud PlatformのプロジェクトID
- **例**: `my-gcp-project-id`
- **用途**: GCS認証とリソースアクセス

### 認証設定

#### `GOOGLE_APPLICATION_CREDENTIALS`
- **説明**: GCPサービスアカウントキーファイルのパス
- **例**: `/path/to/service-account-key.json`
- **用途**: GCS APIの認証

## オプション環境変数

### アプリケーション設定

#### `ENVIRONMENT`
- **説明**: 実行環境の指定
- **デフォルト**: `development`
- **選択肢**: `development`, `test`, `production`
- **例**: `production`

#### `LOG_LEVEL`
- **説明**: ログレベルの設定
- **デフォルト**: `INFO`
- **選択肢**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **例**: `DEBUG`

### データベース設定

#### `DATABASE_TYPE`
- **説明**: 使用するデータベースタイプ
- **デフォルト**: `duckdb`
- **選択肢**: `duckdb`, `postgresql`
- **例**: `duckdb`

#### `LOCAL_DB_PATH`
- **説明**: ローカルDuckDBファイルのパス
- **デフォルト**: `./data/imgstream.db`
- **例**: `/app/data/metadata.db`

### Streamlit設定

#### `STREAMLIT_SERVER_PORT`
- **説明**: Streamlitサーバーのポート番号
- **デフォルト**: `8501`
- **例**: `8080`

#### `STREAMLIT_SERVER_ADDRESS`
- **説明**: Streamlitサーバーのアドレス
- **デフォルト**: `0.0.0.0`
- **例**: `localhost`

### 衝突検出設定

#### `COLLISION_CACHE_TTL_SECONDS`
- **説明**: 衝突検出キャッシュの有効期限（秒）
- **デフォルト**: `300` (5分)
- **例**: `3600` (1時間)

#### `COLLISION_CACHE_MAX_ENTRIES`
- **説明**: 衝突検出キャッシュの最大エントリ数
- **デフォルト**: `10000`
- **例**: `50000`

#### `COLLISION_DETECTION_BATCH_SIZE`
- **説明**: 衝突検出のバッチサイズ
- **デフォルト**: `100`
- **例**: `500`

### 監視設定

#### `MONITORING_ENABLED`
- **説明**: 監視機能の有効/無効
- **デフォルト**: `true`
- **選択肢**: `true`, `false`
- **例**: `false`

#### `MONITORING_EVENT_RETENTION_DAYS`
- **説明**: 監視イベントの保持期間（日）
- **デフォルト**: `30`
- **例**: `90`

## 環境別設定例

### 開発環境 (.env.development)

```bash
# 環境設定
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Google Cloud設定
GOOGLE_CLOUD_PROJECT=my-dev-project
GOOGLE_APPLICATION_CREDENTIALS=./keys/dev-service-account.json
GCS_PHOTOS_BUCKET=my-app-dev-photos
GCS_DATABASE_BUCKET=my-app-dev-database

# データベース設定
DATABASE_TYPE=duckdb
LOCAL_DB_PATH=./data/dev_imgstream.db

# Streamlit設定
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=localhost

# 衝突検出設定
COLLISION_CACHE_TTL_SECONDS=300
COLLISION_CACHE_MAX_ENTRIES=1000
COLLISION_DETECTION_BATCH_SIZE=50

# 監視設定
MONITORING_ENABLED=true
MONITORING_EVENT_RETENTION_DAYS=7
```

### テスト環境 (.env.test)

```bash
# 環境設定
ENVIRONMENT=test
LOG_LEVEL=INFO

# Google Cloud設定
GOOGLE_CLOUD_PROJECT=my-test-project
GOOGLE_APPLICATION_CREDENTIALS=./keys/test-service-account.json
GCS_PHOTOS_BUCKET=my-app-test-photos
GCS_DATABASE_BUCKET=my-app-test-database

# データベース設定
DATABASE_TYPE=duckdb
LOCAL_DB_PATH=./data/test_imgstream.db

# 衝突検出設定
COLLISION_CACHE_TTL_SECONDS=600
COLLISION_CACHE_MAX_ENTRIES=5000
COLLISION_DETECTION_BATCH_SIZE=100

# 監視設定
MONITORING_ENABLED=true
MONITORING_EVENT_RETENTION_DAYS=14
```

### 本番環境 (.env.production)

```bash
# 環境設定
ENVIRONMENT=production
LOG_LEVEL=WARNING

# Google Cloud設定
GOOGLE_CLOUD_PROJECT=my-prod-project
GOOGLE_APPLICATION_CREDENTIALS=/app/keys/prod-service-account.json
GCS_PHOTOS_BUCKET=my-app-prod-photos
GCS_DATABASE_BUCKET=my-app-prod-database

# データベース設定
DATABASE_TYPE=duckdb
LOCAL_DB_PATH=/app/data/imgstream.db

# Streamlit設定
STREAMLIT_SERVER_PORT=8080
STREAMLIT_SERVER_ADDRESS=0.0.0.0

# 衝突検出設定
COLLISION_CACHE_TTL_SECONDS=7200
COLLISION_CACHE_MAX_ENTRIES=50000
COLLISION_DETECTION_BATCH_SIZE=500

# 監視設定
MONITORING_ENABLED=true
MONITORING_EVENT_RETENTION_DAYS=90
```

## バケット設定のベストプラクティス

### 1. バケットの分離

写真用とデータベース用のバケットを分離することで：

- **セキュリティ**: 異なるアクセス権限を設定可能
- **管理**: 用途別のライフサイクル管理
- **コスト**: 用途別のストレージクラス設定
- **バックアップ**: 異なるバックアップ戦略の適用

### 2. 命名規則

```bash
# 推奨命名規則
{project-name}-{environment}-{purpose}-bucket

# 例
my-app-prod-photos-bucket
my-app-prod-database-bucket
my-app-dev-photos-bucket
my-app-dev-database-bucket
```

### 3. リージョン設定

```bash
# 同じリージョンに配置してレイテンシを最小化
# 例: asia-northeast1 (東京)
```

### 4. ストレージクラス

```bash
# 写真バケット: STANDARD (頻繁アクセス)
# データベースバケット: NEARLINE (バックアップ用途)
```

## トラブルシューティング

### よくあるエラー

#### 1. バケットが見つからない

```
StorageError: GCS_PHOTOS_BUCKET environment variable is required
```

**解決方法**: `GCS_PHOTOS_BUCKET`環境変数を設定

#### 2. 認証エラー

```
google.auth.exceptions.DefaultCredentialsError
```

**解決方法**: `GOOGLE_APPLICATION_CREDENTIALS`を正しいパスに設定

#### 3. 権限エラー

```
google.cloud.exceptions.Forbidden: 403 Access denied
```

**解決方法**: サービスアカウントにバケットへの適切な権限を付与

### 設定確認コマンド

```bash
# 環境変数の確認
env | grep -E "(GCS_|GOOGLE_|ENVIRONMENT|LOG_LEVEL)"

# バケットアクセステスト
gsutil ls gs://$GCS_PHOTOS_BUCKET
gsutil ls gs://$GCS_DATABASE_BUCKET
```

## 関連ドキュメント

- [デプロイメントガイド](./deployment_guide.md)
- [API仕様書](./api_specification.md)
- [トラブルシューティングガイド](./troubleshooting_guide.md)
