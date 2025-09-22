# ImgStream デプロイメントガイド

## 概要

このガイドでは、ファイル名衝突回避機能を含むImgStreamアプリケーションのデプロイメント手順について説明します。

## 前提条件

### 必要なツール

- Python 3.9以上
- uv (Python パッケージマネージャー)
- Docker & Docker Compose
- Terraform
- Google Cloud SDK (gcloud)

### 必要なアカウント・権限

- Google Cloud Platform アカウント
- 以下のGCP APIが有効化されていること:
  - Cloud Storage API
  - Cloud SQL API (本番環境の場合)
  - Identity and Access Management (IAM) API

## 環境設定

### 1. 開発環境

#### 依存関係のインストール

```bash
# uvを使用してPython依存関係をインストール
uv sync

# 開発用依存関係も含める
uv sync --dev
```

#### 環境変数の設定

`.env`ファイルを作成し、以下の変数を設定:

```bash
# 環境設定
ENVIRONMENT=development

# Google Cloud設定
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json

# ストレージ設定
GCS_BUCKET_NAME=your-bucket-name
GCS_BUCKET_REGION=asia-northeast1

# データベース設定
DATABASE_TYPE=duckdb
LOCAL_DB_PATH=./data/imgstream.db

# Streamlit設定
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0

# 衝突検出設定
COLLISION_CACHE_TTL_SECONDS=3600
COLLISION_CACHE_MAX_ENTRIES=10000
COLLISION_DETECTION_BATCH_SIZE=100

# 監視設定
MONITORING_ENABLED=true
MONITORING_EVENT_RETENTION_DAYS=30
```

#### ローカル開発用Docker環境

```bash
# Docker Composeでローカル環境を起動
docker-compose up -d

# アプリケーションの起動
uv run streamlit run src/main.py
```

### 2. テスト環境

#### テスト用インフラの構築

```bash
# Terraformでテスト環境を構築
cd terraform/test
terraform init
terraform plan
terraform apply
```

#### テスト環境用の設定

```bash
# テスト環境変数
ENVIRONMENT=test
GOOGLE_CLOUD_PROJECT=your-test-project-id
GCS_BUCKET_NAME=your-test-bucket-name

# テスト用データベース設定
DATABASE_TYPE=duckdb
LOCAL_DB_PATH=./test_data/imgstream_test.db

# テスト用監視設定
MONITORING_EVENT_RETENTION_DAYS=7
```

### 3. 本番環境

#### 本番用インフラの構築

```bash
# Terraformで本番環境を構築
cd terraform/production
terraform init
terraform plan
terraform apply
```

#### 本番環境用の設定

```bash
# 本番環境変数
ENVIRONMENT=production
GOOGLE_CLOUD_PROJECT=your-prod-project-id
GCS_BUCKET_NAME=your-prod-bucket-name

# 本番用データベース設定（Cloud SQLを推奨）
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://user:password@host:port/database

# セキュリティ設定
ADMIN_FUNCTIONS_ENABLED=false
DEBUG_MODE=false

# パフォーマンス設定
COLLISION_CACHE_TTL_SECONDS=7200
COLLISION_CACHE_MAX_ENTRIES=50000
COLLISION_DETECTION_BATCH_SIZE=500

# 監視設定
MONITORING_ENABLED=true
MONITORING_EVENT_RETENTION_DAYS=90
```

## デプロイメント手順

### 1. コードの準備

#### コード品質チェック

```bash
# 環境変数を設定してテストを実行
ENVIRONMENT=production uv run pytest

# コードフォーマット
uv run black src/ tests/

# リンター実行
uv run ruff src/ tests/

# 型チェック
uv run mypy src/
```

#### 依存関係の確認

```bash
# 依存関係の更新確認
uv sync --upgrade

# セキュリティ脆弱性チェック
uv run safety check
```

### 2. インフラストラクチャのデプロイ

#### Google Cloud リソースの作成

```bash
# サービスアカウントの作成
gcloud iam service-accounts create imgstream-app \
    --display-name="ImgStream Application Service Account"

# 必要な権限の付与
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:imgstream-app@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

# サービスアカウントキーの作成
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account=imgstream-app@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com
```

#### Terraformでのリソース作成

