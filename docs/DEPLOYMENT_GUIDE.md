# ImgStream デプロイメントガイド

このガイドは、ImgStreamの開発環境セットアップから本番デプロイメントまでの完全なプロセスをカバーします。

## 📋 目次

- [前提条件](#前提条件)
- [開発環境セットアップ](#開発環境セットアップ)
- [手動デプロイメント](#手動デプロイメント)
- [自動デプロイメント（CI/CD）](#自動デプロイメントcicd)
- [本番デプロイメント](#本番デプロイメント)
- [デプロイメントスクリプト](#デプロイメントスクリプト)
- [トラブルシューティング](#トラブルシューティング)

## 🔧 前提条件

### システム要件
- Python 3.11以上
- Google Cloud Platform アカウント（課金有効）
- Docker
- Terraform >= 1.12

### 必要なツール
```bash
# Google Cloud SDK
brew install google-cloud-sdk

# Terraform
brew install terraform

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 💻 開発環境セットアップ

### 1. リポジトリのクローン
```bash
git clone https://github.com/your-org/imgstream.git
cd imgstream
```

### 2. Python環境のセットアップ
```bash
# 依存関係のインストール
uv sync

# 開発ツールのインストール
uv add --dev black ruff mypy pytest pre-commit
uv run pre-commit install
```

### 3. 環境設定
```bash
# 環境ファイルの作成
cp .env.example .env

# 必要な設定を編集
nano .env
```

### 4. ローカル実行
```bash
# アプリケーションの起動
uv run streamlit run src/imgstream/main.py

# ヘルスチェック
curl http://localhost:8501/health
```

## 🚀 手動デプロイメント

### Google Cloud セットアップ

#### 1. プロジェクト作成と認証
```bash
# 1. ユーザー認証
gcloud auth login

# 2. Application Default Credentials設定（Terraform用）
gcloud auth application-default login

# 3. プロジェクト作成
export PROJECT_ID="imgstream-$(date +%s)"
gcloud projects create $PROJECT_ID
gcloud config set project $PROJECT_ID
```

#### 2. API有効化
```bash
gcloud services enable \
    run.googleapis.com \
    storage.googleapis.com \
    artifactregistry.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com \
    iap.googleapis.com
```

#### 3. インフラストラクチャ構築
```bash
# Terraform初期化
./scripts/terraform-init.sh dev

# インフラ適用
cd terraform
terraform plan -var-file="environments/dev.tfvars" -var="project_id=$PROJECT_ID"
terraform apply -var-file="environments/dev.tfvars" -var="project_id=$PROJECT_ID"
```

#### 4. アプリケーションデプロイ
```bash
# Artifact Registry認証設定
gcloud auth configure-docker asia-northeast1-docker.pkg.dev

# イメージビルド
./scripts/build-image.sh -p $PROJECT_ID -t latest

# デプロイ実行
./scripts/deploy-cloud-run.sh -p $PROJECT_ID -e dev -i asia-northeast1-docker.pkg.dev/$PROJECT_ID/imgstream/imgstream:latest
```

## 🔄 自動デプロイメント（CI/CD）

### GitHub Actions セットアップ

#### 1. OIDC認証設定
```bash
# OIDC設定の自動セットアップ
./scripts/setup-github-oidc.sh
```

#### 2. GitHub Secrets設定
以下のシークレットをGitHubリポジトリに設定：

| Secret Name | Description |
|-------------|-------------|
| `WIF_PROVIDER` | Workload Identity Federation Provider |
| `WIF_SERVICE_ACCOUNT` | GitHub Actions Service Account Email |
| `GCP_PROJECT_ID` | GCP Project ID |
| `GCS_BUCKET_DEV` | Development storage bucket |
| `GCS_BUCKET_PROD` | Production storage bucket |

#### 3. 自動デプロイメント
- **開発環境**: `develop`ブランチへのプッシュで自動デプロイ
- **本番環境**: `main`ブランチへのプッシュまたはタグで自動デプロイ

## 🏭 本番デプロイメント

### 1. 本番環境準備
```bash
# 本番用Terraform初期化
./scripts/terraform-init.sh prod

# 本番インフラ構築
cd terraform
terraform apply -var-file="environments/prod.tfvars" -var="project_id=$PROJECT_ID"
```

### 2. Identity-Aware Proxy設定
```bash
# IAP有効化
gcloud iap web enable --resource-type=backend-services --service=imgstream-production

# ユーザー追加
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:admin@yourdomain.com" \
    --role="roles/iap.httpsResourceAccessor"
```

### 3. 本番デプロイ実行
```bash
# 本番デプロイ（手動）
./scripts/deploy-production.sh -p $PROJECT_ID -i asia-northeast1-docker.pkg.dev/$PROJECT_ID/imgstream/imgstream:v1.0.0

# または自動デプロイ（GitHub Actions）
git tag v1.0.0
git push origin v1.0.0
```

## 🛠️ デプロイメントスクリプト

### 主要スクリプト

#### `terraform-init.sh`
環境別Terraform初期化
```bash
./scripts/terraform-init.sh [dev|prod]
```

#### `setup-github-oidc.sh`
OIDC認証自動セットアップ
```bash
./scripts/setup-github-oidc.sh
```

#### `build-image.sh`
Dockerイメージビルド
```bash
./scripts/build-image.sh -p PROJECT_ID -t TAG [--push]
```

#### `deploy-cloud-run.sh`
Cloud Runデプロイ
```bash
./scripts/deploy-cloud-run.sh -p PROJECT_ID -e ENVIRONMENT -i IMAGE_TAG
```

#### `deploy-production.sh`
本番環境完全デプロイ
```bash
./scripts/deploy-production.sh -p PROJECT_ID -i IMAGE_TAG [OPTIONS]
```

### スクリプトオプション

各スクリプトの詳細なオプションについては、`-h`フラグで確認：
```bash
./scripts/deploy-cloud-run.sh -h
```

## 🔧 トラブルシューティング

### よくある問題

#### 1. 認証エラー
```bash
# ユーザー認証
gcloud auth login

# Application Default Credentials設定（Terraform/スクリプト用）
gcloud auth application-default login

# 認証状態確認
gcloud auth list
gcloud auth application-default print-access-token

# プロジェクト設定確認
gcloud config get-value project
```

#### 2. API未有効化
```bash
# 必要なAPIを有効化
gcloud services enable run.googleapis.com
```

#### 3. 権限不足
```bash
# 権限確認
gcloud projects get-iam-policy $PROJECT_ID
```

#### 4. イメージが見つからない
```bash
# イメージビルド・プッシュ
./scripts/build-image.sh -p $PROJECT_ID -t latest --push
```

### ログ確認
```bash
# Cloud Runログ
gcloud logs read "resource.type=cloud_run_revision" --limit=50

# Dockerビルドログ（ローカル）
docker build --progress=plain -t asia-northeast1-docker.pkg.dev/$PROJECT_ID/imgstream/imgstream:latest .

# サービス状態
gcloud run services describe imgstream-production --region=us-central1
```

### ヘルスチェック
```bash
# アプリケーションヘルス
curl https://your-service-url/health

# サービス状態確認
./scripts/deployment-monitor.sh status
```

## 📊 監視とメンテナンス

### 監視設定
```bash
# 監視・アラート設定
./scripts/setup-monitoring.sh -p $PROJECT_ID -e production
```

### 定期メンテナンス
- 依存関係の更新（月次）
- セキュリティパッチ適用
- パフォーマンス監視
- コスト最適化レビュー

## 🔗 関連ドキュメント

- [アーキテクチャガイド](ARCHITECTURE.md)
- [開発ガイド](DEVELOPMENT.md)
- [品質チェックガイド](QUALITY_CHECK.md)
- [トラブルシューティング](TROUBLESHOOTING.md)
- [GitHub OIDC設定](GITHUB_OIDC_SETUP.md)

---

このガイドは、ImgStreamの完全なデプロイメントプロセスをカバーしています。追加の質問や問題がある場合は、[トラブルシューティングガイド](TROUBLESHOOTING.md)を参照するか、GitHubでIssueを作成してください。
