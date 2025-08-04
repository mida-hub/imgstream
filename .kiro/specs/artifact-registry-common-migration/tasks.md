# Implementation Plan

- [x] 1. 共通インフラストラクチャにArtifact Registry設定を作成
  - `terraform/common/artifact_registry.tf`ファイルを作成
  - 共有Artifact Registryリソースを定義
  - GitHub Actions用のIAM権限を設定
  - _Requirements: 1.1, 3.1, 3.4_

- [x] 2. 共通インフラストラクチャの出力設定を更新
  - `terraform/common/outputs.tf`にArtifact Registry情報を追加
  - レジストリURLとロケーション情報を出力
  - 他の環境から参照可能な形式で定義
  - _Requirements: 1.2, 1.3_

- [x] 3. 共通インフラストラクチャの変数設定を更新
  - `terraform/common/variables.tf`に必要な変数を追加
  - プロジェクトIDとリージョン設定を確認
  - Cloud Runサービスアカウントリストの変数を追加
  - _Requirements: 3.2, 3.3_

- [x] 4. ImgStreamモジュールからArtifact Registry設定を削除
  - `terraform/modules/imgstream/artifact_registry.tf`ファイルを削除
  - 関連するIAM設定を共通インフラストラクチャに移行
  - モジュール内の依存関係を更新
  - _Requirements: 1.4_

- [x] 5. ImgStreamモジュールに共通レジストリ参照を追加
  - `terraform/modules/imgstream/main.tf`にデータソースを追加
  - 共通インフラストラクチャのステートを参照する設定
  - ローカル変数でイメージURL構築ロジックを実装
  - _Requirements: 1.2, 1.3, 2.3_

- [x] 6. 環境別のタグ管理変数を実装
  - `terraform/modules/imgstream/variables.tf`にタグ関連変数を追加
  - デフォルトタグマッピングの定義
  - カスタムタグオーバーライド機能の実装
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 7. Cloud Run設定でのイメージ参照を更新
  - `terraform/modules/imgstream/cloud_run.tf`のイメージ参照を修正
  - 共通レジストリからの動的イメージURL生成
  - 環境別タグの適用ロジックを実装
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 8. 開発環境設定を更新
  - `terraform/dev/variables.tf`にタグ関連変数を追加
  - `terraform/dev/dev.tfvars`にデフォルトタグ設定を追加
  - 共通レジストリ参照のための設定を確認
  - _Requirements: 2.1, 2.4_

- [x] 9. 本番環境設定を更新
  - `terraform/prod/variables.tf`にタグ関連変数を追加
  - `terraform/prod/prod.tfvars`にデフォルトタグ設定を追加
  - 本番環境用の安定タグ設定を実装
  - _Requirements: 2.2, 2.4_

- [x] 10. 共通インフラストラクチャのデプロイとテスト
  - 共通インフラストラクチャを先行デプロイ
  - Artifact Registryの作成を確認
  - IAM権限の設定を検証
  - _Requirements: 1.1, 3.1, 3.4_

- [x] 11. 開発環境での移行テスト
  - 開発環境で新しい設定をデプロイ
  - 共通レジストリからのイメージ参照を確認
  - デフォルトタグ（latest）の動作を検証
  - _Requirements: 1.2, 2.1, 4.2_

- [ ] 12. 本番環境での移行実行
  - 本番環境で新しい設定をデプロイ
  - 安定タグでのイメージ参照を確認
  - サービス継続性を検証
  - _Requirements: 1.3, 2.2, 4.1_

- [ ] 13. 移行後の検証とクリーンアップ
  - 全環境での動作確認テストを実行
  - 旧Artifact Registryリソースの削除
  - ドキュメントの更新
  - _Requirements: 4.2, 4.3_

- [ ] 14. CI/CDパイプライン設定の更新
  - GitHub Actionsワークフローでの共通レジストリ使用
  - 環境別タグ付けロジックの実装
  - 自動デプロイメントプロセスの検証
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 15. エラーハンドリングとロールバック手順の文書化
  - 移行プロセスでの各種エラーシナリオの対処法
  - ロールバック手順の詳細化
  - トラブルシューティングガイドの作成
  - _Requirements: 4.3, 4.4_
