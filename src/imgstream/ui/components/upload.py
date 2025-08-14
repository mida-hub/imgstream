"""Upload UI components for imgstream application."""

from datetime import datetime
from typing import Any

import streamlit as st


def render_file_validation_results(valid_files: list, validation_errors: list) -> None:
    """
    Render the results of file validation.

    Args:
        valid_files: List of valid files
        validation_errors: List of validation errors
    """
    if valid_files:
        st.success(f"✅ {len(valid_files)}個のファイルが検証に合格しました")

        with st.expander("📋 検証済みファイル", expanded=len(valid_files) <= 5):
            for file_info in valid_files:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📷 **{file_info['filename']}**")
                with col2:
                    file_size_mb = file_info["size"] / (1024 * 1024)
                    st.write(f"💾 {file_size_mb:.1f} MB")

    if validation_errors:
        st.error(f"❌ {len(validation_errors)}個のファイルで検証エラーが発生しました")

        with st.expander("🚨 検証エラー", expanded=True):
            for error_info in validation_errors:
                st.error(f"📷 **{error_info['filename']}** - {error_info['error']}")


def render_file_validation_results_with_collisions(
    valid_files: list, validation_errors: list, collision_results: dict
) -> None:
    """
    Render file validation results including collision information.

    Args:
        valid_files: List of valid files
        validation_errors: List of validation errors
        collision_results: Dictionary of collision detection results
    """
    # First render standard validation results
    render_file_validation_results(valid_files, validation_errors)


def render_collision_error_messages(collision_errors: list) -> None:
    """
    Render enhanced error messages for collision-related errors.

    Args:
        collision_errors: List of collision detection errors
    """
    if not collision_errors:
        return

    st.error(f"🚨 {len(collision_errors)}個のファイルで衝突検出エラーが発生しました")

    with st.expander("🔍 衝突検出エラー詳細", expanded=True):
        for error_info in collision_errors:
            filename = error_info.get("filename", "不明なファイル")
            error_message = error_info.get("error", "不明なエラー")
            error_type = error_info.get("error_type", "一般エラー")

            st.markdown(f"### 📷 {filename}")

            col1, col2 = st.columns([1, 2])
            with col1:
                st.write(f"**エラータイプ:** {error_type}")
                st.write(f"**ファイル:** {filename}")
            with col2:
                st.code(error_message, language="text")

            # Provide specific guidance based on error type
            if "timeout" in error_message.lower():
                st.info("💡 **対処法:** ネットワーク接続を確認し、しばらく待ってから再試行してください。")
            elif "connection" in error_message.lower():
                st.info("💡 **対処法:** データベース接続に問題があります。ページを更新して再試行してください。")
            elif "permission" in error_message.lower():
                st.info("💡 **対処法:** アクセス権限に問題があります。管理者にお問い合わせください。")
            else:
                st.info("💡 **対処法:** 一時的な問題の可能性があります。しばらく待ってから再試行してください。")

            st.divider()


def render_upload_progress(
    progress_placeholder: Any,
    current_file: str,
    current_step: str,
    completed: int,
    total: int,
    stage: str = "processing",
) -> None:
    """
    Render enhanced upload progress information with visual indicators.

    Args:
        progress_placeholder: Streamlit placeholder for progress display
        current_file: Name of file currently being processed
        current_step: Current processing step
        completed: Number of completed files
        total: Total number of files
        stage: Current processing stage (processing, success, error, completed)
    """
    progress_percentage = (completed / total) * 100 if total > 0 else 0

    with progress_placeholder.container():
        # Main progress bar
        st.progress(progress_percentage / 100, text=f"Processing {completed}/{total} files")

        # Current file information with enhanced styling
        if current_file:
            # Color coding based on stage
            stage_colors = {"processing": "🔄", "success": "✅", "error": "❌", "failed": "❌", "completed": "✅"}

            stage_icon = stage_colors.get(stage, "⚙️")

            # File info with better formatting
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"📷 **Current file:** `{current_file}`")
                st.markdown(f"{stage_icon} **Status:** {current_step}")
            with col2:
                # Progress indicator for current file
                if stage == "processing":
                    st.markdown("🔄 **Processing...**")
                elif stage == "success":
                    st.markdown("✅ **Success**")
                elif stage in ["error", "failed"]:
                    st.markdown("❌ **Failed**")
                else:
                    st.markdown("⚙️ **Working...**")

        # Overall progress summary
        if total > 1:
            st.markdown(f"**Overall Progress:** {completed}/{total} files processed")

            # Show completion percentage
            if completed > 0:
                success_rate = f"({progress_percentage:.1f}% complete)"
                st.markdown(f"**Status:** {success_rate}")


