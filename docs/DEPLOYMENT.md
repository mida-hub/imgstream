# デプロイメントガイド

このドキュメントでは、imgstreamアプリケーションのデプロイメント手順について説明します。

## 前提条件

1. **Google Cloud Platform**
   - GCPプロジェクトが作成済み
   - 必要なAPIが有効化済み
   - サービスアカウントが作成済み

2. **GitHub**
   - リポジトリがGitHubに作成済み
   - GitHub Actionsが有効

3. **ローカル環境**
   - Docker がインストール済み
   - gcloud CLI がインストール済み

## GitHub Secrets の設定

デプロイメントワークフローを実行するために、以下のシークレットをGitHubリポジトリに設定してください。

### 必須シークレット

| シークレット名 | 説明 | 例 |
|---|---|---|
| `GCP_SA_KEY` | GCPサービスアカウントキー（JSON形式） | `{"type": "service_account", ...}` |
| `GCP_PROJECT_ID` | GCPプロジェクトID | `my-imgstream-project` |
| `GCS_BUCKET_DEV` | 開発環境用GCSバケット名 | `my-project-imgstream-dev` |
| `GCS_BUCKET_PROD` | 本番環境用GCSバケット名 | `my-project-imgstream-prod` |

### オプションシークレット

| シークレット名 | 説明 | 例 |
|---|---|---|
| `PROD_DOMAIN_URL` | 本番環境のカスタムドメインURL | `https://imgstream.example.com` |
| `SONAR_TOKEN` | SonarCloudトークン | `sqp_...` |

### サービスアカウントの作成と設定

1. **サービスアカウントの作成**
   ```bash
   gcloud iam service-accounts create imgstream-deploy \
     --display-name="imgstream Deployment Service Account" \
     --project=YOUR_PROJECT_ID
   ```

2. **必要な権限の付与**
   ```bash
   # Cloud Run管理者
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/run.admin"
   
   # Storage管理者
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   
   # Container Registry管理者
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   
   # IAM管理者（Cloud Runサービスアカウント作成用）
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"
   ```

3. **サービスアカウントキーの作成**
   ```bash
   gcloud iam service-accounts keys create key.json \
     --iam-account=imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

4. **GitHubシークレットの設定**
   - GitHubリポジトリの Settings > Secrets and variables > Actions
   - `GCP_SA_KEY` に `key.json` の内容をコピー

## デプロイメント方法

### 1. 自動デプロイメント（推奨）

**開発環境への自動デプロイ**
- `main` ブランチにプッシュすると自動的に開発環境にデプロイされます

**本番環境への自動デプロイ**
- `v*` タグをプッシュすると本番環境にデプロイされます
  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```

**手動デプロイ**
- GitHub Actions の "Build and Deploy" ワークフローを手動実行
- 環境（dev/prod）を選択して実行

### 2. ローカルからのデプロイ

**Dockerイメージのビルド**
```bash
# イメージをビルドしてプッシュ
./scripts/build-image.sh -p YOUR_PROJECT_ID -t latest --push

# 特定のタグでビルド
./scripts/build-image.sh -p YOUR_PROJECT_ID -t v1.0.0 --push
```

**Cloud Runへのデプロイ**
```bash
# 開発環境にデプロイ
./scripts/deploy-cloud-run.sh -p YOUR_PROJECT_ID -e dev -i gcr.io/YOUR_PROJECT_ID/imgstream:latest

# 本番環境にデプロイ
./scripts/deploy-cloud-run.sh -p YOUR_PROJECT_ID -e prod -i gcr.io/YOUR_PROJECT_ID/imgstream:v1.0.0
```

## 環境設定

### 開発環境

- **認証**: パブリックアクセス（認証なし）
- **スケーリング**: 0-3インスタンス
- **リソース**: 1Gi メモリ、1 CPU
- **URL**: Cloud Run自動生成URL

### 本番環境

- **認証**: Cloud IAP（認証必須）
- **スケーリング**: 1-10インスタンス
- **リソース**: 2Gi メモリ、1 CPU
- **URL**: カスタムドメイン（設定済みの場合）

## ヘルスチェック

デプロイ後、以下のエンドポイントでアプリケーションの健全性を確認できます：

- **ヘルスチェックページ**: `https://your-app-url/health`
- **JSON形式**: `https://your-app-url/health?format=json`

### ヘルスチェック項目

1. **データベース接続**: DuckDB接続テスト
2. **ストレージ接続**: Google Cloud Storage接続テスト
3. **環境設定**: 必要な環境変数の確認

## トラブルシューティング

### よくある問題

1. **デプロイが失敗する**
   - GitHub Secretsが正しく設定されているか確認
   - サービスアカウントの権限を確認
   - Cloud Run APIが有効になっているか確認

2. **ヘルスチェックが失敗する**
   - 環境変数が正しく設定されているか確認
   - GCSバケットが存在するか確認
   - サービスアカウントの権限を確認

3. **アプリケーションにアクセスできない**
   - Cloud IAP設定を確認（本番環境）
   - DNS設定を確認（カスタムドメイン使用時）
   - SSL証明書の状態を確認

### ログの確認

```bash
# Cloud Runログの確認
gcloud logs read "resource.type=cloud_run_revision" --project=YOUR_PROJECT_ID --limit=50

# 特定のサービスのログ
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=imgstream-prod" --project=YOUR_PROJECT_ID
```

### ロールバック

デプロイに問題がある場合、以前のリビジョンにロールバックできます：

```bash
# 利用可能なリビジョンを確認
gcloud run revisions list --service=imgstream-prod --region=us-central1

# 特定のリビジョンにロールバック
gcloud run services update-traffic imgstream-prod \
  --to-revisions=REVISION_NAME=100 \
  --region=us-central1
```

## セキュリティ考慮事項

1. **サービスアカウント**
   - 最小権限の原則に従って権限を設定
   - 定期的にキーをローテーション

2. **シークレット管理**
   - GitHub Secretsを適切に設定
   - 本番環境の情報を開発環境と分離

3. **ネットワークセキュリティ**
   - Cloud IAP設定（本番環境）
   - HTTPS強制
   - 適切なCORS設定

## 監視とアラート

1. **Cloud Run監視**
   - リクエスト数、レスポンス時間
   - エラー率、可用性

2. **アプリケーション監視**
   - ヘルスチェック結果
   - アプリケーションログ

3. **アラート設定**
   - サービス停止時のアラート
   - エラー率上昇時のアラート

## 参考リンク

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Cloud IAP Documentation](https://cloud.google.com/iap/docs)
