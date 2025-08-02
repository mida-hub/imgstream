# ImgStream ドキュメント

このディレクトリには、ImgStreamプロジェクトの包括的なドキュメントが含まれています。

## 📚 ドキュメント構造

### 🚀 はじめに
- **[プロジェクト概要](../README.md)** - プロジェクト全体の概要とクイックスタート

### 🛠️ セットアップ・デプロイメント
- **[デプロイメントガイド](DEPLOYMENT_GUIDE.md)** - 開発環境から本番デプロイまでの完全ガイド
- **[GitHub OIDC設定](GITHUB_OIDC_SETUP.md)** - OIDC認証の詳細設定手順

### 💻 開発
- **[開発ガイド](DEVELOPMENT.md)** - 開発環境固有の設定と認証問題の解決
- **[品質チェックガイド](QUALITY_CHECK.md)** - コード品質管理とCI/CD品質チェック

### 🏗️ アーキテクチャ・技術
- **[アーキテクチャガイド](ARCHITECTURE.md)** - システム設計とコンポーネント構造
- **[トラブルシューティング](TROUBLESHOOTING.md)** - 一般的な問題の診断と解決

### 🔄 CI/CD・自動化
- **[デプロイメント自動化](DEPLOYMENT.md)** - CI/CDパイプラインと自動化戦略

## 📖 読書ガイド

### 初回セットアップ時
1. [プロジェクト概要](../README.md) - 全体像の把握
2. [デプロイメントガイド](DEPLOYMENT_GUIDE.md) - 実際のセットアップ実行
3. [開発ガイド](DEVELOPMENT.md) - 開発環境の詳細設定

### 本番デプロイ時
1. [デプロイメントガイド](DEPLOYMENT_GUIDE.md) - 本番デプロイメント手順
2. [GitHub OIDC設定](GITHUB_OIDC_SETUP.md) - セキュアな認証設定
3. [デプロイメント自動化](DEPLOYMENT.md) - CI/CDパイプライン設定

### 開発・保守時
1. [開発ガイド](DEVELOPMENT.md) - 日常的な開発作業
2. [品質チェックガイド](QUALITY_CHECK.md) - コード品質管理
3. [トラブルシューティング](TROUBLESHOOTING.md) - 問題解決

### システム理解時
1. [アーキテクチャガイド](ARCHITECTURE.md) - システム設計の理解
2. [デプロイメント自動化](DEPLOYMENT.md) - 自動化戦略の理解

## 🔗 関連リソース

### スクリプト
- **[デプロイメントスクリプト](../scripts/README.md)** - 自動化スクリプトの詳細

### インフラストラクチャ
- **[Terraform設定](../terraform/README.md)** - インフラストラクチャ as Code

### テスト
- **[パフォーマンステスト](../tests/performance/README.md)** - 性能テストの詳細
- **[セキュリティテスト](../tests/security/README.md)** - セキュリティテストの詳細

### CI/CD
- **[GitHub Actionsワークフロー](../.github/workflows/README.md)** - CI/CDパイプラインの詳細

## 🆘 サポート

問題が発生した場合：

1. **[トラブルシューティング](TROUBLESHOOTING.md)** を確認
2. **関連ログ** を確認（各ガイドに記載）
3. **GitHub Issues** で問題を報告
4. **プロジェクトディスカッション** で質問

## 📝 ドキュメント更新

ドキュメントの更新や改善提案は、以下の方法で行ってください：

1. **Pull Request** でドキュメント修正を提案
2. **GitHub Issues** で改善提案を報告
3. **定期レビュー** で内容の正確性を確認

---

このドキュメント構造は、ImgStreamプロジェクトの効率的な理解と使用をサポートするために設計されています。
