"""Upload handlers for imgstream application."""

import streamlit as st
import structlog

from imgstream.services.image_processor import ImageProcessingError, ImageProcessor, UnsupportedFormatError
from imgstream.ui.components import format_file_size

logger = structlog.get_logger()


def validate_uploaded_files(uploaded_files: list) -> tuple[list, list]:
    """
    Validate uploaded files for format and size.

    Args:
        uploaded_files: List of uploaded file objects from Streamlit

    Returns:
        tuple: (valid_files, validation_errors)
    """
    if not uploaded_files:
        return [], []

    image_processor = ImageProcessor()
    valid_files = []
    validation_errors = []

    for uploaded_file in uploaded_files:
        try:
            # Check file format
            if not image_processor.is_supported_format(uploaded_file.name):
                validation_errors.append(
                    {
                        "filename": uploaded_file.name,
                        "error": "Unsupported file format",
                        "details": "Only HEIC, HEIF, JPG, and JPEG files are supported",
                    }
                )
                continue

            # Read file data
            file_data = uploaded_file.read()
            uploaded_file.seek(0)  # Reset file pointer for later use

            # Validate file size
            image_processor.validate_file_size(file_data, uploaded_file.name)

            # Add to valid files
            valid_files.append(
                {
                    "file_object": uploaded_file,
                    "filename": uploaded_file.name,
                    "size": len(file_data),
                    "data": file_data,
                }
            )

            logger.info("file_validation_success", filename=uploaded_file.name, size=len(file_data))

        except (ImageProcessingError, UnsupportedFormatError) as e:
            validation_errors.append({"filename": uploaded_file.name, "error": "Validation failed", "details": str(e)})
            logger.warning("file_validation_failed", filename=uploaded_file.name, error=str(e))
        except Exception as e:
            validation_errors.append(
                {
                    "filename": uploaded_file.name,
                    "error": "Unexpected error",
                    "details": f"An unexpected error occurred: {str(e)}",
                }
            )
            logger.error("file_validation_error", filename=uploaded_file.name, error=str(e))

    return valid_files, validation_errors


def render_file_validation_results(valid_files: list, validation_errors: list) -> None:
    """
    Render the results of file validation.

    Args:
        valid_files: List of valid file objects
        validation_errors: List of validation error objects
    """
    if valid_files:
        st.success(f"✅ {len(valid_files)} file(s) ready for upload")

        # Show valid files
        with st.expander("📁 Valid Files", expanded=True):
            for file_info in valid_files:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"📷 **{file_info['filename']}**")
                with col2:
                    st.write(format_file_size(file_info["size"]))
                with col3:
                    st.write("✅ Valid")

    if validation_errors:
        st.error(f"❌ {len(validation_errors)} file(s) failed validation")

        # Show validation errors
        with st.expander("⚠️ Validation Errors", expanded=True):
            for error in validation_errors:
                st.error(f"**{error['filename']}**: {error['error']}")
                if error["details"]:
                    st.write(f"Details: {error['details']}")


def get_file_size_limits() -> tuple[int, int]:
    """
    Get current file size limits from ImageProcessor.

    Returns:
        tuple: (min_size, max_size) in bytes
    """
    image_processor = ImageProcessor()
    return image_processor.MIN_FILE_SIZE, image_processor.MAX_FILE_SIZE