```bash
# 本番環境の場合
cd terraform/production

# 変数ファイルの設定
cat > terraform.tfvars << EOF
project_id = "your-prod-project-id"
region = "asia-northeast1"
bucket_name = "your-prod-bucket-name"
environment = "production"
EOF

# インフラの作成
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

### 3. アプリケーションのデプロイ

#### Dockerイメージのビルド

```bash
# Dockerイメージのビルド
docker build -t imgstream:latest .

# イメージのタグ付け（Container Registryを使用する場合）
docker tag imgstream:latest gcr.io/$GOOGLE_CLOUD_PROJECT/imgstream:latest

# イメージのプッシュ
docker push gcr.io/$GOOGLE_CLOUD_PROJECT/imgstream:latest
```

#### Cloud Runへのデプロイ（推奨）

```bash
# Cloud Runサービスのデプロイ
gcloud run deploy imgstream \
    --image gcr.io/$GOOGLE_CLOUD_PROJECT/imgstream:latest \
    --platform managed \
    --region asia-northeast1 \
    --allow-unauthenticated \
    --set-env-vars ENVIRONMENT=production \
    --set-env-vars GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT \
    --set-env-vars GCS_BUCKET_NAME=your-prod-bucket-name \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10
```

#### Compute Engineへのデプロイ

```bash
# VMインスタンスの作成
gcloud compute instances create imgstream-app \
    --zone=asia-northeast1-a \
    --machine-type=e2-standard-2 \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB \
    --service-account=imgstream-app@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com \
    --scopes=cloud-platform

# アプリケーションのデプロイ
gcloud compute scp --recurse . imgstream-app:~/imgstream --zone=asia-northeast1-a
gcloud compute ssh imgstream-app --zone=asia-northeast1-a --command="cd ~/imgstream && docker-compose up -d"
```

## 設定管理

### 1. 環境別設定

#### Streamlit設定

`.streamlit/config.toml`:
```toml
[server]
port = 8501
address = "0.0.0.0"
maxUploadSize = 200

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"

[browser]
gatherUsageStats = false
```

#### シークレット管理

`.streamlit/secrets.toml`:
```toml
# 本番環境では環境変数またはSecret Managerを使用
[gcp]
project_id = "your-project-id"
bucket_name = "your-bucket-name"

[database]
type = "postgresql"
url = "postgresql://user:password@host:port/database"

[monitoring]
enabled = true
retention_days = 90
```

### 2. ログ設定

#### ログレベルの設定

```python
# logging.conf
[loggers]
keys=root,imgstream

[handlers]
keys=consoleHandler,fileHandler

[formatters]
keys=simpleFormatter,detailedFormatter

[logger_root]
level=INFO
handlers=consoleHandler

[logger_imgstream]
level=DEBUG
handlers=consoleHandler,fileHandler
qualname=imgstream
propagate=0

[handler_consoleHandler]
class=StreamHandler
level=INFO
formatter=simpleFormatter
args=(sys.stdout,)

[handler_fileHandler]
class=FileHandler
level=DEBUG
formatter=detailedFormatter
args=('imgstream.log',)

