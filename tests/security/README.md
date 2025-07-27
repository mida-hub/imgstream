# セキュリティテスト

このディレクトリには、imgstreamアプリケーションの包括的なセキュリティテストが含まれています。

## テストの種類

### 1. 認証セキュリティテスト (`test_authentication_security.py`)

**認証バイパステスト**:
- 空のヘッダーでの認証試行
- 不正な形式のJWTトークン
- 無効なペイロードを持つトークン
- 期限切れトークン
- 未来の発行時刻を持つトークン
- 間違った発行者からのトークン

**インジェクション攻撃テスト**:
- SQLインジェクション試行
- XSS攻撃試行
- ヘッダーインジェクション攻撃

**セッションセキュリティテスト**:
- セッション固定攻撃の防止
- 並行認証の安全性
- タイミング攻撃への耐性
- レート制限のシミュレーション

**Unicode・エンコーディングテスト**:
- Unicode正規化攻撃
- 文字エンコーディング攻撃

### 2. データアクセスセキュリティテスト (`test_data_access_security.py`)

**ユーザー間データアクセス防止**:
- クロスユーザーの写真アクセス防止
- メタデータサービスのユーザー分離
- 並行操作でのユーザー分離

**パストラバーサル攻撃防止**:
- ストレージパスでのパストラバーサル
- データベースパスインジェクション
- 不正ファイルアクセス試行

**メタデータインジェクション防止**:
- ファイル名でのスクリプトインジェクション
- MIMEタイプ操作
- メタデータフィールドでのインジェクション

**権限昇格防止**:
- 一般ユーザーから管理者への権限昇格試行
- ユーザーIDの操作による権限昇格

**リソース枯渇攻撃防止**:
- 巨大ファイル名による攻撃
- 過度なメタデータによる攻撃

### 3. 署名付きURLセキュリティテスト (`test_signed_url_security.py`)

**URL有効性テスト**:
- 署名付きURLの有効期限検証
- URL改ざん検出
- クロスユーザーURL アクセス防止

**パラメータインジェクション防止**:
- URLパラメータインジェクション
- クエリパラメータ操作
- エンコーディング攻撃

**リプレイ攻撃防止**:
- ナンス（nonce）を使用したリプレイ攻撃防止
- タイムスタンプベースの検証

**ドメイン検証**:
- ドメインスプーフィング検出
- プロトコル検証（HTTPS強制）
- サブドメイン検証

**レート制限・コンテンツ検証**:
- 署名付きURL生成のレート制限
- コンテンツタイプ検証
- ファイルサイズ制限

## テストの実行方法

### 個別テストの実行

```bash
# 認証セキュリティテストのみ実行
ENVIRONMENT=production uv run pytest tests/security/test_authentication_security.py -v -m security

# データアクセスセキュリティテストのみ実行
ENVIRONMENT=production uv run pytest tests/security/test_data_access_security.py -v -m security

# 署名付きURLセキュリティテストのみ実行
ENVIRONMENT=production uv run pytest tests/security/test_signed_url_security.py -v -m security

# 全セキュリティテストの実行
ENVIRONMENT=production uv run pytest tests/security/ -v -m security

# 特定のテストのみ実行
ENVIRONMENT=production uv run pytest tests/security/test_authentication_security.py::TestAuthenticationSecurity::test_authentication_bypass_empty_headers -v
```

### 包括的セキュリティテストの実行

```bash
# 全てのセキュリティテストを実行
python tests/security/run_security_tests.py --output-dir ./security_results

# 認証テストをスキップして実行
python tests/security/run_security_tests.py --skip-auth-tests --output-dir ./security_results

# データアクセステストをスキップして実行
python tests/security/run_security_tests.py --skip-data-tests --output-dir ./security_results

# 署名付きURLテストをスキップして実行
python tests/security/run_security_tests.py --skip-url-tests --output-dir ./security_results

# 詳細出力付きで実行
python tests/security/run_security_tests.py --verbose --output-dir ./security_results
```

## セキュリティ基準

### 認証セキュリティ

