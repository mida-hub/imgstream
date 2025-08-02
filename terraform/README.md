# Imgstream インフラストラクチャ

このディレクトリには、Google Cloud Platform上でimgstream写真管理アプリケーションのインフラストラクチャをデプロイするためのTerraform設定が含まれています。

## 前提条件

1. **Google Cloud SDK**: gcloud CLIのインストールと設定
   ```bash
   # gcloud CLIのインストール (macOS)
   brew install google-cloud-sdk
   
   # 認証
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Terraform**: Terraformのインストール (バージョン >= 1.12)
   ```bash
   # Terraformのインストール (macOS)
   brew install terraform
   ```

3. **GCPプロジェクト**: GCPプロジェクトの作成と課金の有効化

## 🏗️ Backend設定

このプロジェクトでは、Terraformの状態管理にGoogle Cloud Storage (GCS)をバックエンドとして使用しています：

- **バケット**: `tfstate-apps-466614`
- **開発環境**: `gs://tfstate-apps-466614/imgstream/dev/default.tfstate`
- **本番環境**: `gs://tfstate-apps-466614/imgstream/prod/default.tfstate`

### 環境別の初期化

提供されているスクリプトを使用して環境別に初期化：

```bash
# 開発環境
./scripts/terraform-init.sh dev

# 本番環境
./scripts/terraform-init.sh prod
```

または手動でバックエンド設定を指定して初期化：

```bash
# 開発環境
cd terraform
terraform init -backend-config=backend-dev.hcl

# 本番環境
cd terraform
terraform init -backend-config=backend-prod.hcl
```

## クイックスタート

### オプション1: IAPを使用した自動セットアップ（本番環境推奨）

1. **自動スクリプトでCloud IAPをセットアップ**
   ```bash
   # スクリプトを実行可能にする
   chmod +x scripts/setup-iap.sh scripts/test-iap.sh
   
   # 開発環境のセットアップ
   ./scripts/setup-iap.sh -p YOUR_PROJECT_ID -e support@example.com -env dev
   
   # カスタムドメインとアクセス制御付きの本番環境セットアップ
   ./scripts/setup-iap.sh -p YOUR_PROJECT_ID -e support@example.com -env prod \
     -d imgstream.example.com -u admin@example.com,user@example.com
   ```

2. **IAP設定のテスト**
   ```bash
   # セットアップのテスト
   ./scripts/test-iap.sh -p YOUR_PROJECT_ID -env prod
   ```

### Option 2: Manual Terraform Deployment

1. **Clone and navigate to terraform directory**
   ```bash
   cd terraform
   ```

2. **Configure environment variables**
   ```bash
   # Edit terraform/environments/dev.tfvars or prod.tfvars
   # Update the following required variables:
   # - iap_support_email
   # - allowed_users or allowed_domains
   # - custom_domain (optional)
   ```

3. **Deploy infrastructure**
   ```bash
   # Initialize Terraform
   terraform init
   
   # Plan deployment
   terraform plan -var-file="environments/prod.tfvars" -var="project_id=YOUR_PROJECT_ID"
   
   # Apply deployment
   terraform apply -var-file="environments/prod.tfvars" -var="project_id=YOUR_PROJECT_ID"
   ```

## Infrastructure Components

### Storage Buckets

1. **Photos Bucket** (`imgstream-photos-{env}-{suffix}`)
   - Stores original photos and thumbnails
   - Lifecycle policy: Standard → Coldline (30 days) → Archive (365 days)
   - Public read access for signed URLs
   - CORS enabled for web access

2. **Database Bucket** (`imgstream-database-{env}-{suffix}`)
   - Stores DuckDB backup files
   - Versioning enabled
   - Lifecycle policy: Standard → Coldline (7 days) → Archive (90 days) → Delete (365 days)
   - Private access only

### Service Accounts

1. **Cloud Run Service Account**
   - Used by the application for GCS access
   - Permissions: Storage Object Admin, Logging, Monitoring

2. **Monitoring Service Account**
   - Used for monitoring and alerting
   - Permissions: Monitoring Viewer, Logging Viewer, Storage Object Viewer

### Security Features

- Uniform bucket-level access enabled
- Principle of least privilege for service accounts
- Required APIs automatically enabled
- Bucket-level IAM bindings for access control

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `project_id` | GCP project ID | - | Yes |
| `region` | GCP region | `us-central1` | No |
| `environment` | Environment name | `dev` | No |
| `bucket_location` | GCS bucket location | `US` | No |
| `lifecycle_coldline_days` | Days to Coldline transition | `30` | No |
| `lifecycle_archive_days` | Days to Archive transition | `365` | No |
| `lifecycle_delete_days` | Days to deletion (0=never) | `0` | No |

### Environment-Specific Configurations

- **Development** (`environments/dev.tfvars`)
  - Shorter lifecycle policies for cost optimization
  - Auto-deletion after 90 days
  - Relaxed security settings

- **Production** (`environments/prod.tfvars`)
  - Standard lifecycle policies
  - No auto-deletion
  - Strict security settings

## Deployment Commands

### Using the Deploy Script

