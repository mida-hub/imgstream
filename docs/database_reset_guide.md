# データベースリセット機能ガイド

## 概要

データベースリセット機能は、開発・テスト環境でローカルDuckDBファイルを削除し、Google Cloud Storageから最新のデータベースを再ダウンロードする機能です。

⚠️ **重要**: この機能は開発・テスト環境でのみ利用可能で、本番環境では無効化されています。

## 主な機能

### 1. データベースリセット (`force_reload_from_gcs`)

ローカルデータベースを完全にリセットし、GCSから最新版をダウンロードします。

```python
from imgstream.services.metadata import get_metadata_service

# メタデータサービスを取得
metadata_service = get_metadata_service("user_id")

# データベースリセットを実行（確認が必要）
result = metadata_service.force_reload_from_gcs(confirm_reset=True)

print(f"リセット結果: {result['success']}")
print(f"処理時間: {result['reset_duration_seconds']:.2f}秒")
```

### 2. データベース情報取得 (`get_database_info`)

現在のデータベース状態を確認します。

```python
info = metadata_service.get_database_info()

print(f"ローカルDB存在: {info['local_db_exists']}")
print(f"GCS DB存在: {info['gcs_db_exists']}")
print(f"写真数: {info['photo_count']}")
print(f"最終同期: {info['last_sync_time']}")
```

### 3. データベース整合性検証 (`validate_database_integrity`)

データベースの整合性をチェックします。

```python
validation = metadata_service.validate_database_integrity()

if validation['valid']:
    print("✅ データベースは正常です")
else:
    print("❌ 整合性の問題が見つかりました:")
    for issue in validation['issues']:
        print(f"  - {issue}")
```

## 管理API

### 環境チェック

```python
from imgstream.api.database_admin import is_development_environment

if is_development_environment():
    print("開発環境で実行中")
else:
    print("本番環境では利用できません")
```

### ユーザーデータベースリセット

```python
from imgstream.api.database_admin import reset_user_database

try:
    result = reset_user_database("user_id", confirm_reset=True)
    print(f"リセット完了: {result['message']}")
except DatabaseAdminError as e:
    print(f"リセット失敗: {e}")
```

### データベース状態取得

```python
from imgstream.api.database_admin import get_database_status

status = get_database_status("user_id")
print(f"データベース情報: {status['database_info']}")
print(f"整合性検証: {status['integrity_validation']}")
```

## Streamlit管理パネル

開発環境では、Streamlit UIを使用してデータベース管理を行えます。

```python
from imgstream.api.database_admin import render_database_admin_panel

# Streamlitアプリ内で管理パネルを表示
render_database_admin_panel()
```

### 管理パネルの機能

1. **環境情報表示**: 現在の実行環境を確認
2. **データベース状態確認**: ローカル・GCSデータベースの状態表示
3. **整合性検証**: データベースの整合性チェック
4. **データベースリセット**: 安全確認付きリセット機能
5. **一括操作**: 複数ユーザーの一括検証（将来実装予定）

## 安全性機能

### 1. 環境制限

```python
# 本番環境では自動的にエラーが発生
ENVIRONMENT=production python -c "
from imgstream.api.database_admin import reset_user_database
reset_user_database('user', confirm_reset=True)  # DatabaseAdminError
"
```

### 2. 確認必須

```python
# 確認なしではリセットできない
metadata_service.force_reload_from_gcs()  # MetadataError
metadata_service.force_reload_from_gcs(confirm_reset=False)  # MetadataError
metadata_service.force_reload_from_gcs(confirm_reset=True)  # OK
```

### 3. 詳細ログ記録

すべての操作は詳細にログ記録され、監査証跡が残ります。

```python
# ログ例
2023-01-01 12:00:00 [WARNING] database_reset_initiated user_id=test_user
2023-01-01 12:00:01 [INFO] local_database_deleted db_path=/tmp/metadata_test_user.db
2023-01-01 12:00:02 [INFO] database_downloaded_from_gcs file_size=1024
2023-01-01 12:00:03 [INFO] database_reset_completed duration_seconds=3.2
```

## エラーハンドリング

### 一般的なエラーと対処法