- **JWTトークン検証**: 不正な形式・期限切れ・改ざんされたトークンの拒否
- **インジェクション防止**: SQL、XSS、ヘッダーインジェクション攻撃の防止
- **セッション管理**: セッション固定攻撃の防止、安全なセッション管理
- **レート制限**: 認証試行の制限、ブルートフォース攻撃の防止

### データアクセス制御

- **ユーザー分離**: 完全なユーザー間データ分離
- **パストラバーサル防止**: ディレクトリトラバーサル攻撃の防止
- **権限制御**: 適切な権限チェック、権限昇格の防止
- **入力検証**: 全ての入力データの適切な検証とサニタイゼーション

### 署名付きURL

- **有効期限管理**: 適切な有効期限設定と検証
- **改ざん検出**: URL改ざんの検出と拒否
- **アクセス制御**: ユーザー固有のアクセス制御
- **リプレイ攻撃防止**: ナンスやタイムスタンプによる防止

## セキュリティレポート

セキュリティテストの実行後、以下のファイルが生成されます：

- `security_report.txt`: 包括的なセキュリティレポート
- `authentication_security_results.txt`: 認証セキュリティテストの詳細結果
- `data_access_security_results.txt`: データアクセスセキュリティテストの詳細結果
- `signed_url_security_results.txt`: 署名付きURLセキュリティテストの詳細結果

### レポートの内容

1. **エグゼクティブサマリー**
   - 実行されたテスト数
   - 成功/失敗の統計
   - 全体的なセキュリティ状況

2. **脆弱性の詳細**
   - 検出された脆弱性の分類
   - 重要度レベル
   - 具体的な問題の説明

3. **詳細テスト結果**
   - 各テストカテゴリの結果
   - エラーの詳細
   - 実行ログ

4. **セキュリティ推奨事項**
   - 検出された問題の修正方法
   - 追加のセキュリティ対策
   - ベストプラクティスの提案

## トラブルシューティング

### よくある問題

1. **認証テストの失敗**
   - JWTライブラリの設定を確認
   - モックの設定が正しいか確認
   - 時刻同期の問題がないか確認

2. **データアクセステストの失敗**
   - ファイルパスの権限設定を確認
   - データベースの分離設定を確認
   - ユーザーIDの検証ロジックを確認

3. **署名付きURLテストの失敗**
   - URL生成ロジックの実装を確認
   - 有効期限の計算が正しいか確認
   - ドメイン検証の設定を確認

### デバッグ方法

```bash
# 詳細ログ付きでテスト実行
ENVIRONMENT=production uv run pytest tests/security/ -v -s --log-cli-level=DEBUG

# 特定のテストのみデバッグ実行
ENVIRONMENT=production uv run pytest tests/security/test_authentication_security.py::TestAuthenticationSecurity::test_authentication_bypass_empty_headers -v -s

# セキュリティテストスクリプトのデバッグ実行
python tests/security/run_security_tests.py --verbose --output-dir ./debug_results
```

## CI/CD統合

GitHub Actionsでセキュリティテストを実行する場合：

```yaml
- name: Run Security Tests
  run: |
    python tests/security/run_security_tests.py --output-dir ./security_results
    
- name: Upload Security Results
  uses: actions/upload-artifact@v3
  with:
    name: security-results
    path: ./security_results/
    
- name: Check Security Status
  run: |
    if [ -f ./security_results/security_report.txt ]; then
      if grep -q "SECURITY ISSUES DETECTED" ./security_results/security_report.txt; then
        echo "Security vulnerabilities detected!"
        exit 1
      fi
    fi
```

## セキュリティベストプラクティス

### 継続的セキュリティ監視

1. **定期実行**: セキュリティテストを定期的に実行
2. **自動化**: CI/CDパイプラインに組み込み
3. **監視**: セキュリティメトリクスの継続的監視
4. **更新**: 新しい脅威に対応したテストの追加

### セキュリティ文化

1. **教育**: 開発チームのセキュリティ意識向上
2. **レビュー**: セキュリティ観点でのコードレビュー
3. **インシデント対応**: セキュリティインシデントへの迅速な対応
4. **改善**: セキュリティテスト結果に基づく継続的改善

これらのセキュリティテストにより、アプリケーションの堅牢性を確保し、ユーザーデータの安全性を保護できます。
