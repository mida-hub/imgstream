"""Upload page for imgstream application."""

from datetime import datetime
from typing import Any

import streamlit as st
import structlog

from imgstream.ui.auth_handlers import require_authentication
from imgstream.ui.components import render_empty_state, render_info_card
from imgstream.ui.upload_handlers import (
    get_file_size_limits,
    process_batch_upload,
    render_detailed_progress_info,
    render_file_validation_results_with_collisions,
    render_upload_progress,
    render_upload_results,
    render_upload_statistics,
    validate_uploaded_files_with_collision_check,
)
from imgstream.ui.collision_components import (
    render_collision_warnings,
    render_collision_status_indicator,
    render_collision_help_section,
    get_collision_decisions_from_session,
    validate_collision_decisions,
    clear_collision_decisions,
)
from imgstream.utils.collision_detection import process_collision_results, filter_files_by_collision_decision

logger = structlog.get_logger()


def render_upload_page() -> None:
    """Render the upload page with file selection and validation."""
    if not require_authentication():
        return

    # Upload area with drag-and-drop styling
    st.markdown("### 📤 Upload Your Photos")

    # Get file size limits for display
    min_size, max_size = get_file_size_limits()
    max_size_mb = max_size / (1024 * 1024)

    # File format information
    col1, col2 = st.columns([1, 1])

    with col1:
        render_info_card(
            "Supported Formats",
            f"• HEIC (iPhone/iPad photos)\n• JPEG/JPG (Standard photos)\n"
            f"• Maximum file size: {max_size_mb:.0f}MB per photo",
            "📋",
        )

    with col2:
        render_info_card(
            "Smart Processing",
            "• Automatic EXIF data extraction\n• Thumbnail generation\n• Secure cloud storage",
            "⚙️",
        )

    # File uploader with validation
    st.markdown("#### Choose Photos to Upload")

    uploaded_files = st.file_uploader(
        "Drag and drop photos here, or click to browse",
        type=["heic", "heif", "jpg", "jpeg"],
        accept_multiple_files=True,
        help=f"Supported formats: HEIC, HEIF, JPG, JPEG. Max size: {max_size_mb:.0f}MB per file",
        key="photo_uploader",
    )

    # Initialize session state for upload management
    if "upload_validated" not in st.session_state:
        st.session_state.upload_validated = False
    if "valid_files" not in st.session_state:
        st.session_state.valid_files = []
    if "validation_errors" not in st.session_state:
        st.session_state.validation_errors = []
    if "collision_results" not in st.session_state:
        st.session_state.collision_results = {}
    if "collision_decisions_made" not in st.session_state:
        st.session_state.collision_decisions_made = False
    if "upload_in_progress" not in st.session_state:
        st.session_state.upload_in_progress = False
    if "last_upload_result" not in st.session_state:
        st.session_state.last_upload_result = None

    # Process uploaded files
    if uploaded_files:
        # Validate files when new files are uploaded (including collision detection)
        if not st.session_state.upload_validated or len(uploaded_files) != len(st.session_state.valid_files) + len(
            st.session_state.validation_errors
        ):
            with st.spinner("ファイルを検証中（衝突検出を含む）..."):
                valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(
                    uploaded_files
                )
                st.session_state.valid_files = valid_files
                st.session_state.validation_errors = validation_errors
                st.session_state.collision_results = collision_results
                st.session_state.upload_validated = True
                st.session_state.collision_decisions_made = False

                logger.info(
                    "file_validation_with_collision_completed",
                    total_files=len(uploaded_files),
                    valid_files=len(valid_files),
                    errors=len(validation_errors),
                    collisions=len(collision_results),
                )

        # Display validation results with collision information
        st.divider()
        st.markdown("#### 検証結果")
        render_file_validation_results_with_collisions(
            st.session_state.valid_files, st.session_state.validation_errors, st.session_state.collision_results
        )

        # Handle collision resolution if there are collisions
        if st.session_state.collision_results:
            st.divider()

            # Get current user decisions from session
            user_decisions = get_collision_decisions_from_session(st.session_state.collision_results)

            # Render collision warnings and collect decisions
            updated_decisions = render_collision_warnings(st.session_state.collision_results)

            # Update decisions if any were made
            if updated_decisions:
                user_decisions.update(updated_decisions)

            # Show collision status indicator
            render_collision_status_indicator(st.session_state.collision_results, user_decisions)

            # Validate that all decisions have been made
            all_decisions_made, pending_files = validate_collision_decisions(
                st.session_state.collision_results, user_decisions
            )

            if not all_decisions_made:
                st.warning(f"⚠️ {len(pending_files)} 件のファイルについて決定が必要です: {', '.join(pending_files)}")

                # Show help section
                render_collision_help_section()

                # Clear decisions button
                if st.button("🗑️ すべての決定をクリア", help="すべての衝突決定をリセットします"):
                    clear_collision_decisions(st.session_state.collision_results)
                    st.rerun()
            else:
                st.success("✅ すべての衝突について決定が完了しました。アップロードを続行できます。")
                st.session_state.collision_decisions_made = True

        # Show upload button if there are valid files
        if st.session_state.valid_files:
            st.divider()

            # Check if all collision decisions have been made
            can_upload = True
            upload_button_text = f"🚀 {len(st.session_state.valid_files)} 件のファイルをアップロード"

            if st.session_state.collision_results:
                user_decisions = get_collision_decisions_from_session(st.session_state.collision_results)
                all_decisions_made, pending_files = validate_collision_decisions(
                    st.session_state.collision_results, user_decisions
                )

                if not all_decisions_made:
                    can_upload = False
                    upload_button_text = f"⚠️ 衝突の決定が必要です ({len(pending_files)} 件)"
                else:
                    # Process collision results to determine final file list
                    processed_results = process_collision_results(st.session_state.collision_results, user_decisions)
                    filtered_files = filter_files_by_collision_decision(
                        st.session_state.valid_files, processed_results["collisions"]
                    )

                    proceed_count = len(filtered_files["proceed_files"])
                    skip_count = len(filtered_files["skip_files"])

                    if proceed_count == 0:
                        can_upload = False
                        upload_button_text = "❌ すべてのファイルがスキップされました"
                    else:
                        upload_button_text = f"🚀 {proceed_count} 件をアップロード"
                        if skip_count > 0:
                            upload_button_text += f" ({skip_count} 件をスキップ)"

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                # Disable button during upload or if decisions are pending
                upload_button_disabled = st.session_state.upload_in_progress or not can_upload

                if st.button(
                    upload_button_text,
                    use_container_width=True,
                    type="primary" if can_upload else "secondary",
                    disabled=upload_button_disabled,
                    help="衝突の決定を完了してからアップロードしてください" if not can_upload else None,
                ):
                    # Set upload in progress
                    st.session_state.upload_in_progress = True

                    # Determine which files to upload based on collision decisions
                    files_to_upload = st.session_state.valid_files

                    if st.session_state.collision_results:
                        user_decisions = get_collision_decisions_from_session(st.session_state.collision_results)
                        processed_results = process_collision_results(
                            st.session_state.collision_results, user_decisions
                        )
                        filtered_files = filter_files_by_collision_decision(
                            st.session_state.valid_files, processed_results["collisions"]
                        )
                        files_to_upload = filtered_files["proceed_files"]

                        logger.info(
                            "upload_with_collision_decisions",
                            total_files=len(st.session_state.valid_files),
                            proceed_files=len(files_to_upload),
                            skip_files=len(filtered_files["skip_files"]),
                            overwrite_files=len([f for f in files_to_upload if f.get("is_overwrite", False)]),
                        )

                    # Initialize progress tracking
                    start_time = datetime.now()
                    progress_placeholder = st.empty()
                    progress_info_placeholder = st.empty()
                    stats_placeholder = st.empty()

                    # Track processing results for real-time updates
                    processing_results: list[dict[str, Any]] = []

                    def progress_callback(
                        current_file: str, current_step: str, completed: int, total: int, stage: str = "processing"
                    ) -> None:
                        """Callback function for real-time progress updates."""
                        render_upload_progress(
                            progress_placeholder, current_file, current_step, completed, total, stage
                        )

                        # Update detailed progress info
                        render_detailed_progress_info(
                            progress_info_placeholder,
                            processing_results,
                            {"filename": current_file, "step": current_step},
                        )

                        # Update statistics
                        render_upload_statistics(stats_placeholder, start_time)

                    # Show initial progress
                    progress_callback(
                        "初期化中...",
                        "🚀 アップロードプロセスを開始中...",
                        0,
                        len(files_to_upload),
                        "processing",
                    )

                    # Get collision results with user decisions
                    collision_results_with_decisions = None
                    if st.session_state.collision_results:
                        user_decisions = get_collision_decisions_from_session(st.session_state.collision_results)
                        processed_results = process_collision_results(
                            st.session_state.collision_results, user_decisions
                        )
                        collision_results_with_decisions = processed_results["collisions"]

                    # Process the batch upload with enhanced progress tracking
                    batch_result = process_batch_upload(
                        files_to_upload, collision_results_with_decisions, progress_callback
                    )

                    # Calculate total processing time
                    end_time = datetime.now()
                    processing_time = (end_time - start_time).total_seconds()

                    # Clear progress displays
                    progress_placeholder.empty()
                    progress_info_placeholder.empty()
                    stats_placeholder.empty()

                    # Store results and reset upload state
                    st.session_state.last_upload_result = batch_result
                    st.session_state.upload_in_progress = False

                    # Show enhanced results with processing time
                    st.divider()
                    st.markdown("### 📊 Upload Results")
                    render_upload_results(batch_result, processing_time)

        # Show upload in progress indicator
        if st.session_state.upload_in_progress:
            st.info("🔄 Upload in progress... Please do not refresh the page.")

        # Clear validation state when files are removed
        if not uploaded_files:
            st.session_state.upload_validated = False
            st.session_state.valid_files = []
            st.session_state.validation_errors = []
            st.session_state.collision_results = {}
            st.session_state.collision_decisions_made = False
            st.session_state.upload_in_progress = False

            # Clear collision decisions from session state
            if st.session_state.collision_results:
                clear_collision_decisions(st.session_state.collision_results)

    else:
        # Show last upload result if available
        if st.session_state.last_upload_result and not st.session_state.upload_in_progress:
            st.divider()
            st.markdown("### 📋 Previous Upload Results")
            render_upload_results(st.session_state.last_upload_result)

            # Clear results button
            if st.button("🗑️ Clear Results", use_container_width=True):
                # Clear all upload-related session state
                from imgstream.ui.upload_handlers import clear_upload_session_state

                clear_upload_session_state()
                st.rerun()
        else:
            # Show empty state when no files are uploaded
            render_empty_state(
                title="No Photos Selected",
                description="Choose photos from your device to upload to your personal collection.",
                icon="📁",
            )

    # Upload tips
    with st.expander("💡 Upload Tips"):
        st.markdown(
            f"""
        **For Best Results:**

        - 📱 **iPhone Users**: HEIC format is fully supported
        - 📷 **Camera Photos**: EXIF data will be preserved for date sorting
        - 🗂️ **Batch Upload**: Select multiple photos at once
        - 📶 **Connection**: Ensure stable internet for large uploads
        - 💾 **Storage**: Photos are automatically organized by date
        - 🔒 **Privacy**: All uploads are private to your account

        **File Requirements:**
        - Supported formats: HEIC, HEIF, JPG, JPEG
        - Maximum file size: {max_size_mb:.0f}MB per photo
        - Minimum file size: {min_size} bytes
        """
        )

    # Storage information
    st.divider()
    st.markdown("### 💾 Storage Information")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Available Storage", "Unlimited*", help="Subject to GCP quotas")
    with col2:
        st.metric("Current Usage", "0 MB", help="Total storage used")
    with col3:
        st.metric("Photos Uploaded", "0", help="Total number of photos")