def render_detailed_progress_info(
    progress_info_placeholder: Any,
    batch_results: list[dict[str, Any]] | None = None,
    current_processing: dict[str, Any] | None = None,
) -> None:
    """
    Render detailed progress information during batch processing.

    Args:
        progress_info_placeholder: Streamlit placeholder for detailed progress
        batch_results: List of completed processing results
        current_processing: Information about currently processing file
    """
    with progress_info_placeholder.container():
        if batch_results:
            # Show completed files summary
            successful = sum(1 for r in batch_results if r.get("success", False))
            failed = len(batch_results) - successful

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("完了", len(batch_results))
            with col2:
                st.metric("成功", successful, delta=successful if successful > 0 else None)
            with col3:
                st.metric("失敗", failed, delta=-failed if failed > 0 else None)

            # Show recent completions
            if batch_results:
                with st.expander("📋 最近の完了", expanded=False):
                    for result in batch_results[-5:]:  # Show last 5 results
                        status_icon = "✅" if result.get("success", False) else "❌"
                        filename = result.get("filename", "不明")
                        message = result.get("message", "メッセージなし")
                        st.write(f"{status_icon} **{filename}** - {message}")

        if current_processing:
            st.markdown("### 🔄 現在の処理")
            filename = current_processing.get("filename", "不明")
            step = current_processing.get("step", "処理中...")
            st.info(f"**{filename}**: {step}")


def render_upload_statistics(
    stats_placeholder: Any, start_time: datetime, batch_result: dict[str, Any] | None = None
) -> None:
    """
    Render upload statistics and performance metrics.

    Args:
        stats_placeholder: Streamlit placeholder for statistics
        start_time: When the upload process started
        batch_result: Final batch processing results
    """
    with stats_placeholder.container():
        current_time = datetime.now()
        elapsed_time = current_time - start_time

        st.markdown("### 📊 アップロード統計")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Elapsed Time", f"{elapsed_time.total_seconds():.1f}s")

        if batch_result:
            total_files = batch_result.get("total_files", 0)
            successful = batch_result.get("successful_uploads", 0)

            with col2:
                if total_files > 0 and elapsed_time.total_seconds() > 0:
                    rate = total_files / elapsed_time.total_seconds()
                    st.metric("Processing Rate", f"{rate:.1f} files/sec")
                else:
                    st.metric("Processing Rate", "N/A")

            with col3:
                if total_files > 0:
                    success_rate = (successful / total_files) * 100
                    st.metric("Success Rate", f"{success_rate:.1f}%")
                else:
                    st.metric("Success Rate", "N/A")


def render_collision_decision_help() -> None:
    """Render help information for collision decisions."""
    with st.expander("❓ 衝突処理について", expanded=False):
        st.markdown(
            """
        **ファイル名の衝突とは？**

        同じ名前のファイルが既にアップロードされている場合に発生します。

        **選択肢の説明:**

        - **🔄 上書き**: 既存のファイルを新しいファイルで置き換えます
          - 元のファイルIDと作成日時は保持されます
          - メタデータは新しいファイルの情報に更新されます

        - **⏭️ スキップ**: このファイルの処理をスキップします
          - 既存のファイルは変更されません
          - 新しいファイルはアップロードされません

        **推奨事項:**
        - 同じ写真の新しいバージョンの場合: **上書き**を選択
        - 異なる写真で同じ名前の場合: ファイル名を変更してから再アップロード
        - 確信がない場合: **スキップ**を選択して後で確認
        """
        )