[formatter_simpleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s

[formatter_detailedFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s
```

## 監視とメンテナンス

### 1. ヘルスチェック

#### アプリケーションヘルスチェック

```bash
# ヘルスチェックエンドポイント
curl http://your-app-url/health

# 期待されるレスポンス
{
    "status": "healthy",
    "timestamp": "2025-01-01T00:00:00Z",
    "version": "1.0.0",
    "services": {
        "database": "healthy",
        "storage": "healthy",
        "monitoring": "healthy"
    }
}
```

#### データベースヘルスチェック

```bash
# 開発環境でのデータベース状態確認
curl -X POST http://localhost:8501/api/admin/database/status \
    -H "Content-Type: application/json" \
    -d '{"user_id": "admin"}'
```

### 2. ログ監視

#### Cloud Loggingでの監視

```bash
# エラーログの確認
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
    --limit=50 \
    --format="table(timestamp,severity,textPayload)"

# 衝突検出イベントの監視
gcloud logging read "resource.type=cloud_run_revision AND textPayload:collision_detected" \
    --limit=100
```

### 3. パフォーマンス監視

#### メトリクスの確認

```python
# 衝突検出パフォーマンスの監視
from imgstream.monitoring.collision_monitor import get_collision_monitor

monitor = get_collision_monitor()
stats = monitor.get_collision_statistics("user_id")
print(f"Average detection time: {stats['collision_metrics']['average_detection_time_ms']}ms")
```

### 4. 定期メンテナンス

#### キャッシュクリア

```bash
# 定期的なキャッシュクリア（cronジョブとして設定）
0 2 * * * /usr/local/bin/python -c "from imgstream.utils.collision_detection import clear_collision_cache; clear_collision_cache()"
```

#### 古いイベントの削除

```bash
# 古い監視イベントの削除
0 3 * * 0 /usr/local/bin/python -c "
from imgstream.monitoring.collision_monitor import get_collision_monitor
from datetime import timedelta
monitor = get_collision_monitor()
monitor.clear_old_events(timedelta(days=30))
"
```

## トラブルシューティング

### 1. 一般的な問題

#### 衝突検出が動作しない

```bash
# キャッシュの確認
python -c "from imgstream.utils.collision_detection import get_collision_cache_stats; print(get_collision_cache_stats())"

# キャッシュのクリア
python -c "from imgstream.utils.collision_detection import clear_collision_cache; clear_collision_cache()"
```

#### データベース接続エラー

```bash
# 開発環境でのデータベースリセット
curl -X POST http://localhost:8501/api/admin/database/reset \
    -H "Content-Type: application/json" \
    -d '{"user_id": "admin", "confirm_reset": true}'
```

### 2. パフォーマンス問題

#### 衝突検出の最適化

```python
# バッチサイズの調整
from imgstream.utils.collision_detection import check_filename_collisions_optimized

# 大量ファイルの場合はバッチサイズを増やす
results = check_filename_collisions_optimized(
    user_id="user_id",
    filenames=large_file_list,
    batch_size=500  # デフォルト100から増加
)
```

### 3. セキュリティ問題

#### 本番環境での管理機能の無効化

```bash
# 環境変数の確認
echo $ENVIRONMENT  # "production"であることを確認

# 管理機能が無効化されていることの確認
python -c "from imgstream.api.database_admin import is_development_environment; print(is_development_environment())"
```

## バックアップとリストア

### 1. データベースバックアップ

```bash
# DuckDBファイルのバックアップ
cp ./data/imgstream.db ./backups/imgstream_$(date +%Y%m%d_%H%M%S).db

# GCSへのバックアップアップロード
gsutil cp ./backups/imgstream_*.db gs://your-backup-bucket/database/
```

### 2. 設定ファイルのバックアップ

```bash
# 重要な設定ファイルのバックアップ
tar -czf config_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    .env \
    .streamlit/ \
    terraform/ \
    docker-compose.yml
```

## セキュリティ考慮事項

### 1. 認証・認可

- すべてのAPIエンドポイントで適切な認証を実装
- 管理機能は開発環境でのみ有効化
- サービスアカウントの最小権限の原則を適用

### 2. データ保護

- 機密情報は環境変数またはSecret Managerで管理
- データベースファイルの適切な権限設定
- ログファイルに機密情報を含めない

### 3. ネットワークセキュリティ

- HTTPSの強制使用
- 適切なCORSポリシーの設定
- ファイアウォールルールの適切な設定

## 更新とロールバック

### 1. アプリケーション更新

```bash
# 新しいバージョンのデプロイ
docker build -t imgstream:v1.1.0 .
docker tag imgstream:v1.1.0 gcr.io/$GOOGLE_CLOUD_PROJECT/imgstream:v1.1.0
docker push gcr.io/$GOOGLE_CLOUD_PROJECT/imgstream:v1.1.0

# Cloud Runサービスの更新
gcloud run deploy imgstream \
    --image gcr.io/$GOOGLE_CLOUD_PROJECT/imgstream:v1.1.0 \
    --platform managed \
    --region asia-northeast1
```

### 2. ロールバック

```bash
# 前のバージョンへのロールバック
gcloud run deploy imgstream \
    --image gcr.io/$GOOGLE_CLOUD_PROJECT/imgstream:v1.0.0 \
    --platform managed \
    --region asia-northeast1
```

## サポートとドキュメント

- [API仕様書](./api_specification.md)
- [ユーザーガイド](./collision_handling_user_guide.md)
- [データベースリセットガイド](./database_reset_guide.md)
- [トラブルシューティングガイド](./troubleshooting_guide.md)
