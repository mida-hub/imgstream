# 統合テスト

> **⚠️ 注意: このディレクトリのテストは現在無効化されています**
>
> 開発初期段階のため、統合テストは `pyproject.toml` の pytest 設定で除外されています。
> 基本機能の実装が完了し、各コンポーネント間の連携が安定した後に有効化する予定です。
>
> 有効化するには: `pyproject.toml` の `addopts` から `--ignore=tests/integration` を削除してください。

このディレクトリには、imgstreamアプリケーションの包括的な統合テストが含まれています。

## テストの種類

### 1. 衝突検出フロー統合テスト (`test_collision_flow_integration.py`)

**完全な衝突検出フロー**:
- ファイルアップロード時の衝突検出
- ユーザー決定処理（上書き/スキップ）
- メタデータサービスとストレージサービスの連携
- キャッシュ機能の統合動作

**エラー回復フロー**:
- 衝突検出エラー時の回復処理
- フォールバック機能の動作確認
- 部分的失敗時の処理

### 2. 完全システム統合テスト (`test_complete_system_integration.py`)

**エンドツーエンドのシステム統合**:
- 認証 → アップロード → 表示の完全フロー
- 複数ユーザーでの同時操作
- データベース、ストレージ、キャッシュの連携
- ログ記録とモニタリングの統合

**システム境界テスト**:
- 外部サービス（Google Cloud Storage）との連携
- データベース接続の管理
- セッション管理の統合

### 3. エラー回復統合テスト (`test_error_recovery_integration.py`)

**障害シナリオでの統合動作**:
- データベース接続エラー時の回復
- ストレージサービスエラー時の処理
- 部分的なサービス障害での動作継続
- トランザクション整合性の確保

**回復メカニズム**:
- 自動リトライ機能
- フォールバック処理
- エラー状態からの復旧
- データ整合性の維持

### 4. パフォーマンス統合テスト (`test_performance_integration.py`)

**システム全体のパフォーマンス**:
- 複数コンポーネント連携時の性能
- 大量データ処理時の統合動作
- メモリ使用量の統合監視
- レスポンス時間の統合測定

**負荷時の統合動作**:
- 高負荷時のコンポーネント間連携
- リソース競合時の動作
- スケーラビリティの検証

## テストの実行方法

### 前提条件

統合テストを実行するには、以下の環境が必要です：

1. **データベース環境**:
   ```bash
   # テスト用データベースの準備
   export TEST_DATABASE_URL="sqlite:///integration_test.db"

   # データベースの初期化
   python -c "from src.imgstream.models.database import create_database; create_database('integration_test.db')"
   ```

2. **ストレージ環境**:
   ```bash
   # テスト用ストレージバケットの設定
   export TEST_STORAGE_BUCKET="integration-test-bucket"
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/test-service-account.json"
   ```

3. **環境設定**:
   ```bash
   # 統合テスト用環境変数
   export ENVIRONMENT="integration_test"
   export LOG_LEVEL="DEBUG"
   ```

### テストの実行

```bash
# 全統合テストの実行
ENVIRONMENT=integration_test uv run pytest tests/integration/ -v -m integration

# 衝突検出フロー統合テストのみ実行
ENVIRONMENT=integration_test uv run pytest tests/integration/test_collision_flow_integration.py -v

# 完全システム統合テストのみ実行
ENVIRONMENT=integration_test uv run pytest tests/integration/test_complete_system_integration.py -v

# エラー回復統合テストのみ実行
ENVIRONMENT=integration_test uv run pytest tests/integration/test_error_recovery_integration.py -v

# パフォーマンス統合テストのみ実行
ENVIRONMENT=integration_test uv run pytest tests/integration/test_performance_integration.py -v
```

### 並行実行

```bash
# 複数プロセスでの並行実行
ENVIRONMENT=integration_test uv run pytest tests/integration/ -v -n 4 -m integration

# 特定のテストクラスのみ並行実行
ENVIRONMENT=integration_test uv run pytest tests/integration/test_complete_system_integration.py -v -n 2
```

## テスト環境の設定

### 1. ローカル統合テスト環境

```bash
# 環境変数の設定
export ENVIRONMENT="integration_test"
export TEST_DATABASE_URL="sqlite:///integration_test.db"
export TEST_STORAGE_BUCKET="local-integration-test"

# テストデータの準備
python tests/integration/setup_test_data.py
```

### 2. CI/CD統合テスト環境