def render_overall_status(batch_result: dict[str, Any]) -> None:
    """Render the overall status message for batch upload results."""
    total_files = batch_result["total_files"]
    successful_uploads = batch_result["successful_uploads"]
    failed_uploads = batch_result["failed_uploads"]
    skipped_uploads = batch_result.get("skipped_uploads", 0)
    overwrite_uploads = batch_result.get("overwrite_uploads", 0)

    if batch_result["success"]:
        if total_files == 1:
            if overwrite_uploads > 0:
                st.success("🎉 1枚の写真を正常に上書きしました！")
            elif skipped_uploads > 0:
                st.info("⏭️ 1枚の写真がリクエストに従ってスキップされました")
            else:
                st.success("🎉 1枚の写真を正常にアップロードしました！")
        else:
            success_parts = []
            if successful_uploads - overwrite_uploads > 0:
                success_parts.append(f"{successful_uploads - overwrite_uploads}枚アップロード")
            if overwrite_uploads > 0:
                success_parts.append(f"{overwrite_uploads}枚上書き")
            if skipped_uploads > 0:
                success_parts.append(f"{skipped_uploads}枚スキップ")

            if success_parts:
                st.success(f"🎉 {total_files}枚の写真を正常に処理しました: {', '.join(success_parts)}")
            else:
                st.success(f"🎉 {total_files}枚の写真を正常に処理しました！")
    elif successful_uploads > 0 or skipped_uploads > 0:
        status_parts = []
        if successful_uploads > 0:
            if overwrite_uploads > 0:
                status_parts.append(f"{successful_uploads}枚成功 ({overwrite_uploads}枚上書き)")
            else:
                status_parts.append(f"{successful_uploads}枚成功")
        if skipped_uploads > 0:
            status_parts.append(f"{skipped_uploads}枚スキップ")
        if failed_uploads > 0:
            status_parts.append(f"{failed_uploads}枚失敗")

        st.warning(f"⚠️ 部分的成功: {', '.join(status_parts)}")
    else:
        st.error(f"❌ アップロード失敗: {failed_uploads}枚すべてでエラーが発生しました")


def render_summary_metrics(batch_result: dict[str, Any], processing_time: float | None = None) -> None:
    """Render summary metrics for batch upload results."""
    total_files = batch_result["total_files"]
    successful_uploads = batch_result["successful_uploads"]
    failed_uploads = batch_result["failed_uploads"]
    skipped_uploads = batch_result.get("skipped_uploads", 0)
    overwrite_uploads = batch_result.get("overwrite_uploads", 0)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("総ファイル数", total_files)
    with col2:
        st.metric("成功", successful_uploads, delta=successful_uploads if successful_uploads > 0 else None)
    with col3:
        if overwrite_uploads > 0:
            st.metric("上書き", overwrite_uploads, delta=overwrite_uploads)
        else:
            st.metric("失敗", failed_uploads, delta=-failed_uploads if failed_uploads > 0 else None)
    with col4:
        if skipped_uploads > 0:
            st.metric("スキップ", skipped_uploads)
        elif processing_time:
            st.metric("処理時間", f"{processing_time:.1f}秒")
        else:
            success_rate = (successful_uploads / total_files * 100) if total_files > 0 else 0
            st.metric("成功率", f"{success_rate:.1f}%")
    with col5:
        if processing_time and (overwrite_uploads > 0 or skipped_uploads > 0):
            st.metric("処理時間", f"{processing_time:.1f}秒")
        elif failed_uploads > 0 and not (overwrite_uploads > 0 or skipped_uploads > 0):
            st.metric("失敗", failed_uploads, delta=-failed_uploads)


