# ImgStream Terraform インフラストラクチャ

このディレクトリには、Google Cloud Platform上のImgStream写真管理アプリケーションインフラストラクチャのTerraform設定が含まれています。

## ディレクトリ構造

```
terraform/
├── common/                 # 共有リソース (GitHub OIDC) - 一度だけデプロイ
│   ├── main.tf
│   ├── github-oidc.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars
├── modules/
│   └── imgstream/         # ImgStreamアプリケーションモジュール
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── storage.tf
│       ├── cloud_run.tf
│       ├── artifact_registry.tf
│       ├── iap.tf
│       ├── security.tf
│       └── monitoring.tf
├── dev/                   # 開発環境
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── dev.tfvars
├── prod/                  # 本番環境
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── prod.tfvars
# バックエンド設定はmain.tfファイルに埋め込まれています
└── README.md
```

## アーキテクチャ概要

### 共有リソース
- **GitHub OIDC**: GitHub Actions認証用のWorkload Identity PoolとProvider
- **サービスアカウント**: 必要な権限を持つGitHub Actionsサービスアカウント

### ImgStreamモジュール
- **Cloud Run**: コンテナ化されたアプリケーションのデプロイ
- **Cloud Storage**: 写真保存とデータベースバックアップ用バケット
- **Artifact Registry**: コンテナイメージリポジトリ
- **IAP (Identity-Aware Proxy)**: 認証と認可
- **Cloud Armor**: セキュリティポリシーとWAFルール
- **Monitoring**: アラート、ダッシュボード、通知チャネル

## 使用方法

### 前提条件

1. Terraform >= 1.12をインストール
2. Google Cloud SDKをインストール
3. Google Cloudで認証:
   ```bash
   gcloud auth application-default login
   ```
4. ステート保存用のGCSバケット `apps-466614-terraform-state` が存在することを確認

### デプロイ順序

**重要**: 依存関係の問題を避けるため、この順序でデプロイしてください。

#### 1. 共通インフラストラクチャ（一度だけデプロイ）

最初に共有GitHub OIDCリソースをデプロイ:

```bash
cd terraform/common
terraform init
terraform plan
terraform apply
```

#### 2. 開発環境

```bash
cd terraform/dev
terraform init
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

#### 3. 本番環境

```bash
cd terraform/prod
terraform init
terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

## 設定

### 機密情報の管理

**重要**: このリポジトリは公開されているため、個人情報（メールアドレスなど）をバージョン管理にコミットしないでください。

#### オプション1: 環境変数（推奨）
環境変数を使用して機密値を設定:

```bash
# 環境変数を設定
export TF_VAR_allowed_users='["user1@example.com","user2@example.com"]'
export TF_VAR_iap_support_email="support@example.com"
export TF_VAR_alert_email="alerts@example.com"

# その後terraformを実行
terraform apply -var-file=dev.tfvars
```

#### オプション2: ローカル設定ファイル
gitにコミットされないローカル設定ファイルを作成:

```bash
# サンプルファイルをコピー
cp terraform.tfvars.local.example terraform.tfvars.local

# 実際の値で編集
vim terraform.tfvars.local

# デプロイスクリプトが自動的にこのファイルを含めます
```

### 環境変数

各環境には環境固有の設定を含む独自の `.tfvars` ファイルがあります:

- **dev.tfvars**: 開発環境設定
  - パブリックアクセス有効
  - IAP無効
  - コスト削減のための最小インスタンス
  - 緩和されたセキュリティポリシー

- **prod.tfvars**: 本番環境設定
  - セキュリティのためのIAP有効
  - 可用性のための最小インスタンス
  - 完全なセキュリティポリシー有効
  - 本番グレードの監視

### 主要設定オプション

