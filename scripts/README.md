# デプロイメントスクリプト

このディレクトリには、imgstream を様々な環境にデプロイするためのスクリプトが含まれています。

## スクリプト概要

- **`build-image.sh`**: アプリケーション用 Docker イメージのビルド
- **`cloud-run-image-update.sh`**: Cloud Run サービスのイメージ更新

## cloud-run-image-update.sh

Cloud Run サービスを指定された環境とイメージタグで更新します。

### 使用方法

```bash
./cloud-run-image-update.sh <environment> [image_tag]
```

### パラメータ

- `environment`: 必須。`dev` または `prod`
- `image_tag`: オプション。デフォルトは `latest`

### 使用例

```bash
# dev環境にlatestイメージをデプロイ
./cloud-run-image-update.sh dev

# prod環境にlatestイメージをデプロイ
./cloud-run-image-update.sh prod

# dev環境に特定のタグをデプロイ
./cloud-run-image-update.sh dev v1.2.3

# prod環境に特定のタグをデプロイ
./cloud-run-image-update.sh prod v1.2.3
```

## ワークフロー

1. まず、イメージをビルドしてプッシュ：

   ```bash
   ./build-image.sh
   ```

2. 次に、目的の環境に Cloud Run サービスを更新：

   ```bash
   # 開発環境の場合
   ./cloud-run-image-update.sh dev

   # 本番環境の場合
   ./cloud-run-image-update.sh prod

   # 特定のイメージタグを使用する場合
   ./cloud-run-image-update.sh prod v1.2.3
   ```
