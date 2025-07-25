"""Upload page for imgstream application."""

import streamlit as st
import structlog

from imgstream.ui.auth_handlers import require_authentication
from imgstream.ui.components import render_empty_state, render_info_card
from imgstream.ui.upload_handlers import get_file_size_limits, render_file_validation_results, validate_uploaded_files

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
                if st.button(
                    f"🚀 Upload {len(st.session_state.valid_files)} Photo(s)",
                    use_container_width=True,
                    type="primary",
                ):
                    st.info("🚧 Upload processing will be implemented in task 8.2")
                    # TODO: Implement actual upload processing in task 8.2

        # Clear validation state when files are removed
        if not uploaded_files:
            st.session_state.upload_validated = False
            st.session_state.valid_files = []
            st.session_state.validation_errors = []

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
