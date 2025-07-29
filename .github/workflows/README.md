# GitHub Actions ワークフロー仕様書

このディレクトリには、ImgStreamアプリケーションのCI/CDパイプラインを構成するGitHub Actionsワークフローが含まれています。

## 📋 ワークフロー一覧

| ワークフロー | ファイル | 目的 | トリガー |
|-------------|---------|------|----------|
| [Build and Deploy](#build-and-deploy) | `deploy.yml` | アプリケーションのビルド・デプロイ | `main`ブランチへのpush、タグ、手動実行 |
| [E2E Tests](#e2e-tests) | `e2e-tests.yml` | エンドツーエンドテスト | push、PR、スケジュール、手動実行 |
| [Security Scan](#security-scan) | `security.yml` | セキュリティスキャン | スケジュール、push、PR |
| [Test and Lint](#test-and-lint) | `test.yml` | 単体テスト・リント・品質チェック | push、PR |

## 🚀 Build and Deploy

**ファイル**: `deploy.yml`

### 概要
アプリケーションのDockerイメージをビルドし、開発環境・本番環境にデプロイするワークフローです。

### トリガー条件
- `main`ブランチへのpush
- `v*`形式のタグ作成
- 手動実行（環境選択可能）

### ジョブ構成

#### 1. build
- **目的**: Dockerイメージのビルドとレジストリへのプッシュ
- **実行環境**: ubuntu-latest
- **主要ステップ**:
  - ソースコードのチェックアウト
  - Docker Buildxのセットアップ
  - Google Cloud認証
  - Artifact Registryへの認証設定
  - メタデータの抽出（タグ、ラベル）
  - Dockerイメージのビルド・プッシュ
  - SBOM（Software Bill of Materials）の生成
- **出力**: イメージタグ、イメージダイジェスト

#### 2. security-scan-image
- **目的**: ビルドしたDockerイメージの脆弱性スキャン
- **依存**: build
- **主要ステップ**:
  - Trivyによる脆弱性スキャン
  - SARIF形式でのGitHub Security tabへのアップロード
  - 重要度HIGH/CRITICALの脆弱性チェック

#### 3. deploy-dev
- **目的**: 開発環境へのデプロイ
- **依存**: build, security-scan-image
- **条件**: `main`ブランチまたは手動実行で`dev`選択時
- **環境**: development
- **主要ステップ**:
  - Cloud Runサービス`imgstream-dev`へのデプロイ
  - ヘルスチェック（`/_stcore/health`エンドポイント）
  - スモークテスト
  - デプロイ状況の通知

#### 4. deploy-prod
- **目的**: 本番環境へのデプロイ
- **依存**: build, security-scan-image, deploy-dev
- **条件**: `v*`タグまたは手動実行で`prod`選択時
- **環境**: production
- **主要ステップ**:
  - Cloud Runサービス`imgstream-prod`へのデプロイ
  - IAP経由でのヘルスチェック
  - GitHubリリースの作成（タグの場合）

#### 5. rollback
- **目的**: デプロイ失敗時の自動ロールバック
- **条件**: deploy-dev または deploy-prod が失敗した場合
- **環境**: production
- **主要ステップ**:
  - 前のリビジョンの取得
  - トラフィックの前のリビジョンへの切り替え

### 環境変数
- `REGISTRY`: asia-northeast1-docker.pkg.dev
- `IMAGE_NAME`: imgstream
- `PYTHON_VERSION`: "3.11"

### 必要なシークレット
- `GCP_SA_KEY`: Google Cloud サービスアカウントキー
- `GCP_PROJECT_ID`: Google Cloud プロジェクトID
- `GCS_BUCKET_DEV`: 開発環境用GCSバケット名
- `GCS_BUCKET_PROD`: 本番環境用GCSバケット名
- `PROD_DOMAIN_URL`: 本番環境のドメインURL

## 🧪 E2E Tests

**ファイル**: `e2e-tests.yml`

### 概要
アプリケーションのエンドツーエンドテストを実行するワークフローです。

### トリガー条件
- `main`, `develop`ブランチへのpush
- `main`, `develop`ブランチへのPR
- 毎日3:00 UTC（スケジュール実行）
- 手動実行（環境・テストスイート選択可能）

### ジョブ構成

#### 1. e2e-unit-style
- **目的**: 単体テストスタイルのE2Eテスト実行
- **実行環境**: ubuntu-latest
- **テスト内容**:
  - 認証フローテスト
  - アップロードフローテスト
  - エラーシナリオテスト
- **成果物**: JUnit XML形式のテスト結果

#### 2. e2e-integration
- **目的**: 統合環境でのE2Eテスト
- **依存**: e2e-unit-style
- **条件**: pushまたは手動実行時
- **サービス**: fake-gcs-server（GCSモック）
- **主要ステップ**:
  - テスト環境のセットアップ
  - Dockerイメージのビルド
  - アプリケーションコンテナの起動
  - 統合E2Eテストの実行
  - ログとカバレッジレポートの収集

#### 3. e2e-live-environment
- **目的**: 実際の環境に対するE2Eテスト
- **条件**: 手動実行時のみ
- **環境**: 選択された環境（dev/staging）
- **テストスイート選択可能**:
  - all: 全テスト
  - auth-flow: 認証フローのみ
  - upload-flow: アップロードフローのみ
  - error-scenarios: エラーシナリオのみ

#### 4. e2e-performance
- **目的**: パフォーマンステスト
- **条件**: スケジュール実行または手動実行（全テスト選択時）
- **成果物**: ベンチマーク結果（JSON形式）

#### 5. e2e-report
- **目的**: E2Eテスト結果のレポート生成
- **依存**: e2e-unit-style, e2e-integration
- **条件**: 常に実行（依存ジョブの成功・失敗に関わらず）

### 必要なシークレット
- `DEV_APP_URL`: 開発環境のアプリケーションURL
- `STAGING_APP_URL`: ステージング環境のアプリケーションURL

## 🔒 Security Scan

**ファイル**: `security.yml`

### 概要
アプリケーションのセキュリティ脆弱性をスキャンするワークフローです。

### トリガー条件
- 毎日2:00 UTC（スケジュール実行）
- `main`ブランチへのpush
- `main`ブランチへのPR

### ジョブ構成

#### 1. security-scan
- **目的**: 静的解析とライブラリ脆弱性スキャン
- **実行環境**: ubuntu-latest
- **スキャンツール**:
  - **Bandit**: Pythonコードの静的セキュリティ解析
  - **Safety**: 依存関係の既知の脆弱性チェック
- **成果物**: JSON形式のスキャン結果
- **PR機能**: PR作成時にセキュリティ結果をコメントで通知

#### 2. codeql-analysis
- **目的**: GitHubのCodeQL静的解析
- **言語**: Python
- **権限**: security-events書き込み権限が必要
- **結果**: GitHub Security tabに表示

#### 3. dependency-review
- **目的**: 依存関係の変更レビュー
- **条件**: PR作成時のみ
- **設定**:
  - 中程度以上の脆弱性で失敗
  - 許可ライセンス: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC

## ✅ Test and Lint

**ファイル**: `test.yml`

### 概要
コード品質チェック、単体テスト、リントを実行するワークフローです。

### トリガー条件
- `main`, `develop`ブランチへのpush
- `main`, `develop`ブランチへのPR

### ジョブ構成

#### 1. test
- **目的**: メインのテスト・リント実行
- **実行環境**: ubuntu-latest
- **チェック項目**:
  - **Black**: コードフォーマットチェック
  - **Ruff**: リント（構文・スタイルチェック）
  - **MyPy**: 型チェック
  - **Pytest**: 単体・統合テスト（カバレッジ付き）
- **カバレッジ**: Codecovにアップロード

#### 2. security-scan
- **目的**: セキュリティスキャン（軽量版）
- **ツール**: Bandit, Safety
- **成果物**: セキュリティレポート

#### 3. docker-build-test
- **目的**: Dockerイメージのビルドテスト
- **検証**: イメージのビルド成功とインポートテスト

#### 4. code-quality
- **目的**: コード品質解析
- **ツール**: SonarCloud（設定されている場合）
- **要件**: `SONAR_TOKEN`シークレットが必要

#### 5. performance-test
- **目的**: パフォーマンステスト
- **条件**: PR作成時のみ
- **成果物**: ベンチマーク結果

## 🔧 設定要件

### 必要なシークレット

#### 共通
- `GITHUB_TOKEN`: GitHub API アクセス（自動設定）

#### デプロイ関連
- `GCP_SA_KEY`: Google Cloud サービスアカウントの認証キー（JSON形式）
- `GCP_PROJECT_ID`: Google Cloud プロジェクトID
- `GCS_BUCKET_DEV`: 開発環境用GCSバケット名
- `GCS_BUCKET_PROD`: 本番環境用GCSバケット名
- `PROD_DOMAIN_URL`: 本番環境のドメインURL

#### テスト関連
- `DEV_APP_URL`: 開発環境のアプリケーションURL
- `STAGING_APP_URL`: ステージング環境のアプリケーションURL

#### コード品質関連（オプション）
- `SONAR_TOKEN`: SonarCloudアクセストークン

### 環境設定

#### GitHub Environments
以下の環境を設定する必要があります：
- `development`: 開発環境デプロイ用
- `production`: 本番環境デプロイ用

#### 権限設定
- `security-events: write`: CodeQL解析結果のアップロード用
- `contents: read`: リポジトリ内容の読み取り用
- `actions: read`: アクション実行情報の読み取り用

## 📊 ワークフロー実行パターン

### 通常の開発フロー
1. **feature ブランチでの開発**
   - PR作成時: `test.yml`, `security.yml` が実行
   - コード品質・セキュリティチェック

2. **main ブランチへのマージ**
   - `test.yml`, `security.yml`, `deploy.yml`, `e2e-tests.yml` が実行
   - 開発環境への自動デプロイ

3. **リリース（タグ作成）**
   - `deploy.yml` が実行
   - 本番環境への自動デプロイ
   - GitHubリリースの作成

### 定期実行
- **毎日2:00 UTC**: セキュリティスキャン
- **毎日3:00 UTC**: E2Eテスト

### 手動実行
- **デプロイ**: 環境選択可能（dev/prod）
- **E2Eテスト**: 環境・テストスイート選択可能

## 🚨 トラブルシューティング

### よくある問題

#### 1. デプロイ失敗
- **原因**: 認証エラー、リソース不足、設定ミス
- **対処**: ログを確認し、自動ロールバック機能を活用
- **確認項目**: GCPシークレット、サービスアカウント権限

#### 2. テスト失敗
- **原因**: 依存関係の問題、環境設定ミス
- **対処**: ローカルでのテスト実行、依存関係の更新
- **確認項目**: Python バージョン、uv の設定

#### 3. セキュリティスキャン警告
- **原因**: 脆弱性のある依存関係、不安全なコード
- **対処**: 依存関係の更新、コードの修正
- **確認項目**: Bandit, Safety の結果

### デバッグ方法
1. **ワークフロー実行ログの確認**
2. **アーティファクトのダウンロード・確認**
3. **ローカル環境での再現テスト**
4. **シークレット・環境変数の確認**

## 📈 メトリクス・監視

### 収集される情報
- **テストカバレッジ**: Codecov経由
- **セキュリティスキャン結果**: GitHub Security tab
- **パフォーマンスベンチマーク**: アーティファクトとして保存
- **デプロイ成功率**: ワークフロー実行履歴

### 監視ポイント
- ワークフロー実行時間の増加
- テスト失敗率の上昇
- セキュリティ脆弱性の検出
- デプロイ失敗の頻度

---

## 📝 更新履歴

このREADMEは、ワークフローファイルの変更に合わせて定期的に更新してください。

最終更新: 2025年1月