| 変数 | 説明 | 開発環境デフォルト | 本番環境デフォルト |
|----------|-------------|-------------|--------------|
| `enable_public_access` | パブリックアクセスを許可 | `true` | `false` |
| `enable_iap` | Identity-Aware Proxyを有効化 | `false` | `true` |
| `min_instances` | Cloud Runの最小インスタンス数 | `0` | `1` |
| `max_instances` | Cloud Runの最大インスタンス数 | `3` | `10` |
| `enable_security_policy` | Cloud Armorを有効化 | `false` | `true` |
| `enable_waf_rules` | WAFルールを有効化 | `false` | `true` |

## 出力

デプロイが成功すると、Terraformは重要な情報を出力します:

- **cloud_run_service_url**: デプロイされたアプリケーションのURL
- **artifact_registry_repository_url**: コンテナレジストリのURL
- **photos_bucket_name**: 写真保存用のGCSバケット
- **workload_identity_provider**: GitHub Actions OIDCプロバイダー
- **monitoring_dashboard_url**: 監視ダッシュボードへのリンク

## セキュリティ機能

### Identity-Aware Proxy (IAP)
- OAuth ベースの認証
- ユーザーとドメインベースのアクセス制御
- セッション管理

### Cloud Armor セキュリティポリシー
- レート制限
- 地理的制限
- XSSとSQLインジェクション保護
- カスタムセキュリティルール

### ストレージセキュリティ
- 統一バケットレベルアクセス
- サービスアカウントベースの権限
- ライフサイクル管理
- データベースバックアップのバージョニング

## 監視とアラート

### アラートポリシー
- サービス可用性監視
- 高エラー率検出
- レスポンス時間監視
- リソース使用率アラート
- ストレージ使用量監視

### 通知チャネル
- メール通知
- Slack統合（オプション）
- カスタムWebhookサポート

### ダッシュボード
- リアルタイムメトリクス可視化
- リクエスト率とエラー追跡
- リソース使用率監視
- ストレージ使用量分析

## メンテナンス

### インフラストラクチャの更新

1. 適切な `.tfvars` ファイルを修正
2. `terraform plan` を実行して変更を確認
3. `terraform apply` を実行して変更を適用

### 新しい環境の追加

1. 新しいディレクトリを作成（例: `staging/`）
2. `dev/` または `prod/` からファイルをコピー
3. 環境固有の `.tfvars` ファイルを作成
4. バックエンド設定ファイルを作成
5. 初期化して適用

### モジュールの更新

ImgStreamモジュールはバージョン管理されており、独立して更新できます。更新時:

1. モジュールの変更を確認
2. 最初に開発環境でテスト
3. 検証後に本番環境に適用

## トラブルシューティング

### よくある問題

1. **バックエンド初期化の失敗**
   - GCSバケット `apps-466614-terraform-state` が存在することを確認
   - バケットの権限を確認
   - 共通インフラストラクチャを最初にデプロイしたことを確認

2. **リモートステートデータソースの失敗**
   - 共通インフラストラクチャが最初にデプロイされていることを確認
   - 共通ステートがGCSバケットに存在することを確認

3. **IAP設定の失敗**
   - OAuth同意画面が設定されていることを確認
   - ドメイン検証を確認

4. **Cloud Runデプロイの失敗**
   - コンテナイメージがArtifact Registryに存在することを確認
   - サービスアカウントの権限を確認

### ヘルプの取得

- Terraformログを確認: `terraform apply -debug`
- リソースステータスについてGoogle Cloud Consoleを確認
- 設定を検証: `terraform validate`
- コードをフォーマット: `terraform fmt -recursive`

## ベストプラクティス

1. **ステート管理**
   - リモートステートストレージ（GCS）を使用
   - ステートロックを有効化
   - 定期的なステートバックアップ

2. **セキュリティ**
   - 最小権限のサービスアカウントを使用
   - 監査ログを有効化
   - 定期的なセキュリティレビュー

3. **コスト最適化**
   - 適切なインスタンスサイジングを使用
   - ライフサイクルポリシーを実装
   - リソース使用量を監視

4. **デプロイメント**
   - 最初に開発環境でテスト
   - Infrastructure as Codeを使用
   - 適切なCI/CDパイプラインを実装