```bash
# Plan deployment
./scripts/deploy.sh -p PROJECT_ID -e ENVIRONMENT -a plan

# Apply deployment
./scripts/deploy.sh -p PROJECT_ID -e ENVIRONMENT -a apply

# Apply with auto-approval
./scripts/deploy.sh -p PROJECT_ID -e ENVIRONMENT -a apply --auto-approve

# Destroy infrastructure
./scripts/deploy.sh -p PROJECT_ID -e ENVIRONMENT -a destroy
```

### Manual Terraform Commands

```bash
# Initialize
terraform init

# Plan
terraform plan -var-file="environments/dev.tfvars" -var="project_id=YOUR_PROJECT_ID"

# Apply
terraform apply -var-file="environments/dev.tfvars" -var="project_id=YOUR_PROJECT_ID"

# Destroy
terraform destroy -var-file="environments/dev.tfvars" -var="project_id=YOUR_PROJECT_ID"
```

## Outputs

After successful deployment, Terraform will output:

- `photos_bucket_name`: Name of the photos storage bucket
- `photos_bucket_url`: URL of the photos storage bucket
- `database_bucket_name`: Name of the database backup bucket
- `database_bucket_url`: URL of the database backup bucket
- `service_account_email`: Email of the Cloud Run service account

## Cost Optimization

### Free Tier Considerations

- **GCS Storage**: 5GB free per month
- **GCS Operations**: 5,000 Class A operations, 50,000 Class B operations per month
- **Lifecycle policies**: Automatically move data to cheaper storage classes

### Lifecycle Policies

1. **Photos Bucket**:
   - Standard storage for first 30 days (frequent access)
   - Coldline storage after 30 days (monthly access)
   - Archive storage after 365 days (yearly access)
   - Optional deletion (disabled by default)

2. **Database Bucket**:
   - Standard storage for first 7 days
   - Coldline storage after 7 days
   - Archive storage after 90 days
   - Automatic deletion after 365 days

## Security Best Practices

1. **Bucket Access**:
   - Uniform bucket-level access enabled
   - Service account-based access only
   - No public write access

2. **Service Accounts**:
   - Principle of least privilege
   - Separate accounts for different purposes
   - Regular key rotation (handled by GCP)

3. **Monitoring**:
   - Cloud Logging integration
   - Cloud Monitoring integration
   - Audit logs enabled

## Troubleshooting

### Common Issues

1. **Permission Denied**:
   ```bash
   # Ensure you're authenticated
   gcloud auth login
   gcloud auth application-default login
   
   # Check project permissions
   gcloud projects get-iam-policy PROJECT_ID
   ```

2. **Bucket Name Conflicts**:
   - Bucket names are globally unique
   - The configuration uses random suffixes to avoid conflicts
   - If conflicts occur, run `terraform apply` again

3. **API Not Enabled**:
   ```bash
   # Enable required APIs manually
   gcloud services enable storage.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable iap.googleapis.com
   ```

### State Management

- Terraform state is stored locally by default
- For production, consider using remote state storage:
  ```hcl
  terraform {
    backend "gcs" {
      bucket = "your-terraform-state-bucket"
      prefix = "imgstream/terraform.tfstate"
    }
  }
  ```

## Cloud Run Deployment

### Container Image Build

1. **Build for Cloud Run**:
   ```bash
   # Build production image
   docker build -f Dockerfile.cloudrun -t gcr.io/PROJECT_ID/imgstream:latest .
   
   # Push to Container Registry
   docker push gcr.io/PROJECT_ID/imgstream:latest
   ```

2. **Deploy using script**:
   ```bash
   # Make script executable
   chmod +x scripts/deploy-cloud-run.sh
   
   # Deploy to development
   ./scripts/deploy-cloud-run.sh -p PROJECT_ID -e dev
   
   # Deploy to production
   ./scripts/deploy-cloud-run.sh -p PROJECT_ID -e prod
   ```

3. **Deploy using Cloud Build**:
   ```bash
   # Submit build to Cloud Build
   gcloud builds submit --config cloudbuild.yaml \
     --substitutions _ENVIRONMENT=dev,_REGION=us-central1
   ```

### Environment Variables

The Cloud Run service automatically receives:
- `ENVIRONMENT`: Environment name (dev/prod)
- `GCP_PROJECT_ID`: GCP project ID
- `GCP_REGION`: GCP region
- `GCS_PHOTOS_BUCKET`: Photos storage bucket name
- `GCS_DATABASE_BUCKET`: Database backup bucket name

### Secrets Management

**Note**: ImgStream currently does not use secrets as it relies on:
- Google Cloud IAP for authentication (no custom session secrets needed)
- DuckDB without encryption (no database encryption keys needed)
- Standard Streamlit session management

If you need to add secrets in the future, you can uncomment and modify the relevant sections in `terraform/secrets.tf`.

### Resource Configuration

- **Development**: 1 vCPU, 1GB RAM, 0-3 instances
- **Production**: 1 vCPU, 2GB RAM, 1-10 instances
- **Timeout**: 5 minutes
- **Concurrency**: 80 requests per instance

## Next Steps

After deploying the infrastructure:

1. ✅ Deploy storage infrastructure (Task 11.1)
2. ✅ Deploy Cloud Run service (Task 11.2)
3. Configure Cloud IAP (Task 11.3)
4. Set up CI/CD pipeline (Task 12)
5. Configure monitoring and alerting (Task 14.2)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Terraform and GCP documentation
3. Check application logs in Cloud Logging
