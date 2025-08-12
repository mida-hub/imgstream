# E2E（エンドツーエンド）テスト

> **⚠️ 注意: このディレクトリのテストは現在無効化されています**
>
> 開発初期段階のため、E2Eテストは `pyproject.toml` の pytest 設定で除外されています。
> 基本機能の実装が完了し、統合テスト環境が整備された後に有効化する予定です。
>
> 有効化するには: `pyproject.toml` の `addopts` から `--ignore=tests/e2e` を削除してください。

このディレクトリには、imgstreamアプリケーションの包括的なE2Eテストが含まれています。

## テストの種類

### 1. 認証フローテスト (`test_authentication_flow.py`)

**完全な認証フロー**:
- ログインからログアウトまでの完全なフロー
- 開発モードと本番モードでの認証
- セッション管理の検証
- 認証エラーハンドリング

**ユーザー体験テスト**:
- 認証UI の表示と操作
- エラーメッセージの表示
- リダイレクト処理の検証

### 2. アップロードフローテスト (`test_upload_flow.py`)

**完全なアップロードフロー**:
- ファイル選択からアップロード完了まで
- 複数ファイルの同時アップロード
- 大容量ファイルのアップロード
- アップロード進捗の表示

**エラーハンドリング**:
- 不正ファイル形式の処理
- ネットワークエラーの処理
- サーバーエラーの処理

### 3. シンプルテスト (`test_simple_auth.py`, `test_simple_upload.py`)

**基本機能テスト**:
- 最小限の認証テスト
- 基本的なアップロード機能テスト
- 主要な画面遷移テスト

### 4. エラーシナリオテスト (`test_error_scenarios.py`)

**エラー処理の包括的テスト**:
- ネットワーク障害シナリオ
- サーバー障害シナリオ
- データベース障害シナリオ
- ストレージ障害シナリオ

## テストの実行方法

### 前提条件

E2Eテストを実行するには、以下の環境が必要です：

1. **テスト環境の構築**:
   ```bash
   # テスト用データベースの準備
   export TEST_DATABASE_URL="sqlite:///test_imgstream.db"

   # テスト用ストレージの準備
   export TEST_STORAGE_BUCKET="test-imgstream-bucket"

   # 開発モードの設定
   export ENVIRONMENT="development"
   ```

2. **依存関係のインストール**:
   ```bash
   # Seleniumドライバーのインストール（必要に応じて）
   pip install selenium webdriver-manager

   # Streamlitテスト用ライブラリ
   pip install streamlit-testing
   ```

### テストの実行

```bash
# 全E2Eテストの実行
ENVIRONMENT=development uv run pytest tests/e2e/ -v -m e2e

# 認証フローテストのみ実行
ENVIRONMENT=development uv run pytest tests/e2e/test_authentication_flow.py -v

# アップロードフローテストのみ実行
ENVIRONMENT=development uv run pytest tests/e2e/test_upload_flow.py -v

# シンプルテストのみ実行
ENVIRONMENT=development uv run pytest tests/e2e/test_simple_auth.py tests/e2e/test_simple_upload.py -v

# エラーシナリオテストのみ実行
ENVIRONMENT=development uv run pytest tests/e2e/test_error_scenarios.py -v
```

### ヘッドレスモードでの実行

```bash
# ヘッドレスモードで実行（CI/CD環境向け）
HEADLESS=true ENVIRONMENT=development uv run pytest tests/e2e/ -v -m e2e

# 特定のブラウザで実行
BROWSER=chrome ENVIRONMENT=development uv run pytest tests/e2e/ -v -m e2e
```

## テスト環境の設定

### 1. ローカル開発環境

```bash
# 環境変数の設定
export ENVIRONMENT="development"
export DEV_USER_EMAIL="test@example.com"
export DEV_USER_ID="test-user-001"

# Streamlitアプリケーションの起動
streamlit run src/imgstream/main.py --server.port 8501
```

### 2. CI/CD環境

```yaml
# GitHub Actions での設定例
- name: Setup E2E Test Environment
  run: |
    export ENVIRONMENT="development"
    export HEADLESS="true"
    export TEST_DATABASE_URL="sqlite:///test_imgstream.db"

- name: Start Application
  run: |
    streamlit run src/imgstream/main.py --server.port 8501 &
    sleep 10  # アプリケーションの起動を待機

- name: Run E2E Tests
  run: |
    uv run pytest tests/e2e/ -v -m e2e
```

## テストデータ

E2Eテストでは以下のテストデータを使用します：

### 画像ファイル

- `test_image_small.jpg` (100KB未満)
- `test_image_medium.jpg` (1-5MB)
- `test_image_large.jpg` (5-10MB)
- `test_image_invalid.txt` (不正ファイル)

### ユーザーデータ

- テストユーザー: `test@example.com`
- 管理者ユーザー: `admin@example.com`
- 無効ユーザー: `invalid@example.com`

## 期待される結果

### 成功基準

1. **認証フロー**: 100%の成功率
2. **アップロードフロー**: 95%以上の成功率
3. **エラーハンドリング**: 適切なエラーメッセージの表示
4. **パフォーマンス**: 各操作が10秒以内に完了

### 失敗時の対応

1. **スクリーンショットの保存**: 失敗時の画面状態を記録
2. **ログの収集**: 詳細なエラーログの保存
3. **環境情報の記録**: ブラウザ、OS、環境変数の記録

## トラブルシューティング

### よくある問題

1. **Streamlitアプリケーションが起動しない**
   - ポートの競合を確認
   - 依存関係のインストール状況を確認
   - 環境変数の設定を確認

2. **ブラウザドライバーのエラー**
   - WebDriverのバージョンを確認
   - ブラウザのバージョンとの互換性を確認
   - ヘッドレスモードでの実行を試行

3. **テストデータの問題**
   - テスト用画像ファイルの存在を確認
   - ファイルサイズと形式を確認
   - アクセス権限を確認

### デバッグ方法

```bash
# 詳細ログ付きでテスト実行
ENVIRONMENT=development uv run pytest tests/e2e/ -v -s --log-cli-level=DEBUG

# 特定のテストのみデバッグ実行
ENVIRONMENT=development uv run pytest tests/e2e/test_authentication_flow.py::TestAuthenticationFlow::test_complete_auth_flow -v -s

# ブラウザを表示してデバッグ
HEADLESS=false ENVIRONMENT=development uv run pytest tests/e2e/test_simple_auth.py -v -s
```

## 継続的改善

### メトリクス収集

- テスト実行時間の監視
- 成功率の追跡
- エラーパターンの分析
- パフォーマンス指標の収集

### テストの拡張

- 新機能に対応したテストケースの追加
- エッジケースのテスト追加
- クロスブラウザテストの実装
- モバイル対応テストの追加

E2Eテストにより、ユーザー体験の品質を確保し、リグレッションを防止できます。
