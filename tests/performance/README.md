# パフォーマンステスト

> **⚠️ 注意: このディレクトリのテストは現在無効化されています**
>
> 開発初期段階のため、パフォーマンステストは `pyproject.toml` の pytest 設定で除外されています。
> 将来的にパフォーマンス最適化が必要になった際に有効化する予定です。
>
> 有効化するには: `pyproject.toml` の `addopts` から `--ignore=tests/performance` を削除してください。

このディレクトリには、imgstreamアプリケーションの包括的なパフォーマンステストが含まれています。

## テストの種類

### 1. 画像処理パフォーマンステスト (`test_image_processing_performance.py`)

- **メタデータ抽出パフォーマンス**: EXIF情報の抽出速度を測定
- **サムネイル生成パフォーマンス**: サムネイル生成の処理時間を測定
- **大容量画像処理パフォーマンス**: 大きな画像ファイルの処理性能を測定
- **複数サムネイル生成パフォーマンス**: 連続処理の効率性を測定
- **メモリ使用量テスト**: 画像処理中のメモリ使用量を監視
- **並行処理パフォーマンス**: 複数スレッドでの同時処理性能を測定

### 2. 負荷・ストレステスト (`test_load_performance.py`)

- **大容量ファイルアップロードテスト**: 大きなファイルのアップロード性能
- **複数ファイルアップロードテスト**: 連続アップロードの処理時間
- **並行アップロードテスト**: 同時アップロードの処理能力
- **メモリ使用量テスト**: 大量処理時のメモリ使用量監視
- **レスポンス時間テスト**: 負荷下でのレスポンス時間測定
- **データベースパフォーマンステスト**: 大量データでのDB性能
- **ストレステスト**: 複数ユーザーの同時利用シミュレーション

## テストの実行方法

### 個別テストの実行

```bash
# 画像処理パフォーマンステストのみ実行
ENVIRONMENT=production uv run pytest tests/performance/test_image_processing_performance.py -v

# 負荷テストのみ実行（ストレステストを除く）
ENVIRONMENT=production uv run pytest tests/performance/test_load_performance.py -v -k "not stress_test"

# 特定のテストのみ実行
ENVIRONMENT=production uv run pytest tests/performance/test_load_performance.py::TestLoadPerformance::test_large_file_upload_performance -v

# パフォーマンステストマークが付いたテストのみ実行
ENVIRONMENT=production uv run pytest -m performance -v

# 遅いテストを除外して実行
ENVIRONMENT=production uv run pytest tests/performance/ -v -m "not slow"
```

### 包括的パフォーマンステストの実行

```bash
# 全てのパフォーマンステストを実行
python tests/performance/run_performance_tests.py --output-dir ./performance_results

# 画像処理テストのみ実行
python tests/performance/run_performance_tests.py --skip-load-tests --output-dir ./performance_results

# 負荷テストのみ実行
python tests/performance/run_performance_tests.py --skip-image-tests --output-dir ./performance_results

# 詳細出力付きで実行
python tests/performance/run_performance_tests.py --verbose --output-dir ./performance_results
```

## パフォーマンス監視

### PerformanceMonitor クラス

`performance_monitor.py`には、テスト実行中のシステムリソースを監視するためのユーティリティが含まれています：

- **メモリ使用量**: RSS、メモリ使用率の監視
- **CPU使用率**: プロセスのCPU使用率監視
- **ディスクI/O**: 読み書きバイト数の測定
- **ネットワークI/O**: 送受信バイト数の測定

### LoadTestRunner クラス

負荷テストを実行し、パフォーマンス指標を自動収集するためのヘルパークラスです。

## パフォーマンス基準

### 画像処理

- **メタデータ抽出**: 1ファイルあたり < 0.1秒
- **サムネイル生成**: 1ファイルあたり < 1秒
- **大容量画像処理**: 4000x3000ピクセル画像で < 3秒

### アップロード処理

- **大容量ファイル**: 10MB画像で < 5秒
- **複数ファイル**: 20ファイルの連続アップロードで < 60秒
- **並行アップロード**: 10ファイルの同時アップロードで < 30秒

### メモリ使用量

- **通常処理**: < 200MB
- **大量処理**: < 500MB
- **メモリリーク**: 50MB以上の増加で警告

### レスポンス時間

- **アップロード**: 平均 < 2秒、最大 < 5秒
- **メタデータクエリ**: 平均 < 0.5秒、最大 < 1秒
- **サムネイル生成**: 平均 < 1秒、最大 < 3秒

## レポート出力

パフォーマンステストの実行後、以下のファイルが生成されます：

- `performance_report.txt`: 包括的なパフォーマンスレポート
- `load_test_report.txt`: 詳細な負荷テストレポート
- `metrics_*.csv`: 詳細なメトリクスデータ（オプション）

## トラブルシューティング

### よくある問題

1. **メモリ不足エラー**
   - 大容量画像テストでメモリが不足する場合は、テスト画像のサイズを調整してください
   - `create_large_image()`の引数を小さくすることで対応可能

2. **テストタイムアウト**
   - 遅いマシンでは、パフォーマンス基準を調整する必要がある場合があります
   - `test_load_performance.py`内のアサーション値を環境に合わせて調整

3. **並行処理エラー**
   - 並行テストでエラーが発生する場合は、ワーカー数を減らしてください
   - `ThreadPoolExecutor(max_workers=N)`のNを調整

### デバッグ

```bash
# 詳細ログ付きでテスト実行
ENVIRONMENT=production uv run pytest tests/performance/ -v -s --log-cli-level=DEBUG

# 特定のテストのみデバッグ実行
ENVIRONMENT=production uv run pytest tests/performance/test_load_performance.py::TestLoadPerformance::test_large_file_upload_performance -v -s
```

## CI/CD統合

GitHub Actionsでパフォーマンステストを実行する場合：

```yaml
- name: Run Performance Tests
  run: |
    python tests/performance/run_performance_tests.py --output-dir ./performance_results

- name: Upload Performance Results
  uses: actions/upload-artifact@v3
  with:
    name: performance-results
    path: ./performance_results/
```

## 継続的パフォーマンス監視

定期的にパフォーマンステストを実行し、以下の指標を監視することを推奨します：

- 処理時間の傾向
- メモリ使用量の変化
- エラー率の推移
- スループットの変化

これにより、パフォーマンスの劣化を早期に検出し、適切な対策を講じることができます。
