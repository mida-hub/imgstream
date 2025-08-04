# Design Document

## Overview

この設計では、現在ImgStreamモジュール内にある`google_artifact_registry_repository`リソースを共通インフラストラクチャ（common）に移動し、環境別のタグ管理システムを実装します。これにより、コンテナレジストリの一元管理と効率的な環境別イメージ管理を実現します。

## Architecture

### Current Architecture
```
terraform/
├── modules/imgstream/
│   ├── artifact_registry.tf  # 各環境で個別のレジストリ
│   └── cloud_run.tf         # 環境固有のイメージ参照
├── dev/                     # dev環境のレジストリ
└── prod/                    # prod環境のレジストリ
```

### Target Architecture
```
terraform/
├── common/
│   ├── artifact_registry.tf  # 共通のレジストリ
│   └── outputs.tf           # レジストリ情報の出力
├── modules/imgstream/
│   └── cloud_run.tf         # 共通レジストリからのイメージ参照
├── dev/                     # 共通レジストリを参照
└── prod/                    # 共通レジストリを参照
```

## Components and Interfaces

### 1. Common Artifact Registry Component

**Location**: `terraform/common/artifact_registry.tf`

**Responsibilities**:
- 単一のArtifact Registryリポジトリの作成
- GitHub Actions用のIAM権限設定
- 基本的なラベリングとメタデータ管理

**Interface**:
```hcl
# Outputs
output "artifact_registry_repository_url" {
  description = "URL of the Artifact Registry repository"
  value       = google_artifact_registry_repository.imgstream.name
}

output "artifact_registry_location" {
  description = "Location of the Artifact Registry repository"
  value       = google_artifact_registry_repository.imgstream.location
}
```

### 2. Environment-Specific Image Tag Management

**Location**: 各環境の`variables.tf`と`*.tfvars`

**Responsibilities**:
- 環境別のデフォルトタグ定義
- カスタムタグのオーバーライド機能
- イメージURL構築

**Interface**:
```hcl
variable "container_image_tag" {
  description = "Container image tag for the environment"
  type        = string
  default     = null  # 環境別デフォルトを使用
}

variable "default_image_tags" {
  description = "Default image tags per environment"
  type        = map(string)
  default = {
    dev  = "latest"
    prod = "stable"
  }
}
```

### 3. Updated ImgStream Module

**Location**: `terraform/modules/imgstream/`

**Changes**:
- `artifact_registry.tf`の削除
- `cloud_run.tf`でのイメージ参照方法の更新
- 共通レジストリからのデータソース参照

**Interface**:
```hcl
# Data source for common Artifact Registry
data "terraform_remote_state" "common" {
  backend = "gcs"
  config = {
    bucket = "tfstate-apps-466614"
    prefix = "imgstream/common"
  }
}

# Updated container image reference
locals {
  registry_url = data.terraform_remote_state.common.outputs.artifact_registry_repository_url
  image_tag    = var.container_image_tag != null ? var.container_image_tag : var.default_image_tags[var.environment]
  container_image = "${local.registry_url}:${local.image_tag}"
}
```

## Data Models

### 1. Artifact Registry Configuration

```hcl
resource "google_artifact_registry_repository" "imgstream" {
  location      = var.region
  repository_id = "imgstream"
  description   = "Shared Docker repository for ImgStream application"
  format        = "DOCKER"

  labels = {
    shared      = "true"
    app         = "imgstream"
    managed-by  = "terraform"
  }
}
```

### 2. Environment Tag Mapping

```hcl
locals {
  default_tags = {
    dev     = "latest"
    staging = "staging"
    prod    = "stable"
  }
  
  image_tag = var.container_image_tag != null ? var.container_image_tag : local.default_tags[var.environment]
}
```

### 3. IAM Permission Model