#### 1. 環境エラー
```
DatabaseAdminError: Database admin operations are only available in development/test environments
```
**対処法**: `ENVIRONMENT=development` または `ENVIRONMENT=test` を設定

#### 2. 確認エラー
```
MetadataError: Database reset requires explicit confirmation
```
**対処法**: `confirm_reset=True` を指定

#### 3. ファイル削除エラー
```
MetadataError: Failed to delete local database: Permission denied
```
**対処法**: ファイルの権限を確認、プロセスが使用中でないか確認

#### 4. GCSダウンロードエラー
```
MetadataError: Database reset failed: Download failed
```
**対処法**: GCS接続を確認、新しいデータベースが作成される

## 使用例

### 開発中のデータベースリセット

```python
#!/usr/bin/env python3
"""開発用データベースリセットスクリプト"""

import os
from imgstream.api.database_admin import reset_user_database, DatabaseAdminError

def reset_dev_database(user_id: str):
    """開発用データベースをリセット"""
    if os.getenv('ENVIRONMENT') != 'development':
        print("❌ 開発環境でのみ実行してください")
        return
    
    try:
        print(f"🔄 {user_id} のデータベースをリセット中...")
        result = reset_user_database(user_id, confirm_reset=True)
        
        print("✅ リセット完了!")
        print(f"   処理時間: {result['reset_duration_seconds']:.2f}秒")
        print(f"   GCSから復元: {'Yes' if result['download_successful'] else 'No'}")
        
    except DatabaseAdminError as e:
        print(f"❌ リセット失敗: {e}")

if __name__ == "__main__":
    reset_dev_database("development_user")
```

### テスト前のデータベース準備

```python
import pytest
from imgstream.api.database_admin import reset_user_database

@pytest.fixture
def clean_database():
    """テスト用のクリーンなデータベース"""
    user_id = "test_user"
    
    # テスト前にデータベースをリセット
    reset_user_database(user_id, confirm_reset=True)
    
    yield user_id
    
    # テスト後のクリーンアップは必要に応じて
```

### 整合性チェックスクリプト

```python
#!/usr/bin/env python3
"""データベース整合性チェックスクリプト"""

from imgstream.services.metadata import get_metadata_service

def check_database_integrity(user_id: str):
    """データベース整合性をチェック"""
    metadata_service = get_metadata_service(user_id)
    
    print(f"🔍 {user_id} のデータベース整合性をチェック中...")
    
    validation = metadata_service.validate_database_integrity()
    
    if validation['valid']:
        print("✅ データベースは正常です")
        print(f"   検証時間: {validation['validation_duration_seconds']:.2f}秒")
    else:
        print("❌ 整合性の問題が見つかりました:")
        for issue in validation['issues']:
            print(f"   - {issue}")
        
        # 必要に応じてリセットを提案
        print("\n💡 問題を修正するには、データベースリセットを検討してください:")
        print(f"   reset_user_database('{user_id}', confirm_reset=True)")

if __name__ == "__main__":
    check_database_integrity("development_user")
```

## 注意事項

1. **データ損失**: リセット操作はローカルデータを完全に削除します
2. **環境制限**: 本番環境では絶対に実行されません
3. **GCS依存**: GCSにバックアップがない場合、空のデータベースが作成されます
4. **同期停止**: リセット中は他の同期処理を停止してください
5. **権限確認**: ファイル操作権限とGCSアクセス権限が必要です

## トラブルシューティング

### よくある問題

1. **権限エラー**: ファイルの読み書き権限を確認
2. **ネットワークエラー**: GCS接続を確認
3. **環境設定**: ENVIRONMENT変数を確認
4. **プロセス競合**: 他のプロセスがデータベースを使用していないか確認

### ログ確認

詳細なログは以下で確認できます：

```python
import logging
logging.basicConfig(level=logging.INFO)

# または構造化ログを使用
import structlog
logger = structlog.get_logger()
```

### サポート

問題が解決しない場合は、以下の情報と共にサポートに連絡してください：

- 実行環境（ENVIRONMENT変数）
- エラーメッセージ
- 操作ログ
- データベース状態情報