```yaml
# GitHub Actions での設定例
- name: Setup Integration Test Environment
  run: |
    export ENVIRONMENT="integration_test"
    export TEST_DATABASE_URL="sqlite:///integration_test.db"

- name: Setup Test Database
  run: |
    python -c "from src.imgstream.models.database import create_database; create_database('integration_test.db')"

- name: Setup Test Storage
  run: |
    # Google Cloud Storage エミュレーターの起動
    gcloud beta emulators storage start --port=9023 &
    export STORAGE_EMULATOR_HOST=localhost:9023

- name: Run Integration Tests
  run: |
    uv run pytest tests/integration/ -v -m integration
```

## テストデータとフィクスチャ

### データベースフィクスチャ

```python
# 統合テスト用のデータベース設定
@pytest.fixture(scope="session")
def integration_database():
    """統合テスト用データベースの設定"""
    db_path = "integration_test.db"
    create_database(db_path)
    yield db_path
    os.remove(db_path)
```

### ストレージフィクスチャ

```python
# 統合テスト用のストレージ設定
@pytest.fixture(scope="session")
def integration_storage():
    """統合テスト用ストレージの設定"""
    bucket_name = "integration-test-bucket"
    # テスト用バケットの作成
    yield bucket_name
    # テスト後のクリーンアップ
```

### テストユーザーフィクスチャ

```python
# 統合テスト用のユーザー設定
@pytest.fixture
def integration_users():
    """統合テスト用ユーザーの設定"""
    return [
        UserInfo(user_id="integration-user-1", email="user1@integration.test"),
        UserInfo(user_id="integration-user-2", email="user2@integration.test"),
        UserInfo(user_id="integration-admin", email="admin@integration.test"),
    ]
```

## 期待される結果

### 成功基準

1. **データ整合性**: 100%のデータ整合性維持
2. **トランザクション**: 全てのトランザクションが適切に処理される
3. **エラー回復**: 90%以上のエラー回復成功率
4. **パフォーマンス**: 統合処理が許容時間内に完了

### 品質指標

- **コードカバレッジ**: 統合パスで80%以上
- **エラー率**: 1%未満
- **レスポンス時間**: 平均3秒以内
- **メモリ使用量**: 500MB以内

## モニタリングとログ

### 統合テスト中のモニタリング

```python
# パフォーマンス監視
@pytest.fixture(autouse=True)
def monitor_integration_performance():
    """統合テストのパフォーマンス監視"""
    start_time = time.time()
    start_memory = psutil.Process().memory_info().rss

    yield

    end_time = time.time()
    end_memory = psutil.Process().memory_info().rss

    logger.info("integration_test_metrics",
                duration=end_time - start_time,
                memory_delta=end_memory - start_memory)
```

### ログ収集

- **アプリケーションログ**: 全コンポーネントのログ収集
- **データベースログ**: クエリ実行ログ
- **ストレージログ**: ファイル操作ログ
- **パフォーマンスログ**: 処理時間とリソース使用量

## トラブルシューティング

### よくある問題

1. **データベース接続エラー**
   - 接続文字列の確認
   - データベースファイルの権限確認
   - 同時接続数の制限確認

2. **ストレージ接続エラー**
   - サービスアカウントキーの確認
   - バケット権限の確認
   - ネットワーク接続の確認

3. **メモリ不足エラー**
   - テストデータサイズの調整
   - 並行実行数の削減
   - メモリリークの確認

### デバッグ方法

```bash
# 詳細ログ付きでテスト実行
ENVIRONMENT=integration_test uv run pytest tests/integration/ -v -s --log-cli-level=DEBUG

# 特定のテストのみデバッグ実行
ENVIRONMENT=integration_test uv run pytest tests/integration/test_complete_system_integration.py::TestCompleteSystemIntegration::test_full_upload_flow -v -s

# プロファイリング付きでテスト実行
ENVIRONMENT=integration_test uv run pytest tests/integration/ -v --profile
```

## 継続的改善

### メトリクス収集

- **実行時間の傾向**: 統合テストの実行時間監視
- **成功率の追跡**: テスト成功率の継続的監視
- **リソース使用量**: CPU、メモリ、ディスクI/Oの監視
- **エラーパターン**: 頻発するエラーの分析

### テストの拡張

- **新機能の統合テスト**: 機能追加時の統合テスト追加
- **エッジケースの追加**: 境界条件での統合テスト
- **負荷テストの統合**: 高負荷時の統合動作テスト
- **セキュリティ統合テスト**: セキュリティ機能の統合テスト

統合テストにより、システム全体の品質と安定性を確保し、コンポーネント間の連携を検証できます。
