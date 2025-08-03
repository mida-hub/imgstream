# GitHub Actions OIDC認証設定ガイド

このドキュメントでは、GitHub ActionsでGoogle CloudのOIDC（OpenID Connect）認証を設定する方法について説明します。

## 📋 概要

### OIDC認証の利点

従来のサービスアカウントキー（JSON形式）の代わりにOIDC認証を使用することで、以下の利点があります：

- **セキュリティ向上**: 長期間有効なキーファイルが不要
- **自動ローテーション**: トークンが自動的に更新される
- **細かい権限制御**: 特定のリポジトリ・ブランチからのアクセスのみ許可
- **監査の改善**: より詳細なアクセスログが取得可能

### アーキテクチャ

```
GitHub Actions → GitHub OIDC Provider → Google Cloud Workload Identity Federation → Service Account
```

## 🚀 設定手順

### 1. 前提条件

以下のツールがインストールされていることを確認してください：

- [Terraform](https://www.terraform.io/downloads.html) >= 1.12
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) >= 400.0.0
- Git

### 2. Google Cloud プロジェクトの準備

```bash
# Google Cloud にログイン
gcloud auth login

# プロジェクトを設定
gcloud config set project YOUR_PROJECT_ID

# 必要なAPIを有効化
gcloud services enable iam.googleapis.com
gcloud services enable iamcredentials.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
```

### 3. 自動設定スクリプトの実行

最も簡単な方法は、提供されている自動設定スクリプトを使用することです：

```bash
./scripts/setup-github-oidc.sh
```

このスクリプトは以下を自動的に実行します：
- 現在のプロジェクトとGitHubリポジトリの検出
- Terraform変数ファイルの更新
- Terraformの実行
- GitHub Secretsの設定値を表示

### 4. 手動設定（詳細制御が必要な場合）

#### 4.1 Terraform変数の設定

`terraform/terraform.tfvars`ファイルを作成または更新：

```hcl
project_id = "your-gcp-project-id"
github_repository = "your-username/your-repository-name"
region = "asia-northeast1"
environment = "dev"

# その他の必要な変数...
```

#### 4.2 Terraformの実行

```bash
cd terraform

# 環境別の初期化（GCSバックエンド使用）
terraform init -backend-config=backend-dev.tf  # 開発環境
# または
terraform init -backend-config=backend-prod.tf  # 本番環境

# OIDC関連リソースのみを適用
terraform apply -var-file=environments/dev.tfvars \
  -target=google_iam_workload_identity_pool.github_actions \
  -target=google_iam_workload_identity_pool_provider.github_actions \
  -target=google_service_account.github_actions \
  -target=google_service_account_iam_binding.github_actions_workload_identity \
  -target=google_project_iam_member.github_actions_roles
```

#### 4.3 Terraform出力の確認

```bash
# Workload Identity Provider名を取得
terraform output workload_identity_provider

# サービスアカウントメールを取得
terraform output github_actions_service_account_email
```

### 5. GitHub Secretsの設定

GitHubリポジトリの Settings > Secrets and variables > Actions で以下のシークレットを設定：

| シークレット名 | 値 | 説明 |
|---------------|-----|------|
| `WIF_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider` | Workload Identity Providerの完全名 |
| `WIF_SERVICE_ACCOUNT` | `github-actions-sa@PROJECT_ID.iam.gserviceaccount.com` | サービスアカウントのメールアドレス |
| `GCP_PROJECT_ID` | `your-project-id` | Google Cloud プロジェクトID |

#### 既存のシークレットの削除

OIDC認証に移行後、以下の古いシークレットは削除してください：
- `GCP_SA_KEY` (サービスアカウントキー)

## 🔧 Terraform設定の詳細

### 作成されるリソース

#### 1. Workload Identity Pool
```hcl
resource "google_iam_workload_identity_pool" "github_actions" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions OIDC authentication"
}
```

#### 2. Workload Identity Pool Provider
```hcl
resource "google_iam_workload_identity_pool_provider" "github_actions" {
  workload_identity_pool_provider_id = "github-actions-provider"
  
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}
```

