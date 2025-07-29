# ImgStream セットアップガイド

この包括的なガイドは、開発から本番デプロイメントまでのImgStreamのセットアップ手順を説明します。

## 📋 目次

- [前提条件](#前提条件)
- [開発環境セットアップ](#開発環境セットアップ)
- [ローカル設定](#ローカル設定)
- [Google Cloudセットアップ](#google-cloudセットアップ)
- [本番デプロイメント](#本番デプロイメント)
- [監視セットアップ](#監視セットアップ)
- [トラブルシューティング](#トラブルシューティング)
- [次のステップ](#次のステップ)

## 🔧 前提条件

### システム要件

- **オペレーティングシステム**: macOS、Linux、またはWSL2付きWindows
- **Python**: 3.11以上
- **メモリ**: 最低8GB RAM（16GB推奨）
- **ストレージ**: 20GBの空きディスク容量
- **ネットワーク**: 安定したインターネット接続

### 必要なアカウント

1. **Google Cloud Platformアカウント**
   - アクティブな請求アカウント
   - プロジェクト作成権限
   - API アクセス有効

2. **GitHubアカウント** (CI/CD用)
   - リポジトリアクセス
   - Actions有効
   - シークレット管理権限

### Required Tools

Install the following tools before proceeding:

#### 1. Python and uv Package Manager

```bash
# Install Python 3.11+ (if not already installed)
# macOS with Homebrew
brew install python@3.11

# Ubuntu/Debian
sudo apt update && sudo apt install python3.11 python3.11-venv

# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or restart terminal
```

#### 2. Google Cloud SDK

```bash
# macOS with Homebrew
brew install google-cloud-sdk

# Linux
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Windows (PowerShell)
(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:Temp\GoogleCloudSDKInstaller.exe")
& $env:Temp\GoogleCloudSDKInstaller.exe
```

#### 3. Docker

```bash
# macOS with Homebrew
brew install docker

# Ubuntu/Debian
sudo apt update
sudo apt install docker.io docker-compose
sudo usermod -aG docker $USER

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker
```

#### 4. Terraform (Infrastructure as Code)

```bash
# macOS with Homebrew
brew install terraform

# Linux
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

# Verify installation (should be >= 1.12)
terraform version
```

## 💻 Development Setup

### 1. Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-org/imgstream.git
cd imgstream

# Create and switch to development branch
git checkout -b feature/setup
```

### 2. Set Up Python Environment

```bash
# Create virtual environment and install dependencies
uv sync

# Activate virtual environment (if needed)
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### 3. Install Development Tools

```bash
# Install development dependencies
uv add --dev black ruff mypy pytest pytest-cov pre-commit

# Install pre-commit hooks
uv run pre-commit install
```

### 4. Verify Installation

```bash
# Check Python version
python --version  # Should be 3.11+

# Check installed packages
uv pip list

# Run basic tests
uv run pytest tests/unit/ -v
```

## ⚙️ Local Configuration

### 1. Environment Configuration

Create environment configuration files:

```bash
# Create local environment file
cp .env.example .env

# Edit with your settings
nano .env
```

Example `.env` file:
```bash
# Environment
ENVIRONMENT=development

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GCS_BUCKET_DEV=your-dev-bucket

# Application
DEBUG=true
LOG_LEVEL=DEBUG

# Development settings
DEVELOPMENT_MODE=true
BYPASS_IAP=true
```

### 2. Local Storage Setup

```bash
# Create local storage directories
mkdir -p data/uploads
mkdir -p data/thumbnails
mkdir -p logs

# Set permissions
chmod 755 data/
chmod 755 data/uploads/
chmod 755 data/thumbnails/
```

### 3. Database Initialization

```bash
# Initialize local database
uv run python -c "
from src.imgstream.database import init_database
init_database()
print('Database initialized successfully')
"
```

### 4. Test Local Setup

```bash
# Run the application locally
uv run streamlit run src/imgstream/main.py --server.port=8501

# In another terminal, test health endpoint
curl http://localhost:8501/health
```

## ☁️ Google Cloud Setup

### 1. Create Google Cloud Project

```bash
# Authenticate with Google Cloud
gcloud auth login

# Create new project (or use existing)
export PROJECT_ID="imgstream-$(date +%s)"
gcloud projects create $PROJECT_ID --name="ImgStream"

# Set as default project
gcloud config set project $PROJECT_ID

# Enable billing (required for most services)
# Visit: https://console.cloud.google.com/billing
```

### 2. Enable Required APIs

```bash
# Enable necessary Google Cloud APIs
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    storage.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com \
    secretmanager.googleapis.com \
    iap.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled
```

### 3. Create Service Accounts

```bash
# Create Cloud Run service account
gcloud iam service-accounts create imgstream-cloud-run \
    --display-name="ImgStream Cloud Run Service Account" \
    --description="Service account for ImgStream Cloud Run service"

# Create deployment service account
gcloud iam service-accounts create imgstream-deploy \
    --display-name="ImgStream Deployment Service Account" \
    --description="Service account for ImgStream deployments"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:imgstream-cloud-run@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:imgstream-cloud-run@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/monitoring.metricWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:imgstream-cloud-run@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"

# Grant deployment permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:imgstream-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:imgstream-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:imgstream-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"
```

### 4. Create Storage Buckets

```bash
# Create storage buckets for different environments
gsutil mb -p $PROJECT_ID -c STANDARD -l us-central1 gs://$PROJECT_ID-imgstream-dev
gsutil mb -p $PROJECT_ID -c STANDARD -l us-central1 gs://$PROJECT_ID-imgstream-staging
gsutil mb -p $PROJECT_ID -c STANDARD -l us-central1 gs://$PROJECT_ID-imgstream-prod

# Set bucket permissions
gsutil iam ch serviceAccount:imgstream-cloud-run@$PROJECT_ID.iam.gserviceaccount.com:objectAdmin gs://$PROJECT_ID-imgstream-dev
gsutil iam ch serviceAccount:imgstream-cloud-run@$PROJECT_ID.iam.gserviceaccount.com:objectAdmin gs://$PROJECT_ID-imgstream-staging
gsutil iam ch serviceAccount:imgstream-cloud-run@$PROJECT_ID.iam.gserviceaccount.com:objectAdmin gs://$PROJECT_ID-imgstream-prod

# Configure CORS for web access
cat > cors-config.json << EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "POST", "PUT", "DELETE"],
    "responseHeader": ["Content-Type", "Authorization"],
    "maxAgeSeconds": 3600
  }
]
EOF

gsutil cors set cors-config.json gs://$PROJECT_ID-imgstream-dev
gsutil cors set cors-config.json gs://$PROJECT_ID-imgstream-staging
gsutil cors set cors-config.json gs://$PROJECT_ID-imgstream-prod
```

### 5. Create Service Account Keys

```bash
# Create key for deployment service account
gcloud iam service-accounts keys create deploy-key.json \
    --iam-account=imgstream-deploy@$PROJECT_ID.iam.gserviceaccount.com

# Store key securely (for GitHub Actions)
echo "Store this key in GitHub Secrets as GCP_SA_KEY:"
cat deploy-key.json | base64

# Clean up local key file
rm deploy-key.json
```

### 6. Configure Terraform Infrastructure

Terraformを使用してインフラストラクチャとOIDC認証を設定：

```bash
# Terraformバックエンドの初期化（開発環境）
./scripts/terraform-init.sh dev

# terraform.tfvarsファイルの作成
cd terraform
cp terraform.tfvars.example terraform.tfvars

# 必要な変数を設定
cat >> terraform.tfvars << EOF
project_id = "$PROJECT_ID"
region = "asia-northeast1"
environment = "development"
github_repository = "your-username/your-repository-name"
EOF

# インフラストラクチャの適用
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars

# OIDC設定の自動セットアップ（推奨）
cd ..
./scripts/setup-github-oidc.sh
```

## 🚀 Production Deployment

### 1. GitHub Repository Setup

```bash
# Push code to GitHub
git add .
git commit -m "Initial ImgStream setup"
git push origin main

# Create develop branch for staging
git checkout -b develop
git push origin develop
```

### 2. Configure GitHub Secrets (OIDC Authentication)

**重要**: このプロジェクトではOIDC認証を使用します。従来のサービスアカウントキーは不要です。

Terraformの出力から必要な値を取得：

```bash
cd terraform
terraform output workload_identity_provider
terraform output github_actions_service_account_email
```

GitHub repository settings で以下のシークレットを設定：

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `WIF_PROVIDER` | Terraform出力の値 | Workload Identity Federation Provider |
| `WIF_SERVICE_ACCOUNT` | Terraform出力の値 | GitHub Actions Service Account Email |
| `GCP_PROJECT_ID` | Your project ID | GCP project identifier |
| `GCS_BUCKET_DEV` | `$PROJECT_ID-imgstream-dev` | Development storage bucket |
| `GCS_BUCKET_STAGING` | `$PROJECT_ID-imgstream-staging` | Staging storage bucket |
| `GCS_BUCKET_PROD` | `$PROJECT_ID-imgstream-prod` | Production storage bucket |

### 3. Deploy to Staging

```bash
# Push to develop branch to trigger staging deployment
git checkout develop
git push origin develop

# Monitor deployment in GitHub Actions
# Visit: https://github.com/your-org/imgstream/actions
```

### 4. Configure Identity-Aware Proxy (Production)

```bash
# Enable IAP for production
gcloud iap web enable --resource-type=backend-services \
    --service=imgstream-production

# Add users to IAP
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:admin@yourdomain.com" \
    --role="roles/iap.httpsResourceAccessor"

# Get IAP audience for configuration
gcloud iap web get-iam-policy --resource-type=backend-services \
    --service=imgstream-production
```

### 5. Deploy to Production

```bash
# Create production release
git checkout main
git tag v1.0.0
git push origin v1.0.0

# Or use manual deployment
ENVIRONMENT=production ./scripts/deploy-cloud-run.sh
```

### 6. Verify Production Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe imgstream-production \
    --region=us-central1 --format="value(status.url)")

echo "Production URL: $SERVICE_URL"

# Test health endpoint
curl "$SERVICE_URL/health"

# Test with authentication (if IAP is enabled)
# Visit the URL in browser for IAP authentication
```

## 📊 Monitoring Setup

### 1. Configure Monitoring and Alerts

```bash
# Set up monitoring and alerting
ENVIRONMENT=production \
ALERT_EMAIL=ops@yourdomain.com \
./scripts/setup-monitoring.sh
```

### 2. Create Custom Dashboard

```bash
# Access monitoring dashboard
echo "Monitoring Dashboard: https://console.cloud.google.com/monitoring/dashboards?project=$PROJECT_ID"

# View logs
echo "Logs: https://console.cloud.google.com/logs/query?project=$PROJECT_ID"
```

### 3. Test Alerting

```bash
# Generate test load to trigger alerts (optional)
for i in {1..100}; do
  curl -s "$SERVICE_URL/health" > /dev/null &
done
wait
```

## 🔧 Troubleshooting

### Common Setup Issues

#### 1. Permission Errors

```bash
# Check current permissions
gcloud projects get-iam-policy $PROJECT_ID

# Re-authenticate if needed
gcloud auth login
gcloud auth application-default login
```

#### 2. API Not Enabled

```bash
# List enabled APIs
gcloud services list --enabled

# Enable missing API
gcloud services enable [API_NAME]
```

#### 3. Storage Access Issues

```bash
# Test bucket access
gsutil ls gs://$PROJECT_ID-imgstream-dev

# Fix bucket permissions
gsutil iam ch serviceAccount:imgstream-cloud-run@$PROJECT_ID.iam.gserviceaccount.com:objectAdmin gs://$PROJECT_ID-imgstream-dev
```

#### 4. Deployment Failures

```bash
# Check build logs
gcloud builds log [BUILD_ID]

# Check service logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50

# Validate configuration
./scripts/validate-deployment-config.sh production
```

### Getting Help

1. **Check Documentation**: Review `docs/` directory
2. **View Logs**: Use `gcloud logs read` commands
3. **Monitor Dashboard**: Check Cloud Console
4. **GitHub Issues**: Create issue with error details
5. **Community Support**: Check project discussions

## ✅ Next Steps

After successful setup, consider these next steps:

### 1. Customize Configuration

```bash
# Update environment-specific settings
nano config/environments/production.yaml

# Configure custom domain (optional)
gcloud run domain-mappings create --service=imgstream-production --domain=imgstream.yourdomain.com
```

### 2. Set Up Development Workflow

```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes and test
uv run pytest
uv run black .
uv run ruff check .

# Commit and push
git add .
git commit -m "feat: add new feature"
git push origin feature/new-feature

# Create pull request for review
```

### 3. Configure Backup and Recovery

```bash
# Set up automated backups
gsutil lifecycle set lifecycle-config.json gs://$PROJECT_ID-imgstream-prod

# Test backup restoration
./scripts/backup-restore.sh test
```

### 4. Performance Optimization

```bash
# Monitor performance
./scripts/deployment-monitor.sh status

# Optimize based on metrics
# - Adjust resource limits
# - Configure caching
# - Optimize database queries
```

### 5. Security Hardening

```bash
# Review security settings
./scripts/security-audit.sh

# Update IAM permissions
# Configure additional security headers
# Set up security monitoring
```

## 📚 Additional Resources

- **API Documentation**: [docs/API_SPECIFICATION.md](API_SPECIFICATION.md)
- **Architecture Guide**: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- **Deployment Guide**: [docs/DEPLOYMENT.md](DEPLOYMENT.md)
- **Troubleshooting**: [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Contributing**: [CONTRIBUTING.md](../CONTRIBUTING.md)

## 🎉 Congratulations!

You have successfully set up ImgStream! Your photo management application is now ready for development and production use.

### Quick Verification Checklist

- [ ] Local development environment working
- [ ] Google Cloud project configured
- [ ] Storage buckets created and accessible
- [ ] Service accounts configured with proper permissions
- [ ] GitHub Actions CI/CD pipeline working
- [ ] Staging environment deployed and tested
- [ ] Production environment deployed with IAP
- [ ] Monitoring and alerting configured
- [ ] Documentation reviewed and understood

### Support

If you encounter any issues during setup, please:

1. Check the troubleshooting guide
2. Review the logs for error messages
3. Consult the documentation
4. Create a GitHub issue with detailed information

Happy coding! 🚀
