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


def process_batch_upload(valid_files: list[dict[str, Any]], progress_callback: Any = None) -> dict[str, Any]:
    """
    Process multiple files through the upload pipeline with progress tracking.

    Args:
        valid_files: List of validated file information dictionaries
        progress_callback: Optional callback function for progress updates

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
    total_files = len(valid_files)

    # Process each file with progress tracking
    for index, file_info in enumerate(valid_files):
        filename = file_info["filename"]

        # Update progress before processing
        if progress_callback:
            progress_callback(
                current_file=filename,
                current_step="Starting processing...",
                completed=index,
                total=total_files,
                stage="processing",
            )

        # Process the file with detailed step tracking
        result = process_single_upload_with_progress(file_info, progress_callback, index, total_files)
        results.append(result)

        if result["success"]:
            successful_uploads += 1
        else:
            failed_uploads += 1

        # Update progress after processing
        if progress_callback:
            status = "✅ Completed" if result["success"] else "❌ Failed"
            progress_callback(
                current_file=filename,
                current_step=status,
                completed=index + 1,
                total=total_files,
                stage="completed" if result["success"] else "failed",
            )

    # Create summary
    batch_result = {
        "success": failed_uploads == 0,
        "total_files": total_files,
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads,
        "results": results,
        "message": f"Processed {total_files} files: {successful_uploads} successful, {failed_uploads} failed",
    }

    logger.info("batch_upload_completed", total_files=total_files, successful=successful_uploads, failed=failed_uploads)

    return batch_result


def process_single_upload_with_progress(
    file_info: dict[str, Any], progress_callback: Any = None, file_index: int = 0, total_files: int = 1
) -> dict[str, Any]:
    """
    Process a single file upload with detailed progress tracking.

    Args:
        file_info: Dictionary containing file information from validation
        progress_callback: Optional callback function for progress updates
        file_index: Index of current file in batch
        total_files: Total number of files in batch

    Returns:
        dict: Processing result with success status and details
    """
    filename = file_info["filename"]
    file_data = file_info["data"]

    def update_progress(step: str, stage: str = "processing") -> None:
        if progress_callback:
            progress_callback(
                current_file=filename, current_step=step, completed=file_index, total=total_files, stage=stage
            )

    try:
        logger.info("upload_processing_started", filename=filename, size=len(file_data))
        update_progress("🔐 Authenticating user...")

        # Get services
        auth_service = get_auth_service()
        image_processor = ImageProcessor()
        storage_service = get_storage_service()

        # Ensure user is authenticated
        user_info = auth_service.ensure_authenticated()

        # Get metadata service for this user
        metadata_service = get_metadata_service(user_info.user_id)

        # Step 1: Extract EXIF metadata
        update_progress("📊 Extracting image metadata...")
        logger.info("extracting_exif_metadata", filename=filename)
        try:
            creation_date = image_processor.extract_creation_date(file_data)
        except Exception as e:
            logger.warning("exif_extraction_failed", filename=filename, error=str(e))
            # Use current time as fallback
            creation_date = datetime.now()

        # Step 2: Generate thumbnail
        update_progress("🖼️ Generating thumbnail...")
        logger.info("generating_thumbnail", filename=filename)
        thumbnail_data = image_processor.generate_thumbnail(file_data)

        # Step 3: Upload original image to GCS
        update_progress("☁️ Uploading original image...")
        logger.info("uploading_original_image", filename=filename)
        original_upload_result = storage_service.upload_original_photo(user_info.user_id, file_data, filename)
        original_gcs_path = original_upload_result["gcs_path"]

        # Step 4: Upload thumbnail to GCS
        update_progress("🔄 Uploading thumbnail...")
        logger.info("uploading_thumbnail", filename=filename)
        thumbnail_upload_result = storage_service.upload_thumbnail(user_info.user_id, thumbnail_data, filename)
        thumbnail_gcs_path = thumbnail_upload_result["gcs_path"]

        # Step 5: Save metadata to DuckDB
        update_progress("💾 Saving metadata...")
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

        update_progress("✅ Upload completed!", "success")
        logger.info("upload_processing_completed", filename=filename)

        return {
            "success": True,
            "filename": filename,
            "original_path": original_gcs_path,
            "thumbnail_path": thumbnail_gcs_path,
            "creation_date": creation_date,
            "file_size": len(file_data),
            "processing_steps": [
                "Authentication verified",
                "EXIF metadata extracted",
                "Thumbnail generated",
                "Original image uploaded to GCS",
                "Thumbnail uploaded to GCS",
                "Metadata saved to database",
            ],
            "message": f"Successfully uploaded {filename}",
        }

    except Exception as e:
        update_progress(f"❌ Error: {str(e)}", "error")
        logger.error("upload_processing_failed", filename=filename, error=str(e))
        return {
            "success": False,
            "filename": filename,
            "error": str(e),
            "error_type": type(e).__name__,
            "message": f"Failed to upload {filename}: {str(e)}",
        }


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
    Render detailed progress information including completed files and current processing.

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
                st.metric("Completed", len(batch_results))
            with col2:
                st.metric("Successful", successful, delta=successful if successful > 0 else None)
            with col3:
                st.metric("Failed", failed, delta=-failed if failed > 0 else None)

            # Show recent completions
            if batch_results:
                with st.expander("📋 Recent Completions", expanded=False):
                    for result in batch_results[-5:]:  # Show last 5 results
                        status_icon = "✅" if result.get("success", False) else "❌"
                        filename = result.get("filename", "Unknown")
                        message = result.get("message", "No message")
                        st.write(f"{status_icon} **{filename}** - {message}")

        if current_processing:
            st.markdown("### 🔄 Current Processing")
            filename = current_processing.get("filename", "Unknown")
            step = current_processing.get("step", "Processing...")
            st.info(f"**{filename}**: {step}")


def render_upload_statistics(
    stats_placeholder: Any, start_time: datetime, batch_result: dict[str, Any] | None = None
) -> None:
    """
    Render upload statistics including timing and performance metrics.

    Args:
        stats_placeholder: Streamlit placeholder for statistics
        start_time: When the upload process started
        batch_result: Final batch processing results
    """
    with stats_placeholder.container():
        current_time = datetime.now()
        elapsed_time = current_time - start_time

        st.markdown("### 📊 Upload Statistics")

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


def render_upload_results(batch_result: dict[str, Any], processing_time: float | None = None) -> None:
    """
    Render enhanced results of batch upload processing with detailed feedback.

    Args:
        batch_result: Dictionary containing batch processing results
        processing_time: Total processing time in seconds
    """
    total_files = batch_result["total_files"]
    successful_uploads = batch_result["successful_uploads"]
    failed_uploads = batch_result["failed_uploads"]

    # Enhanced overall status with more context
    if batch_result["success"]:
        if successful_uploads == 1:
            st.success("🎉 Successfully uploaded 1 photo!")
        else:
            st.success(f"🎉 Successfully uploaded all {successful_uploads} photos!")
    elif successful_uploads > 0:
        st.warning(f"⚠️ Partial success: {successful_uploads} uploaded, {failed_uploads} failed")
    else:
        st.error(f"❌ Upload failed: All {failed_uploads} files encountered errors")

    # Enhanced summary metrics with additional information
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Files", total_files)
    with col2:
        st.metric("Successful", successful_uploads, delta=successful_uploads if successful_uploads > 0 else None)
    with col3:
        st.metric("Failed", failed_uploads, delta=-failed_uploads if failed_uploads > 0 else None)
    with col4:
        if processing_time:
            st.metric("Processing Time", f"{processing_time:.1f}s")
        else:
            success_rate = (successful_uploads / total_files * 100) if total_files > 0 else 0
            st.metric("Success Rate", f"{success_rate:.1f}%")

    # Enhanced detailed results with better organization
    if batch_result["results"]:
        # Separate successful and failed results
        successful_results = [r for r in batch_result["results"] if r["success"]]
        failed_results = [r for r in batch_result["results"] if not r["success"]]

        # Show successful uploads
        if successful_results:
            with st.expander(
                f"✅ Successful Uploads ({len(successful_results)})", expanded=len(successful_results) <= 3
            ):
                for result in successful_results:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.success(f"📷 **{result['filename']}**")
                        if "creation_date" in result:
                            st.write(f"   📅 Created: {result['creation_date'].strftime('%Y-%m-%d %H:%M:%S')}")
                        if "file_size" in result:
                            file_size_mb = result["file_size"] / (1024 * 1024)
                            st.write(f"   💾 Size: {file_size_mb:.1f} MB")
                        if "processing_steps" in result:
                            with st.expander(f"Processing steps for {result['filename']}", expanded=False):
                                for step in result["processing_steps"]:
                                    st.write(f"• {step}")
                    with col2:
                        st.markdown("✅ **Success**")

        # Show failed uploads with detailed error information
        if failed_results:
            with st.expander(f"❌ Failed Uploads ({len(failed_results)})", expanded=True):
                for result in failed_results:
                    st.error(f"📷 **{result['filename']}** - {result['message']}")

                    # Show error details
                    if "error" in result:
                        with st.expander(f"🔍 Error Details: {result['filename']}", expanded=False):
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                if "error_type" in result:
                                    st.write(f"**Error Type:** {result['error_type']}")
                                st.write(f"**File:** {result['filename']}")
                            with col2:
                                st.code(result["error"], language="text")

                    # Provide troubleshooting suggestions
                    st.info("💡 **Troubleshooting suggestions:**")
                    suggestions = get_error_suggestions(result.get("error", ""), result.get("filename", ""))
                    for suggestion in suggestions:
                        st.write(f"• {suggestion}")

    # Processing summary and next steps
    st.divider()

    if batch_result["success"] and successful_uploads > 0:
        st.markdown("### 🎯 Next Steps")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🖼️ View Gallery", use_container_width=True, type="primary"):
                st.session_state.current_page = "gallery"
                st.rerun()

        with col2:
            if st.button("📤 Upload More", use_container_width=True):
                # Clear upload state for new upload
                clear_upload_session_state()
                st.rerun()

        with col3:
            if st.button("🏠 Go Home", use_container_width=True):
                st.session_state.current_page = "home"
                st.rerun()

        # Show storage information
        st.markdown("### 💾 Storage Information")
        st.info(
            "📊 Your photos are securely stored in Google Cloud Storage with automatic lifecycle management. "
            "Original photos will be moved to cost-effective Coldline storage after 30 days."
        )

    elif failed_uploads > 0:
        st.markdown("### 🔧 Need Help?")
        st.info(
            "If you continue to experience upload issues, please check your internet connection and file formats. "
            "Supported formats: HEIC, HEIF, JPG, JPEG"
        )

        if st.button("🔄 Try Again", use_container_width=True, type="primary"):
            st.rerun()

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
                "Check if the file size is within the allowed limit",
                "Try compressing the image before uploading",
                "Ensure the file is not corrupted",
            ]
        )

    if "format" in error_lower or "unsupported" in error_lower:
        suggestions.extend(
            [
                "Verify the file format is supported (HEIC, HEIF, JPG, JPEG)",
                "Try converting the image to JPEG format",
                "Check if the file extension matches the actual format",
            ]
        )

    if "network" in error_lower or "connection" in error_lower or "timeout" in error_lower:
        suggestions.extend(
            [
                "Check your internet connection",
                "Try uploading again with a stable connection",
                "Upload files in smaller batches",
            ]
        )

    if "authentication" in error_lower or "permission" in error_lower:
        suggestions.extend(
            [
                "Refresh the page and try again",
                "Ensure you're properly authenticated",
                "Contact support if the issue persists",
            ]
        )

    if "storage" in error_lower or "gcs" in error_lower:
        suggestions.extend(
            [
                "Try again in a few minutes",
                "Check if you have sufficient storage quota",
                "Contact support if the issue persists",
            ]
        )

    # Default suggestions if no specific error type detected
    if not suggestions:
        suggestions.extend(
            [
                "Try uploading the file again",
                "Check your internet connection",
                "Verify the file is not corrupted",
                "Contact support if the issue continues",
            ]
        )

    return suggestions


def clear_upload_session_state() -> None:
    """Clear upload-related session state variables."""
    session_keys_to_clear = [
        "valid_files",
        "validation_errors",
        "upload_validated",
        "upload_in_progress",
        "upload_results",
        "last_upload_result",  # Add this to clear the upload result
    ]

    for key in session_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
