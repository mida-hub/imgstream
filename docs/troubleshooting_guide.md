# ImgStream トラブルシューティングガイド

## 概要

このガイドでは、ImgStreamアプリケーション、特にファイル名衝突回避機能に関する一般的な問題とその解決方法について説明します。

## 目次

1. [衝突検出関連の問題](#衝突検出関連の問題)
2. [アップロード処理の問題](#アップロード処理の問題)
3. [データベース関連の問題](#データベース関連の問題)
4. [パフォーマンス問題](#パフォーマンス問題)
5. [監視・ログ関連の問題](#監視ログ関連の問題)
6. [環境・設定の問題](#環境設定の問題)
7. [UI・表示の問題](#ui表示の問題)

## 衝突検出関連の問題

### 問題: 衝突検出が動作しない

**症状:**
- ファイル名が重複しているのに衝突警告が表示されない
- 既存ファイルが上書きされてしまう

**原因と解決方法:**

#### 1. キャッシュの問題

```python
# キャッシュの状態を確認
from imgstream.utils.collision_detection import get_collision_cache_stats
stats = get_collision_cache_stats()
print(f"キャッシュエントリ数: {stats['total_entries']}")
print(f"有効エントリ数: {stats['valid_entries']}")
```

**解決方法:**
```python
# キャッシュをクリア
from imgstream.utils.collision_detection import clear_collision_cache
clear_collision_cache()
```

#### 2. データベース接続の問題

**確認方法:**
```python
# MetadataServiceの動作確認
from imgstream.services.metadata import get_metadata_service
service = get_metadata_service()
result = service.check_filename_exists("test.jpg")
print(f"衝突チェック結果: {result}")
```

**解決方法:**
- データベースファイルの存在確認
- 権限の確認
- 開発環境の場合はデータベースリセット

#### 3. 環境変数の設定問題

**確認項目:**
```bash
# 重要な環境変数の確認
echo $ENVIRONMENT
echo $DATABASE_TYPE
echo $LOCAL_DB_PATH
echo $COLLISION_CACHE_TTL_SECONDS
```

### 問題: 衝突検出が遅い

**症状:**
- 大量ファイルのアップロード時に衝突チェックが遅い
- タイムアウトエラーが発生する

**解決方法:**

#### 1. 最適化された関数の使用

```python
# 通常の衝突検出（遅い）
from imgstream.utils.collision_detection import check_filename_collisions
results = check_filename_collisions(user_id, filenames)

# 最適化された衝突検出（速い）
from imgstream.utils.collision_detection import check_filename_collisions_optimized
results = check_filename_collisions_optimized(
    user_id, 
    filenames, 
    batch_size=500  # バッチサイズを調整
)
```

#### 2. キャッシュの有効活用

```python
# キャッシュを有効にして実行
results = check_filename_collisions(user_id, filenames, use_cache=True)
```

#### 3. バッチサイズの調整

```python
# 環境に応じてバッチサイズを調整
# 小さなファイル数: batch_size=50
# 中程度のファイル数: batch_size=100
# 大量のファイル数: batch_size=500
```

### 問題: フォールバック機能が動作しない

**症状:**
- データベースエラー時にフォールバックモードにならない
- エラーが発生してアップロードが停止する

**解決方法:**

```python
# フォールバック機能付きの衝突検出を使用
from imgstream.utils.collision_detection import check_filename_collisions_with_fallback

results, fallback_used = check_filename_collisions_with_fallback(
    user_id, 
    filenames, 
    enable_fallback=True
)

if fallback_used:
    print("フォールバックモードで実行されました")
```

## アップロード処理の問題

### 問題: 上書きアップロードが失敗する

**症状:**
- 上書きを選択したのにファイルが更新されない
- エラーメッセージが表示される

**原因と解決方法:**

#### 1. 権限の問題

**確認方法:**
```bash
# GCSバケットの権限確認
gsutil iam get gs://your-bucket-name

# サービスアカウントの権限確認
gcloud projects get-iam-policy $GOOGLE_CLOUD_PROJECT
```

#### 2. ストレージサービスの問題

**デバッグ方法:**
```python
# ストレージサービスの動作確認
from imgstream.services.storage import get_storage_service
storage = get_storage_service()

# アップロードテスト
result = storage.upload_original_photo(
    file_data=b"test_data",
    filename="test.jpg",
    user_id="test_user"
)
print(f"アップロード結果: {result}")
```

#### 3. メタデータ更新の問題

**確認方法:**
```python
# メタデータ更新の確認
from imgstream.services.metadata import get_metadata_service
service = get_metadata_service()

# 上書きモードでの保存テスト
result = service.save_or_update_photo_metadata(
    photo_metadata=photo_metadata,
    is_overwrite=True
)
print(f"メタデータ更新結果: {result}")
```

### 問題: バッチアップロードで一部ファイルが失敗する

**症状:**
- 複数ファイルのアップロード時に一部だけ失敗する
- エラーメッセージが不明確

**解決方法:**

#### 1. 詳細ログの確認

```python
# 詳細なログ出力を有効にする
import logging
logging.getLogger('imgstream').setLevel(logging.DEBUG)

# バッチアップロード実行
from imgstream.ui.upload_handlers import process_batch_upload
result = process_batch_upload(valid_files, collision_results)

# 結果の詳細確認
for file_result in result['results']:
    if not file_result['success']:
        print(f"失敗ファイル: {file_result['filename']}")
        print(f"エラー: {file_result['error']}")
```

#### 2. ファイル別の個別処理

```python
# 失敗したファイルを個別に処理
failed_files = [r for r in result['results'] if not r['success']]
for failed_file in failed_files:
    # 個別にリトライ処理
    pass
```

## データベース関連の問題

### 問題: データベースファイルが破損している

**症状:**
- データベース読み込みエラー
- 写真メタデータが表示されない

**解決方法:**

#### 1. 開発環境でのデータベースリセット

```bash
# 開発環境の確認
echo $ENVIRONMENT  # "development"であることを確認

# データベースリセット
curl -X POST http://localhost:8501/api/admin/database/reset \
    -H "Content-Type: application/json" \
    -d '{"user_id": "your_user_id", "confirm_reset": true}'
```

#### 2. データベース整合性の確認

```python
# データベース状態の確認
from imgstream.api.database_admin import get_database_status
status = get_database_status("your_user_id")
print(f"データベース状態: {status}")

# 整合性チェック
integrity = status['integrity_validation']
if not integrity['valid']:
    print(f"整合性問題: {integrity['issues']}")
```

#### 3. 手動でのデータベースファイル削除

```bash
# 注意: データが失われます
rm ./data/imgstream.db
# アプリケーション再起動後、新しいデータベースが作成されます
```

### 問題: GCSからのデータベース同期が失敗する

**症状:**
- GCSからのデータベースダウンロードが失敗する
- 同期処理がタイムアウトする

**解決方法:**

#### 1. GCS権限の確認

```bash
# バケットアクセス権限の確認
gsutil ls gs://your-bucket-name/databases/

# サービスアカウント権限の確認
gcloud iam service-accounts get-iam-policy your-service-account@project.iam.gserviceaccount.com
```

#### 2. ネットワーク接続の確認

```bash
# GCSへの接続テスト
gsutil cp gs://your-bucket-name/databases/test.db ./test_download.db
```

## パフォーマンス問題

### 問題: アプリケーションの応答が遅い

**症状:**
- ページ読み込みが遅い
- ファイルアップロードが遅い

**解決方法:**

#### 1. キャッシュ設定の最適化

```bash
# キャッシュ設定の確認
echo $COLLISION_CACHE_TTL_SECONDS
echo $COLLISION_CACHE_MAX_ENTRIES

# 推奨設定
export COLLISION_CACHE_TTL_SECONDS=7200
export COLLISION_CACHE_MAX_ENTRIES=50000
```

#### 2. バッチサイズの調整

```python
# 環境に応じたバッチサイズの設定
import os
batch_size = int(os.getenv('COLLISION_DETECTION_BATCH_SIZE', 100))

# パフォーマンステスト
import time
start_time = time.perf_counter()
results = check_filename_collisions_optimized(user_id, filenames, batch_size)
processing_time = time.perf_counter() - start_time
print(f"処理時間: {processing_time:.2f}秒")
```

#### 3. メモリ使用量の監視

```python
# メモリ使用量の確認
import psutil
process = psutil.Process()
memory_info = process.memory_info()
print(f"メモリ使用量: {memory_info.rss / 1024 / 1024:.2f} MB")

# ガベージコレクション実行
import gc
gc.collect()
```

### 問題: 大量ファイル処理時のメモリ不足

**症状:**
- OutOfMemoryエラー
- アプリケーションがクラッシュする

**解決方法:**

#### 1. バッチ処理の実装

```python
# 大量ファイルを小さなバッチに分割
def process_large_batch(filenames, batch_size=100):
    results = {}
    for i in range(0, len(filenames), batch_size):
        batch = filenames[i:i+batch_size]
        batch_results = check_filename_collisions(user_id, batch)
        results.update(batch_results)
        
        # メモリクリーンアップ
        import gc
        gc.collect()
    
    return results
```

#### 2. ストリーミング処理の使用

```python
# ファイルをストリーミングで処理
def stream_process_files(file_iterator):
    for file_batch in file_iterator:
        yield process_batch_upload(file_batch, {})
```

## 監視・ログ関連の問題

### 問題: 監視データが記録されない

**症状:**
- 衝突イベントがログに記録されない
- 統計情報が更新されない

**解決方法:**

#### 1. 監視機能の有効化確認

```bash
# 監視設定の確認
echo $MONITORING_ENABLED  # "true"であることを確認
```

#### 2. 監視インスタンスの確認

```python
# 監視インスタンスの動作確認
from imgstream.monitoring.collision_monitor import get_collision_monitor
monitor = get_collision_monitor()

# イベント数の確認
print(f"衝突イベント数: {len(monitor.collision_events)}")
print(f"決定イベント数: {len(monitor.user_decision_events)}")
print(f"上書きイベント数: {len(monitor.overwrite_events)}")
```

#### 3. 手動でのイベント記録テスト

```python
# 手動でイベントを記録してテスト
from imgstream.monitoring.collision_monitor import log_collision_detected
log_collision_detected("test_user", "test.jpg", "existing_123", 100.0)

# イベントが記録されたか確認
monitor = get_collision_monitor()
recent_events = [e for e in monitor.collision_events if e.user_id == "test_user"]
print(f"記録されたイベント数: {len(recent_events)}")
```

### 問題: ログファイルが大きくなりすぎる

**症状:**
- ディスク容量不足
- ログファイルの読み込みが遅い

**解決方法:**

#### 1. ログローテーションの設定

```python
# logging.confでローテーション設定
[handler_fileHandler]
class=handlers.RotatingFileHandler
args=('imgstream.log', 'a', 10*1024*1024, 5)  # 10MB, 5ファイル
```

#### 2. 古いイベントの削除

```python
# 古いイベントを定期的に削除
from imgstream.monitoring.collision_monitor import get_collision_monitor
from datetime import timedelta

monitor = get_collision_monitor()
deleted_count = monitor.clear_old_events(timedelta(days=30))
print(f"削除されたイベント数: {deleted_count}")
```

#### 3. ログレベルの調整

```python
# 本番環境ではログレベルを上げる
import logging
if os.getenv('ENVIRONMENT') == 'production':
    logging.getLogger('imgstream').setLevel(logging.WARNING)
```

## 環境・設定の問題

### 問題: 環境変数が正しく読み込まれない

**症状:**
- デフォルト値が使用される
- 設定が反映されない

**解決方法:**

#### 1. 環境変数の確認

```bash
# 重要な環境変数の一覧確認
env | grep -E "(ENVIRONMENT|GOOGLE_|GCS_|DATABASE_|COLLISION_|MONITORING_)"
```

#### 2. .envファイルの確認

```bash
# .envファイルの存在確認
ls -la .env

# .envファイルの内容確認
cat .env
```

#### 3. Streamlit設定の確認

```bash
# Streamlit設定ファイルの確認
ls -la .streamlit/
cat .streamlit/config.toml
cat .streamlit/secrets.toml
```

### 問題: 本番環境で管理機能が使用できない

**症状:**
- データベースリセット機能が使用できない
- 管理APIがエラーを返す

**これは正常な動作です。**

**確認方法:**
```python
# 環境の確認
from imgstream.api.database_admin import is_development_environment
print(f"開発環境: {is_development_environment()}")

# 本番環境では管理機能は無効化されます
if not is_development_environment():
    print("本番環境では管理機能は使用できません")
```

**解決方法:**
- 開発環境またはテスト環境で管理機能を使用
- 本番環境では適切なバックアップ・リストア手順を使用

## UI・表示の問題

### 問題: 衝突警告が表示されない

**症状:**
- ファイル名が重複しているのに警告が表示されない
- UIに衝突情報が表示されない

**解決方法:**

#### 1. セッション状態の確認

```python
# Streamlitセッション状態の確認
import streamlit as st
print("セッション状態のキー:", list(st.session_state.keys()))

# 衝突結果の確認
if 'collision_results' in st.session_state:
    print("衝突結果:", st.session_state.collision_results)
```

#### 2. ファイル検証フローの確認

```python
# ファイル検証の実行確認
from imgstream.ui.upload_handlers import validate_uploaded_files_with_collision_check

valid_files, errors, collisions = validate_uploaded_files_with_collision_check(uploaded_files)
print(f"有効ファイル数: {len(valid_files)}")
print(f"エラー数: {len(errors)}")
print(f"衝突数: {len(collisions)}")
```

### 問題: アップロード結果の表示が正しくない

**症状:**
- 成功・失敗の表示が間違っている
- 上書き結果が正しく表示されない

**解決方法:**

#### 1. 結果データの確認

```python
# アップロード結果の詳細確認
result = process_batch_upload(valid_files, collision_results)
print("バッチアップロード結果:")
print(f"  成功: {result['successful_uploads']}")
print(f"  失敗: {result['failed_uploads']}")
print(f"  スキップ: {result['skipped_uploads']}")
print(f"  上書き: {result['overwrite_uploads']}")

# 個別ファイル結果の確認
for file_result in result['results']:
    print(f"  {file_result['filename']}: {file_result['status']}")
```

## 緊急時の対応

### データベース完全リセット（開発環境のみ）

```bash
# 注意: すべてのデータが失われます
rm -f ./data/imgstream.db
rm -rf ./data/cache/
mkdir -p ./data/cache/

# アプリケーション再起動
```

### キャッシュとセッションの完全クリア

```python
# すべてのキャッシュをクリア
from imgstream.utils.collision_detection import clear_collision_cache
clear_collision_cache()

# 監視データのクリア
from imgstream.monitoring.collision_monitor import get_collision_monitor
from datetime import timedelta
monitor = get_collision_monitor()
monitor.clear_old_events(timedelta(seconds=0))  # すべてのイベントを削除

# Streamlitセッション状態のクリア
import streamlit as st
for key in list(st.session_state.keys()):
    del st.session_state[key]
```

### ログ収集（サポート用）

```bash
# 問題調査用のログ収集
mkdir -p ./debug_logs
cp imgstream.log ./debug_logs/
cp -r .streamlit/ ./debug_logs/
env | grep -E "(ENVIRONMENT|GOOGLE_|GCS_|DATABASE_|COLLISION_|MONITORING_)" > ./debug_logs/env_vars.txt
tar -czf debug_info_$(date +%Y%m%d_%H%M%S).tar.gz ./debug_logs/
```

## サポート連絡先

問題が解決しない場合は、以下の情報を含めてサポートに連絡してください：

1. エラーメッセージの全文
2. 実行環境（開発/テスト/本番）
3. 問題が発生した操作手順
4. 関連するログファイル
5. 環境変数の設定（機密情報は除く）

## 関連ドキュメント

- [API仕様書](./api_specification.md)
- [デプロイメントガイド](./deployment_guide.md)
- [ユーザーガイド](./collision_handling_user_guide.md)
- [データベースリセットガイド](./database_reset_guide.md)