def render_new_uploads(new_upload_results: list[dict[str, Any]]) -> None:
    """Render new upload results."""
    if not new_upload_results:
        return

    with st.expander(f"✅ 新規アップロード ({len(new_upload_results)})", expanded=len(new_upload_results) <= 3):
        for result in new_upload_results:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.success(f"📷 **{result['filename']}**")
                if "created_at" in result:
                    st.write(f"   📅 作成日時: {result['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                if "file_size" in result:
                    file_size_mb = result["file_size"] / (1024 * 1024)
                    st.write(f"   💾 サイズ: {file_size_mb:.1f} MB")
                if "processing_steps" in result:
                    with st.expander(f"{result['filename']}の処理ステップ", expanded=False):
                        for step in result["processing_steps"]:
                            st.write(f"• {step}")
            with col2:
                st.markdown("✅ **新規アップロード**")


def render_overwrites(overwrite_results: list[dict[str, Any]]) -> None:
    """Render overwrite results."""
    if not overwrite_results:
        return


def render_skipped_files(skipped_results: list[dict[str, Any]]) -> None:
    """Render skipped files results."""
    if not skipped_results:
        return

    with st.expander(f"⏭️ スキップされたファイル ({len(skipped_results)})", expanded=len(skipped_results) <= 3):
        st.markdown("**以下のファイルはユーザーの選択によりスキップされました:**")
        st.divider()

        for result in skipped_results:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.warning(f"📷 **{result['filename']}**")
                st.markdown("**スキップ理由:**")
                st.write("   ⚠️ 同名のファイルが既に存在していました")
                st.write("   👤 ユーザーが上書きを選択せず、スキップを選択しました")
                st.write("   🔒 既存のファイルは変更されていません")

                st.info(
                    "💡 **ヒント:** 同じファイルを後でアップロードしたい場合は、ファイル名を変更するか、上書きを選択してください。"
                )
            with col2:
                st.markdown("⏭️ **スキップ済み**")
                st.markdown("---")
                st.markdown("**状態:**")
                st.write("⏭️ 処理スキップ")
                st.write("🔒 既存ファイル保護")
                st.write("👤 ユーザー選択")


def render_failed_uploads(failed_results: list[dict[str, Any]]) -> None:
    """Render failed upload results."""
    if not failed_results:
        return

    with st.expander(f"❌ 失敗したアップロード ({len(failed_results)})", expanded=True):
        # Separate overwrite failures from regular failures
        overwrite_failures = [r for r in failed_results if r.get("is_overwrite", False)]
        regular_failures = [r for r in failed_results if not r.get("is_overwrite", False)]

        # Show overwrite-specific failures first
        if overwrite_failures:
            render_overwrite_failures(overwrite_failures)

        # Show regular failures
        if regular_failures:
            render_regular_failures(regular_failures, bool(overwrite_failures))


def render_overwrite_failures(overwrite_failures: list[dict[str, Any]]) -> None:
    """Render overwrite-specific failures."""
    st.markdown("**🔄 上書き操作の失敗:**")
    for result in overwrite_failures:
        st.error(f"📷 **{result['filename']}** - {result['message']}")

        # Special handling for overwrite failures
        st.warning("⚠️ **上書き失敗の影響:** 既存のファイルは変更されていません。")

        # Show error details
        if "error" in result:
            with st.expander(f"🔍 上書きエラー詳細: {result['filename']}", expanded=False):
                col1, col2 = st.columns([1, 2])
                with col1:
                    if "error_type" in result:
                        st.write(f"**エラータイプ:** {result['error_type']}")
                    st.write(f"**ファイル:** {result['filename']}")
                    st.write("**操作:** 上書き試行")
                with col2:
                    st.code(result["error"], language="text")

        # Overwrite-specific troubleshooting
        st.info("💡 **上書き失敗のトラブルシューティング:**")
        overwrite_suggestions = [
            "既存のファイルが別のプロセスで使用されていないか確認してください",
            "データベースの整合性を確認してください",
            "一度ファイルを削除してから再アップロードを試してください",
            "ファイル名を変更して新規アップロードとして試してください",
        ]
        for suggestion in overwrite_suggestions:
            st.write(f"• {suggestion}")

        st.divider()


def render_regular_failures(regular_failures: list[dict[str, Any]], has_overwrite_failures: bool) -> None:
    """Render regular upload failures."""
    if has_overwrite_failures:
        st.markdown("**📤 通常のアップロード失敗:**")

    for result in regular_failures:
        st.error(f"📷 **{result['filename']}** - {result['message']}")

        # Show error details
        if "error" in result:
            with st.expander(f"🔍 エラー詳細: {result['filename']}", expanded=False):
                col1, col2 = st.columns([1, 2])
                with col1:
                    if "error_type" in result:
                        st.write(f"**エラータイプ:** {result['error_type']}")
                    st.write(f"**ファイル:** {result['filename']}")
                with col2:
                    st.code(result["error"], language="text")

        # Provide troubleshooting suggestions
        st.info("💡 **トラブルシューティング提案:**")
        suggestions = get_error_suggestions(result.get("error", ""), result.get("filename", ""))
        for suggestion in suggestions:
            st.write(f"• {suggestion}")


def render_detailed_results(batch_result: dict[str, Any]) -> None:
    """Render detailed results organized by type."""
    if not batch_result["results"]:
        return

    # Separate results by type
    successful_results = [r for r in batch_result["results"] if r["success"] and not r.get("skipped", False)]
    skipped_results = [r for r in batch_result["results"] if r.get("skipped", False)]
    failed_results = [r for r in batch_result["results"] if not r["success"]]

    # Further separate successful results into new uploads and overwrites
    new_upload_results = [r for r in successful_results if not r.get("is_overwrite", False)]
    overwrite_results = [r for r in successful_results if r.get("is_overwrite", False)]

    # Render each type
    render_new_uploads(new_upload_results)
    render_overwrites(overwrite_results)
    render_skipped_files(skipped_results)
    render_failed_uploads(failed_results)


def render_processing_summary(batch_result: dict[str, Any]) -> None:
    pass


def render_next_steps(batch_result: dict[str, Any]) -> None:
    """Render next steps section."""
    successful_uploads = batch_result["successful_uploads"]
    failed_uploads = batch_result["failed_uploads"]

    if batch_result["success"] and successful_uploads > 0:
        st.markdown("### 🎯 次のステップ")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🖼️ ギャラリー", use_container_width=True, type="primary"):
                st.session_state.current_page = "gallery"
                st.rerun()

        with col2:
            if st.button("📤 さらにアップロード", use_container_width=True):
                # Clear upload state for new upload
                from imgstream.ui.handlers.upload import clear_upload_session_state

                clear_upload_session_state()
                st.rerun()

        with col3:
            if st.button("🏠 ホーム", use_container_width=True):
                st.session_state.current_page = "home"
                st.rerun()

    elif failed_uploads > 0:
        st.markdown("### 🔧 ヘルプが必要ですか？")
        st.info(
            "アップロードの問題が続く場合は、インターネット接続とファイル形式を確認してください。"
            "サポートされている形式: HEIC, HEIF, JPG, JPEG"
        )

        if st.button("🔄 再試行", use_container_width=True, type="primary"):
            st.rerun()


def render_upload_results(batch_result: dict[str, Any], processing_time: float | None = None) -> None:
    """
    Render enhanced results of batch upload processing with detailed feedback.

    Args:
        batch_result: Dictionary containing batch processing results
        processing_time: Total processing time in seconds
    """
    # Render overall status
    render_overall_status(batch_result)

    # Render summary metrics
    render_summary_metrics(batch_result, processing_time)

    # Render detailed results
    render_detailed_results(batch_result)

    # Enhanced processing summary for mixed operations
    st.divider()
    render_processing_summary(batch_result)

    # Render next steps
    render_next_steps(batch_result)

    # Note: Don't automatically clear session state here to allow users to see results
    # Session state will be cleared when user navigates away or uploads new files


def get_error_suggestions(error_message: str, filename: str) -> list[str]:
    """
    Generate troubleshooting suggestions based on error message and filename.

    Args:
        error_message: The error message from failed upload
        filename: Name of the failed file

    Returns:
        list: List of troubleshooting suggestions
    """
    suggestions = []

    error_lower = error_message.lower()

    if "size" in error_lower or "large" in error_lower:
        suggestions.extend(
            [
                "ファイルサイズが許可された制限内であることを確認してください",
                "アップロード前に画像を圧縮してみてください",
                "ファイルが破損していないことを確認してください",
            ]
        )

    if "format" in error_lower or "unsupported" in error_lower:
        suggestions.extend(
            [
                "ファイル形式がサポートされていることを確認してください (HEIC, HEIF, JPG, JPEG)",
                "画像をJPEG形式に変換してみてください",
                "ファイル拡張子が実際の形式と一致することを確認してください",
            ]
        )

    if "network" in error_lower or "connection" in error_lower or "timeout" in error_lower:
        suggestions.extend(
            [
                "インターネット接続を確認してください",
                "安定した接続で再度アップロードしてみてください",
                "ファイルを小さなバッチでアップロードしてください",
            ]
        )

    if "authentication" in error_lower or "permission" in error_lower:
        suggestions.extend(
            [
                "ページを更新して再試行してください",
                "適切に認証されていることを確認してください",
                "問題が続く場合はサポートにお問い合わせください",
            ]
        )

    if "storage" in error_lower or "gcs" in error_lower:
        suggestions.extend(
            [
                "数分後に再試行してください",
                "十分なストレージ容量があることを確認してください",
                "問題が続く場合はサポートにお問い合わせください",
            ]
        )

    # Default suggestions if no specific error type detected
    if not suggestions:
        suggestions.extend(
            [
                "ファイルを再度アップロードしてみてください",
                "インターネット接続を確認してください",
                "ファイルが破損していないことを確認してください",
                "問題が続く場合はサポートにお問い合わせください",
            ]
        )

    return suggestions
