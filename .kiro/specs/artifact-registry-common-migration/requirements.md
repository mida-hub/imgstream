# Requirements Document

## Introduction

この機能は、現在ImgStreamモジュール内にある`google_artifact_registry_repository`リソースを共通インフラストラクチャ（common）に移動し、prod/dev環境でタグによってイメージを切り替える仕組みを実装します。これにより、コンテナレジストリを一元管理し、環境間でのイメージ管理を効率化します。

## Requirements

### Requirement 1

**User Story:** インフラストラクチャ管理者として、Artifact Registryを共通リソースとして管理したい。これにより、複数環境でのコンテナレジストリの重複を避け、一元管理できるようになる。

#### Acceptance Criteria

1. WHEN 共通インフラストラクチャをデプロイする THEN Artifact Registryリポジトリが作成される SHALL
2. WHEN dev環境をデプロイする THEN 共通のArtifact Registryを参照する SHALL
3. WHEN prod環境をデプロイする THEN 共通のArtifact Registryを参照する SHALL
4. WHEN 既存のモジュールからArtifact Registry設定を削除する THEN 機能に影響しない SHALL

### Requirement 2

**User Story:** 開発者として、環境ごとに異なるコンテナイメージタグを使用したい。これにより、開発環境では最新のイメージを、本番環境では安定したイメージを使用できる。

#### Acceptance Criteria

1. WHEN dev環境でデプロイする THEN `latest`または`dev`タグのイメージを使用する SHALL
2. WHEN prod環境でデプロイする THEN 特定のバージョンタグ（例：`v1.0.0`）のイメージを使用する SHALL
3. WHEN 環境変数でイメージタグを指定する THEN そのタグが使用される SHALL
4. WHEN タグが指定されていない場合 THEN 環境に応じたデフォルトタグが使用される SHALL

### Requirement 3

**User Story:** システム管理者として、Artifact Registryへのアクセス権限を適切に管理したい。これにより、各環境のCloud Runサービスが必要な権限でイメージを取得できる。

#### Acceptance Criteria

1. WHEN 共通Artifact Registryを作成する THEN 適切なIAM権限が設定される SHALL
2. WHEN dev環境のCloud Runサービスアカウントを作成する THEN Artifact Registryへの読み取り権限が付与される SHALL
3. WHEN prod環境のCloud Runサービスアカウントを作成する THEN Artifact Registryへの読み取り権限が付与される SHALL
4. WHEN GitHub Actionsからイメージをプッシュする THEN 適切な書き込み権限が設定される SHALL

### Requirement 4

**User Story:** 運用担当者として、既存のデプロイメントプロセスに影響を与えずに移行したい。これにより、サービスの中断なく新しい構成に移行できる。

#### Acceptance Criteria

1. WHEN 移行を実行する THEN 既存のCloud Runサービスが継続して動作する SHALL
2. WHEN 新しい構成をデプロイする THEN 既存のコンテナイメージが引き続き使用可能である SHALL
3. WHEN 移行後にロールバックが必要な場合 THEN 元の構成に戻すことができる SHALL
4. WHEN 移行プロセスを実行する THEN ステップバイステップの手順が提供される SHALL

### Requirement 5

**User Story:** 開発チームとして、CI/CDパイプラインでの環境別イメージ管理を自動化したい。これにより、手動でのタグ管理を不要にし、デプロイメントプロセスを効率化できる。

#### Acceptance Criteria

1. WHEN GitHub Actionsでビルドする THEN 環境に応じたタグが自動的に付与される SHALL
2. WHEN dev環境にデプロイする THEN 最新のdevタグが自動的に使用される SHALL
3. WHEN prod環境にデプロイする THEN 指定されたリリースタグが使用される SHALL
4. WHEN タグ管理の設定を変更する THEN 環境変数で制御できる SHALL
