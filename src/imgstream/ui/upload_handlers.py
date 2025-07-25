"""Upload handlers for imgstream application."""

from datetime import datetime
from typing import Any

import streamlit as st
import structlog

from imgstream.models.photo import PhotoMetadata
from imgstream.services.auth import get_auth_service
from imgstream.services.image_processor import ImageProcessingError, ImageProcessor, UnsupportedFormatError
from imgstream.services.metadata import get_metadata_service
from imgstream.services.storage import get_storage_service
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


def process_single_upload(file_info: dict[str, Any]) -> dict[str, Any]:
    """
    Process a single file upload through the complete pipeline.

    Args:
        file_info: Dictionary containing file information from validation

    Returns:
        dict: Processing result with success status and details
    """
    filename = file_info["filename"]
    file_data = file_info["data"]

    try:
        logger.info("upload_processing_started", filename=filename, size=len(file_data))

        # Get services
        auth_service = get_auth_service()
        image_processor = ImageProcessor()
        storage_service = get_storage_service()

        # Ensure user is authenticated
        user_info = auth_service.ensure_authenticated()

        # Get metadata service for this user
        metadata_service = get_metadata_service(user_info.user_id)

        # Step 1: Extract EXIF metadata
        logger.info("extracting_exif_metadata", filename=filename)
        try:
            creation_date = image_processor.extract_creation_date(file_data)
        except Exception as e:
            logger.warning("exif_extraction_failed", filename=filename, error=str(e))
            # Use current time as fallback
            creation_date = datetime.now()

        # Step 2: Generate thumbnail
        logger.info("generating_thumbnail", filename=filename)
        thumbnail_data = image_processor.generate_thumbnail(file_data)

        # Step 3: Upload original image to GCS
        logger.info("uploading_original_image", filename=filename)
        original_upload_result = storage_service.upload_original_photo(user_info.user_id, file_data, filename)
        original_gcs_path = original_upload_result["gcs_path"]

        # Step 4: Upload thumbnail to GCS
        logger.info("uploading_thumbnail", filename=filename)
        thumbnail_upload_result = storage_service.upload_thumbnail(user_info.user_id, thumbnail_data, filename)
        thumbnail_gcs_path = thumbnail_upload_result["gcs_path"]

        # Step 5: Save metadata to DuckDB
        logger.info("saving_metadata", filename=filename)

        # Determine MIME type based on file extension
        file_extension = filename.lower().split(".")[-1]
        mime_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "heic": "image/heic", "heif": "image/heif"}.get(
            file_extension, "application/octet-stream"
        )

        photo_metadata = PhotoMetadata.create_new(
            user_id=user_info.user_id,
            filename=filename,
            original_path=original_gcs_path,
            thumbnail_path=thumbnail_gcs_path,
            file_size=len(file_data),
            mime_type=mime_type,
            created_at=creation_date,
            uploaded_at=datetime.now(),
        )

        metadata_service.save_photo_metadata(photo_metadata)

        logger.info("upload_processing_completed", filename=filename)

        return {
            "success": True,
            "filename": filename,
            "original_path": original_gcs_path,
            "thumbnail_path": thumbnail_gcs_path,
            "creation_date": creation_date,
            "message": f"Successfully uploaded {filename}",
        }

    except Exception as e:
        logger.error("upload_processing_failed", filename=filename, error=str(e))
        return {
            "success": False,
            "filename": filename,
            "error": str(e),
            "message": f"Failed to upload {filename}: {str(e)}",
        }


def process_batch_upload(valid_files: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Process multiple files through the upload pipeline.

    Args:
        valid_files: List of validated file information dictionaries

    Returns:
        dict: Batch processing results with success/failure counts and details
    """
    if not valid_files:
        return {
            "success": True,
            "total_files": 0,
            "successful_uploads": 0,
            "failed_uploads": 0,
            "results": [],
            "message": "No files to process",
        }

    logger.info("batch_upload_started", total_files=len(valid_files))

    results = []
    successful_uploads = 0
    failed_uploads = 0

    # Process each file
    for file_info in valid_files:
        result = process_single_upload(file_info)
        results.append(result)

        if result["success"]:
            successful_uploads += 1
        else:
            failed_uploads += 1

    # Create summary
    batch_result = {
        "success": failed_uploads == 0,
        "total_files": len(valid_files),
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads,
        "results": results,
        "message": f"Processed {len(valid_files)} files: {successful_uploads} successful, {failed_uploads} failed",
    }

    logger.info(
        "batch_upload_completed", total_files=len(valid_files), successful=successful_uploads, failed=failed_uploads
    )

    return batch_result


def render_upload_progress(
    progress_placeholder: Any, current_file: str, current_step: str, completed: int, total: int
) -> None:
    """
    Render upload progress information.

    Args:
        progress_placeholder: Streamlit placeholder for progress display
        current_file: Name of file currently being processed
        current_step: Current processing step
        completed: Number of completed files
        total: Total number of files
    """
    progress_percentage = (completed / total) * 100 if total > 0 else 0

    with progress_placeholder.container():
        st.progress(progress_percentage / 100, text=f"Processing {completed}/{total} files")

        if current_file:
            st.write(f"📷 **Current file:** {current_file}")
            st.write(f"⚙️ **Step:** {current_step}")


def render_upload_results(batch_result: dict[str, Any]) -> None:
    """
    Render the results of batch upload processing.

    Args:
        batch_result: Dictionary containing batch processing results
    """
    total_files = batch_result["total_files"]
    successful_uploads = batch_result["successful_uploads"]
    failed_uploads = batch_result["failed_uploads"]

    # Overall status
    if batch_result["success"]:
        st.success(f"✅ Successfully uploaded {successful_uploads} photo(s)!")
    else:
        st.warning(f"⚠️ Upload completed with {failed_uploads} error(s)")

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Files", total_files)
    with col2:
        st.metric("Successful", successful_uploads, delta=successful_uploads if successful_uploads > 0 else None)
    with col3:
        st.metric("Failed", failed_uploads, delta=-failed_uploads if failed_uploads > 0 else None)

    # Detailed results
    if batch_result["results"]:
        with st.expander("📋 Detailed Results", expanded=failed_uploads > 0):
            for result in batch_result["results"]:
                if result["success"]:
                    st.success(f"✅ **{result['filename']}** - {result['message']}")
                    if "creation_date" in result:
                        st.write(f"   📅 Creation date: {result['creation_date'].strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    st.error(f"❌ **{result['filename']}** - {result['message']}")
                    if "error" in result:
                        with st.expander(f"Error details for {result['filename']}"):
                            st.code(result["error"])

    # Clear session state after successful upload
    if batch_result["success"] and successful_uploads > 0:
        # Clear upload-related session state
        if "valid_files" in st.session_state:
            st.session_state.valid_files = []
        if "validation_errors" in st.session_state:
            st.session_state.validation_errors = []
        if "upload_validated" in st.session_state:
            st.session_state.upload_validated = False
