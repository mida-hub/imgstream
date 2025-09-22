# ImgStream API 仕様書

## 概要

ImgStream は写真アップロードとメタデータ管理のためのWebアプリケーションです。この文書では、ファイル名衝突回避機能を含む主要なAPIエンドポイントとサービスについて説明します。

## 認証

すべてのAPIエンドポイントは認証が必要です。認証は `AuthService` を通じて処理されます。

## 主要サービス

### MetadataService

写真メタデータの管理とファイル名衝突検出を担当します。

#### メソッド

##### `check_filename_exists(filename: str) -> Optional[Dict[str, Any]]`

指定されたファイル名の衝突をチェックします。

**パラメータ:**
- `filename` (str): チェックするファイル名

**戻り値:**
- 衝突が検出された場合: 既存写真情報を含む辞書
- 衝突がない場合: `None`

**戻り値の構造:**
```python
{
    "existing_photo": PhotoMetadata,
    "existing_file_info": {
        "photo_id": str,
        "file_size": int,
        "upload_date": datetime,
        "creation_date": datetime
    },
    "collision_detected": True
}
```

##### `check_multiple_filename_exists(filenames: List[str]) -> Dict[str, Dict[str, Any]]`

複数のファイル名の衝突を一括でチェックします（最適化版）。

**パラメータ:**
- `filenames` (List[str]): チェックするファイル名のリスト

**戻り値:**
- ファイル名をキーとし、衝突情報を値とする辞書

##### `save_or_update_photo_metadata(photo_metadata: PhotoMetadata, is_overwrite: bool = False) -> Dict[str, Any]`

写真メタデータを保存または更新します。

**パラメータ:**
- `photo_metadata` (PhotoMetadata): 保存する写真メタデータ
- `is_overwrite` (bool): 上書きモードかどうか

**戻り値:**
```python
{
    "success": bool,
    "operation": str,  # "save" or "overwrite"
    "photo_id": str,
    "fallback_used": bool
}
```

##### `force_reload_from_gcs(confirm_reset: bool = False) -> Dict[str, Any]`

ローカルデータベースをリセットし、GCSから再読み込みします（開発環境のみ）。

**パラメータ:**
- `confirm_reset` (bool): リセット確認フラグ

**戻り値:**
```python
{
    "success": bool,
    "operation": str,
    "user_id": str,
    "local_db_deleted": bool,
    "gcs_database_exists": bool,
    "download_successful": bool,
    "reset_duration_seconds": float,
    "message": str,
    "data_loss_risk": bool
}
```

### StorageService

GCSへのファイルアップロードを担当します。

#### メソッド

##### `upload_original_photo(file_data: bytes, filename: str, user_id: str) -> Dict[str, str]`

オリジナル写真をGCSにアップロードします。

##### `upload_thumbnail(thumbnail_data: bytes, filename: str, user_id: str) -> Dict[str, str]`

サムネイル画像をGCSにアップロードします。

### ImageProcessor

画像処理とメタデータ抽出を担当します。

#### メソッド

##### `is_supported_format(filename: str) -> bool`

サポートされている画像形式かどうかをチェックします。

##### `validate_file_size(file_data: bytes) -> Optional[str]`

ファイルサイズを検証します。

##### `extract_creation_date(file_data: bytes) -> Optional[datetime]`

画像から作成日時を抽出します。

##### `generate_thumbnail(file_data: bytes) -> bytes`

サムネイル画像を生成します。

## ユーティリティ関数

### collision_detection.py

#### `check_filename_collisions(user_id: str, filenames: List[str], use_cache: bool = True) -> Dict[str, Dict[str, Any]]`

ファイル名衝突を検出します。

**パラメータ:**
- `user_id` (str): ユーザーID
- `filenames` (List[str]): チェックするファイル名のリスト
- `use_cache` (bool): キャッシュを使用するかどうか

**戻り値:**
- 衝突が検出されたファイル名をキーとする辞書

#### `check_filename_collisions_with_fallback(user_id: str, filenames: List[str], enable_fallback: bool = True) -> Tuple[Dict[str, Dict[str, Any]], bool]`

フォールバック機能付きの衝突検出。

**戻り値:**
- タプル: (衝突結果, フォールバック使用フラグ)

#### `check_filename_collisions_optimized(user_id: str, filenames: List[str], batch_size: int = 100) -> Dict[str, Dict[str, Any]]`

最適化されたバッチ衝突検出。

#### `get_collision_cache_stats() -> Dict[str, int]`

衝突検出キャッシュの統計情報を取得します。