```hcl
# GitHub Actions - Write access
resource "google_artifact_registry_repository_iam_member" "github_actions_writer" {
  location   = google_artifact_registry_repository.imgstream.location
  repository = google_artifact_registry_repository.imgstream.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.github_actions.email}"
}

# Cloud Run Service Accounts - Read access
resource "google_artifact_registry_repository_iam_member" "cloud_run_readers" {
  for_each = toset(var.cloud_run_service_accounts)
  
  location   = google_artifact_registry_repository.imgstream.location
  repository = google_artifact_registry_repository.imgstream.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${each.value}"
}
```

## Error Handling

### 1. Migration Error Scenarios

**Scenario**: 共通インフラストラクチャが未デプロイ
- **Detection**: `terraform_remote_state`データソースでエラー
- **Handling**: 明確なエラーメッセージと前提条件の表示
- **Recovery**: 共通インフラストラクチャの先行デプロイ

**Scenario**: 既存イメージの参照エラー
- **Detection**: Cloud Runデプロイ時のイメージプルエラー
- **Handling**: 既存イメージの新レジストリへの移行
- **Recovery**: イメージの再タグ付けとプッシュ

### 2. Runtime Error Handling

**Scenario**: 指定されたタグが存在しない
- **Detection**: Cloud Runサービス起動時のエラー
- **Handling**: フォールバック機能（デフォルトタグの使用）
- **Recovery**: 正しいタグでのイメージ再ビルド

### 3. Permission Error Handling

**Scenario**: IAM権限不足
- **Detection**: Artifact Registryアクセス時の403エラー
- **Handling**: 必要な権限の自動付与
- **Recovery**: サービスアカウント権限の再設定

## Testing Strategy

### 1. Unit Testing

**Terraform Validation**:
```bash
# 各環境での設定検証
terraform validate
terraform plan -var-file=dev.tfvars
terraform plan -var-file=prod.tfvars
```

**Configuration Testing**:
- 変数の型と制約の検証
- デフォルト値の妥当性確認
- 依存関係の整合性チェック

### 2. Integration Testing

**Cross-Environment Testing**:
- 共通リソースの複数環境からの参照
- 環境別タグの正しい解決
- IAM権限の適切な分離

**Migration Testing**:
- 段階的移行プロセスの検証
- ロールバック手順の確認
- データ整合性の維持

### 3. End-to-End Testing

**Deployment Pipeline Testing**:
```bash
# 1. 共通インフラストラクチャのデプロイ
cd terraform/common && terraform apply

# 2. 開発環境のデプロイ
cd terraform/dev && terraform apply -var-file=dev.tfvars

# 3. 本番環境のデプロイ
cd terraform/prod && terraform apply -var-file=prod.tfvars

# 4. 機能テスト
curl -f $CLOUD_RUN_URL/_stcore/health
```

**Image Tag Resolution Testing**:
- 環境別デフォルトタグの確認
- カスタムタグオーバーライドの動作
- CI/CDパイプラインでの自動タグ付け

### 4. Performance Testing

**Registry Access Performance**:
- イメージプル時間の測定
- 複数環境からの同時アクセス
- ネットワーク最適化の効果確認

**Deployment Time Impact**:
- 移行前後のデプロイ時間比較
- 初回デプロイと更新デプロイの差異
- リソース作成順序の最適化

## Migration Strategy

### Phase 1: Common Infrastructure Setup
1. `terraform/common/artifact_registry.tf`の作成
2. 共通インフラストラクチャのデプロイ
3. 既存イメージの新レジストリへの移行

### Phase 2: Module Updates
1. ImgStreamモジュールの更新
2. データソース参照の追加
3. イメージ参照ロジックの変更

### Phase 3: Environment Migration
1. 開発環境での検証デプロイ
2. 本番環境での段階的移行
3. 旧リソースのクリーンアップ

### Phase 4: Validation and Cleanup
1. 全環境での動作確認
2. 不要なリソースの削除
3. ドキュメントの更新