#### 3. Service Account
```hcl
resource "google_service_account" "github_actions" {
  account_id   = "github-actions-sa"
  display_name = "GitHub Actions Service Account"
}
```

#### 4. IAM Bindings
- Workload Identity User権限
- 必要なGoogle Cloud サービスへの権限

### セキュリティ制限

OIDC認証では以下のセキュリティ制限が適用されます：

#### リポジトリレベルの制限
- **指定されたGitHubリポジトリからのみアクセス可能**
- `terraform/variables.tf` の `github_repository` 変数で設定
- 例: `mida-hub/imgstream` からのみアクセス許可

#### 追加のセキュリティオプション（必要に応じて設定）
- **ブランチレベルの制限**: `attribute_condition` を使用して特定のブランチからのみアクセス許可
- **環境ベースの制限**: GitHub Environmentsと連携したアクセス制御
- **複合条件**: リポジトリ、ブランチ、環境を組み合わせた制限

**注意**: `attribute_condition` を使用する場合は、`attribute_mapping` で定義された属性のみ参照可能です。

### 権限の詳細

GitHub Actions用サービスアカウントには以下の権限が付与されます：

- `roles/run.admin`: Cloud Run管理
- `roles/storage.admin`: Cloud Storage管理
- `roles/artifactregistry.admin`: Artifact Registry管理
- `roles/iam.serviceAccountUser`: サービスアカウント使用
- `roles/monitoring.editor`: モニタリング
- `roles/logging.admin`: ログ管理

**削除された権限（ImgStreamでは不要）:**
- `roles/secretmanager.admin`: Secret Managerは使用していない
- `roles/cloudsql.admin`: Cloud SQLは使用していない（DuckDBを使用）

## 🧪 テスト

### 1. ワークフローの実行テスト

OIDC設定後、以下の方法でテストできます：

```bash
# テスト用のコミットをプッシュ
git commit --allow-empty -m "Test OIDC authentication"
git push origin main
```

### 2. 認証の確認

GitHub Actionsのログで以下を確認：

```
✅ Successfully authenticated to Google Cloud using Workload Identity Federation
✅ Configured Docker for Artifact Registry
```

### 3. トラブルシューティング

#### よくあるエラー

1. **Permission denied エラー**
   ```
   Error: google: could not find default credentials
   ```
   - `WIF_PROVIDER`と`WIF_SERVICE_ACCOUNT`が正しく設定されているか確認
   - Workload Identity Poolの設定を確認

2. **Repository not allowed エラー**
   ```
   Error: The repository 'owner/repo' is not allowed
   ```
   - `github_repository`変数が正しく設定されているか確認
   - Terraformを再適用

3. **Token exchange failed エラー**
   ```
   Error: Token exchange failed
   ```
   - GitHub Actionsワークフローに`id-token: write`権限があるか確認
   - OIDC Providerの設定を確認

## 🔄 既存プロジェクトからの移行

### 移行手順

1. **現在のワークフローをバックアップ**
2. **OIDC設定を適用**（上記手順に従って）
3. **GitHub Secretsを更新**
4. **ワークフローファイルを更新**（認証部分を変更）
5. **テスト実行**
6. **古いサービスアカウントキーを削除**

### 移行チェックリスト

- [ ] Terraform設定の適用完了
- [ ] GitHub Secretsの更新完了
- [ ] ワークフローファイルの更新完了
- [ ] テスト実行成功
- [ ] 古い`GCP_SA_KEY`シークレットの削除
- [ ] 不要なサービスアカウントキーの削除

## 📚 参考資料

- [Google Cloud Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [google-github-actions/auth](https://github.com/google-github-actions/auth)

## 🆘 サポート

問題が発生した場合は、以下を確認してください：

1. [トラブルシューティングガイド](TROUBLESHOOTING.md)
2. GitHub Actionsのワークフロー実行ログ
3. Google Cloud IAMの監査ログ

---

最終更新: 2025年1月