#### `clear_collision_cache() -> None`

衝突検出キャッシュをクリアします。

## UI ハンドラー

### upload_handlers.py

#### `validate_uploaded_files_with_collision_check(uploaded_files: List[Any]) -> Tuple[List[Any], List[str], Dict[str, Dict[str, Any]]]`

アップロードファイルの検証と衝突チェックを実行します。

**戻り値:**
- タプル: (有効ファイル, 検証エラー, 衝突結果)

#### `process_batch_upload(valid_files: List[Any], collision_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]`

バッチアップロードを処理します。

**戻り値:**
```python
{
    "success": bool,
    "total_files": int,
    "successful_uploads": int,
    "failed_uploads": int,
    "skipped_uploads": int,
    "overwrite_uploads": int,
    "results": List[Dict[str, Any]]
}
```

#### `handle_collision_decision_monitoring(user_id: str, filename: str, decision: str, existing_photo_id: str) -> None`

ユーザーの衝突解決決定を監視・記録します。

#### `monitor_batch_collision_processing(user_id: str, filenames: List[str], collision_count: int, processing_time_ms: float) -> None`

バッチ衝突処理の監視を行います。

## 監視とメトリクス

### collision_monitor.py

#### `get_collision_monitor() -> CollisionMonitor`

衝突監視インスタンスを取得します。

#### `log_collision_detected(user_id: str, filename: str, existing_photo_id: str, detection_time_ms: float) -> None`

衝突検出イベントをログに記録します。

#### `log_user_decision(user_id: str, filename: str, decision: str, decision_time_ms: float, existing_photo_id: str = None) -> None`

ユーザー決定イベントをログに記録します。

#### `log_collision_resolved(user_id: str, filename: str, resolution: str, resolution_time_ms: float) -> None`

衝突解決イベントをログに記録します。

#### `log_overwrite_operation(user_id: str, filename: str, original_photo_id: str, operation_result: str, operation_time_ms: float) -> None`

上書き操作イベントをログに記録します。

#### `log_batch_collision_detection(user_id: str, filenames: List[str], collision_count: int, processing_time_ms: float) -> None`

バッチ衝突検出イベントをログに記録します。

### CollisionMonitor クラス

#### `get_collision_statistics(user_id: str) -> Dict[str, Any]`

ユーザーの衝突統計情報を取得します。

**戻り値:**
```python
{
    "collision_metrics": {
        "total_detected": int,
        "total_resolved": int,
        "average_detection_time_ms": float,
        "average_resolution_time_ms": float
    },
    "user_decision_metrics": {
        "total_decisions": int,
        "overwrite_count": int,
        "skip_count": int,
        "overwrite_rate": float,
        "average_decision_time_ms": float
    },
    "overwrite_metrics": {
        "total_operations": int,
        "successful_operations": int,
        "failed_operations": int,
        "success_rate": float,
        "average_operation_time_ms": float
    },
    "batch_processing_metrics": {
        "total_batches": int,
        "total_files_processed": int,
        "total_collisions_found": int,
        "collision_rate": float,
        "average_batch_processing_time_ms": float
    }
}
```

#### `clear_old_events(max_age: timedelta) -> int`

古いイベントをクリアします。

## データベース管理API

### database_admin.py

開発環境でのみ利用可能な管理機能です。

#### `get_database_status(user_id: str) -> Dict[str, Any]`

データベースの状態を取得します。

#### `reset_user_database(user_id: str, confirm_reset: bool = False) -> Dict[str, Any]`

ユーザーデータベースをリセットします。

#### `is_development_environment() -> bool`

開発環境かどうかを判定します。

## エラーハンドリング

### DatabaseAdminError

データベース管理操作のエラーを表します。

### CollisionDetectionError

衝突検出処理のエラーを表します。

## パフォーマンス考慮事項

1. **キャッシュ**: 衝突検出結果はメモリキャッシュされます
2. **バッチ処理**: 大量ファイルの処理には最適化されたバッチ関数を使用
3. **非同期処理**: 監視イベントは非同期で記録されます
4. **リソース管理**: 定期的なキャッシュクリアとイベント削除が推奨されます

## セキュリティ

1. **環境制限**: データベース管理機能は開発環境でのみ利用可能
2. **認証**: すべての操作で適切な認証が必要
3. **入力検証**: ファイル名とユーザー入力は適切に検証されます

## バージョン情報

- API バージョン: 1.0
- 最終更新: 2025年1月
- 衝突回避機能追加: バージョン 1.0
