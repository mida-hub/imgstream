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
    render_file_validation_results,
    render_upload_progress,
    render_upload_results,
    render_upload_statistics,
    validate_uploaded_files,
)

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
    if "upload_in_progress" not in st.session_state:
        st.session_state.upload_in_progress = False
    if "last_upload_result" not in st.session_state:
        st.session_state.last_upload_result = None

    # Process uploaded files
    if uploaded_files:
        # Validate files when new files are uploaded
        if not st.session_state.upload_validated or len(uploaded_files) != len(st.session_state.valid_files) + len(
            st.session_state.validation_errors
        ):
            with st.spinner("Validating uploaded files..."):
                valid_files, validation_errors = validate_uploaded_files(uploaded_files)
                st.session_state.valid_files = valid_files
                st.session_state.validation_errors = validation_errors
                st.session_state.upload_validated = True

                logger.info(
                    "file_validation_completed",
                    total_files=len(uploaded_files),
                    valid_files=len(valid_files),
                    errors=len(validation_errors),
                )

        # Display validation results
        st.divider()
        st.markdown("#### Validation Results")
        render_file_validation_results(st.session_state.valid_files, st.session_state.validation_errors)

        # Show upload button if there are valid files
        if st.session_state.valid_files:
            st.divider()
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                # Disable button during upload
                upload_button_disabled = st.session_state.upload_in_progress

                if st.button(
                    f"🚀 Upload {len(st.session_state.valid_files)} Photo(s)",
                    use_container_width=True,
                    type="primary",
                    disabled=upload_button_disabled,
                ):
                    # Set upload in progress
                    st.session_state.upload_in_progress = True
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
                        "Initializing...",
                        "🚀 Starting upload process...",
                        0,
                        len(st.session_state.valid_files),
                        "processing",
                    )

                    # Process the batch upload with enhanced progress tracking
                    batch_result = process_batch_upload(st.session_state.valid_files, progress_callback)

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
            st.session_state.upload_in_progress = False

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
