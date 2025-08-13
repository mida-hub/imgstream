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
from imgstream.ui.handlers.collision_detection import (
    check_filename_collisions_with_fallback,
    check_filename_collisions_optimized,
    CollisionDetectionError,
    CollisionDetectionRecoveryError,
)


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


def validate_uploaded_files_with_collision_check(uploaded_files: list) -> tuple[list, list, dict]:
    """
    Validate uploaded files for format, size, and filename collisions.

    Args:
        uploaded_files: List of uploaded file objects from Streamlit

    Returns:
        tuple: (valid_files, validation_errors, collision_results)
               collision_results: Dict mapping filename to collision info
    """
    if not uploaded_files:
        return [], [], {}

    # First, perform standard validation
    valid_files, validation_errors = validate_uploaded_files(uploaded_files)

    if not valid_files:
        # No valid files to check for collisions
        return valid_files, validation_errors, {}

    # Extract filenames from valid files for collision detection
    filenames = [file_info["filename"] for file_info in valid_files]

    try:
        # Get current user for collision detection
        auth_service = get_auth_service()
        user_info = auth_service.ensure_authenticated()

        # Use optimized collision detection for better performance
        if len(filenames) > 20:  # Use optimized version for larger batches
            try:
                collision_results = check_filename_collisions_optimized(user_info.user_id, filenames, batch_size=50)
                fallback_used = False
            except (CollisionDetectionError, CollisionDetectionRecoveryError):
                # Fall back to regular collision detection with fallback
                collision_results, fallback_used = check_filename_collisions_with_fallback(
                    user_info.user_id, filenames, enable_fallback=True
                )
        else:
            # Use regular collision detection with fallback for smaller batches
            collision_results, fallback_used = check_filename_collisions_with_fallback(
                user_info.user_id, filenames, enable_fallback=True
            )

        if fallback_used:
            # Add warning about fallback mode
            validation_errors.append(
                {
                    "filename": "システム",
                    "error": "衝突検出フォールバック",
                    "details": "衝突検出に問題が発生したため、安全モードで動作しています。すべてのファイルで既存ファイルの確認を求める場合があります。",
                }
            )

        logger.info(
            "file_validation_with_collision_completed",
            total_files=len(uploaded_files),
            valid_files=len(valid_files),
            validation_errors=len(validation_errors),
            collisions_found=len(collision_results),
            fallback_used=fallback_used,
        )

        return valid_files, validation_errors, collision_results

    except (CollisionDetectionError, CollisionDetectionRecoveryError) as e:
        logger.error(
            "collision_detection_completely_failed",
            error=str(e),
            total_files=len(uploaded_files),
            error_type=type(e).__name__,
        )

        # Provide user-friendly error message with recovery options
        error_details = _get_collision_detection_error_message(e)
        validation_errors.append(
            {
                "filename": "システム",
                "error": "衝突検出失敗",
                "details": error_details,
                "recovery_options": [
                    "しばらく待ってから再試行してください",
                    "ファイル数を減らして再試行してください",
                    "ネットワーク接続を確認してください",
                    "問題が続く場合は管理者にお問い合わせください",
                ],
            }
        )
        return valid_files, validation_errors, {}

    except Exception as e:
        logger.error(
            "unexpected_error_during_collision_check",
            error=str(e),
            total_files=len(uploaded_files),
            error_type=type(e).__name__,
        )

        # Continue without collision detection on unexpected errors
        validation_errors.append(
            {
                "filename": "システム",
                "error": "予期しないエラー",
                "details": "衝突検出中に予期しないエラーが発生しました。アップロードは続行できますが、既存ファイルの上書きにご注意ください。",
                "recovery_options": [
                    "アップロードを続行する（注意が必要）",
                    "ページを再読み込みして再試行する",
                    "ファイルを個別にアップロードする",
                ],
            }
        )
        return valid_files, validation_errors, {}


def get_file_size_limits() -> tuple[int, int]:
    """
    Get current file size limits from ImageProcessor.

    Returns:
        tuple: (min_size, max_size) in bytes
    """
    image_processor = ImageProcessor()
    return image_processor.MIN_FILE_SIZE, image_processor.MAX_FILE_SIZE


def process_single_upload(file_info: dict[str, Any], is_overwrite: bool = False) -> dict[str, Any]:
    """
    Process a single file upload through the complete pipeline.

    Args:
        file_info: Dictionary containing file information from validation
        is_overwrite: Whether this is an overwrite operation

    Returns:
        dict: Processing result with success status and details
    """
    filename = file_info["filename"]
    file_data = file_info["data"]

    try:
        operation_type = "overwrite" if is_overwrite else "new_upload"
        logger.info("upload_processing_started", filename=filename, size=len(file_data), operation_type=operation_type)

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
            created_at = image_processor.extract_created_at(file_data)
        except Exception as e:
            logger.warning("exif_extraction_failed", filename=filename, error=str(e))
            # Use current time as fallback
            created_at = datetime.now()

        # Step 2: Generate thumbnail
        logger.info("generating_thumbnail", filename=filename)
        thumbnail_data = image_processor.generate_thumbnail(file_data)

        # Step 3: Upload original image to GCS
        logger.info("uploading_original_image", filename=filename, is_overwrite=is_overwrite)
        original_upload_result = storage_service.upload_original_photo(user_info.user_id, file_data, filename)
        original_gcs_path = original_upload_result["gcs_path"]

        # Step 4: Upload thumbnail to GCS
        logger.info("uploading_thumbnail", filename=filename, is_overwrite=is_overwrite)
        thumbnail_upload_result = storage_service.upload_thumbnail(user_info.user_id, thumbnail_data, filename)
        thumbnail_gcs_path = thumbnail_upload_result["gcs_path"]

        # Step 5: Save or update metadata in DuckDB
        logger.info("saving_metadata", filename=filename, is_overwrite=is_overwrite)

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
            created_at=created_at,
            uploaded_at=datetime.now(),
        )

        # Use the new save_or_update method based on operation type
        metadata_service.save_or_update_photo_metadata(photo_metadata, is_overwrite=is_overwrite)

        operation_message = "overwritten" if is_overwrite else "uploaded"
        logger.info("upload_processing_completed", filename=filename, operation_type=operation_type)

        return {
            "success": True,
            "filename": filename,
            "original_path": original_gcs_path,
            "thumbnail_path": thumbnail_gcs_path,
            "created_at": created_at,
            "is_overwrite": is_overwrite,
            "message": f"正常にアップロードしました {operation_message} {filename}",
        }

    except Exception as e:
        operation_type = "overwrite" if is_overwrite else "upload"
        logger.error("upload_processing_failed", filename=filename, error=str(e), operation_type=operation_type)
        return {
            "success": False,
            "filename": filename,
            "error": str(e),
            "is_overwrite": is_overwrite,
            "message": f"アップロードに失敗しました: {filename}",
        }


def _update_progress_before_processing(progress_callback: Any, filename: str, index: int, total_files: int) -> None:
    """Update progress before processing a file."""
    if progress_callback:
        progress_callback(
            current_file=filename,
            current_step="Starting processing...",
            completed=index,
            total=total_files,
            stage="processing",
        )


def _determine_processing_action(filename: str, collision_results: dict[str, Any]) -> dict[str, Any]:
    """
    Determine what action to take for a file based on collision status.

    Returns:
        dict: Action information with 'action', 'is_overwrite', and 'reason' keys
    """
    collision_info = collision_results.get(filename)
    if not collision_info:
        return {"action": "process", "is_overwrite": False, "reason": "no_collision"}

    user_decision = collision_info.get("user_decision", "pending")

    if user_decision == "skip":
        return {"action": "skip", "is_overwrite": False, "reason": "user_decision"}
    elif user_decision == "overwrite":
        logger.info("file_marked_for_overwrite", filename=filename)
        return {"action": "process", "is_overwrite": True, "reason": "user_overwrite"}
    else:
        logger.warning("file_collision_decision_pending", filename=filename)
        return {"action": "error", "is_overwrite": False, "reason": "decision_pending"}


def _handle_skip_file(filename: str, reason: str) -> dict[str, Any]:
    """Handle skipping a file."""
    logger.info("file_skipped_by_user_decision", filename=filename)
    return {
        "success": True,
        "filename": filename,
        "skipped": True,
        "is_overwrite": False,
        "message": f"Skipped {filename} (user decision)",
    }


def _handle_processing_error(filename: str, reason: str) -> dict[str, Any]:
    """Handle processing error for a file."""
    return {
        "success": False,
        "filename": filename,
        "error": "User decision pending for collision",
        "is_overwrite": False,
        "message": f"Failed to process {filename}: User decision required for collision",
    }


def _update_progress_after_skip(progress_callback: Any, filename: str, index: int, total_files: int) -> None:
    """Update progress after skipping a file."""
    if progress_callback:
        progress_callback(
            current_file=filename,
            current_step="⏭️ Skipped by user",
            completed=index + 1,
            total=total_files,
            stage="skipped",
        )


def _update_progress_after_error(progress_callback: Any, filename: str, index: int, total_files: int) -> None:
    """Update progress after a processing error."""
    if progress_callback:
        progress_callback(
            current_file=filename,
            current_step="❌ Decision pending",
            completed=index + 1,
            total=total_files,
            stage="failed",
        )


def _update_upload_counters(
    result: dict[str, Any], is_overwrite: bool, successful_uploads: int, failed_uploads: int, overwrite_uploads: int
) -> tuple[int, int, int]:
    """Update upload counters based on result."""
    if result["success"]:
        successful_uploads += 1
        if is_overwrite:
            overwrite_uploads += 1
    else:
        failed_uploads += 1
    return successful_uploads, failed_uploads, overwrite_uploads


def _update_progress_after_processing(
    progress_callback: Any, filename: str, result: dict[str, Any], is_overwrite: bool, index: int, total_files: int
) -> None:
    """Update progress after processing a file."""
    if progress_callback:
        if result["success"]:
            status = "✅ Overwritten" if is_overwrite else "✅ Uploaded"
            stage = "completed"
        else:
            status = "❌ Failed"
            stage = "failed"

        progress_callback(
            current_file=filename,
            current_step=status,
            completed=index + 1,
            total=total_files,
            stage=stage,
        )


def process_batch_upload(
    valid_files: list[dict[str, Any]], collision_results: dict[str, Any] | None = None, progress_callback: Any = None
) -> dict[str, Any]:
    """
    Process multiple files through the upload pipeline with progress tracking and collision handling.

    Args:
        valid_files: List of validated file information dictionaries
        collision_results: Dictionary mapping filename to collision info with user decisions
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
            "skipped_uploads": 0,
            "overwrite_uploads": 0,
            "results": [],
            "message": "No files to process",
        }

    collision_results = collision_results or {}
    logger.info("batch_upload_started", total_files=len(valid_files), collisions_detected=len(collision_results))

    results = []
    successful_uploads = 0
    failed_uploads = 0
    skipped_uploads = 0
    overwrite_uploads = 0
    total_files = len(valid_files)

    # Process each file with progress tracking
    for index, file_info in enumerate(valid_files):
        filename = file_info["filename"]

        # Update progress before processing
        _update_progress_before_processing(progress_callback, filename, index, total_files)

        # Determine processing action based on collision status
        processing_action = _determine_processing_action(filename, collision_results)

        if processing_action["action"] == "skip":
            result = _handle_skip_file(filename, processing_action["reason"])
            results.append(result)
            skipped_uploads += 1
            _update_progress_after_skip(progress_callback, filename, index, total_files)
            continue

        if processing_action["action"] == "error":
            result = _handle_processing_error(filename, processing_action["reason"])
            results.append(result)
            failed_uploads += 1
            _update_progress_after_error(progress_callback, filename, index, total_files)
            continue

        # Process the file with detailed step tracking
        is_overwrite = processing_action["is_overwrite"]
        result = process_single_upload_with_progress(
            file_info, progress_callback, index, total_files, is_overwrite=is_overwrite
        )
        results.append(result)

        # Update counters
        successful_uploads, failed_uploads, overwrite_uploads = _update_upload_counters(
            result, is_overwrite, successful_uploads, failed_uploads, overwrite_uploads
        )

        # Update progress after processing
        _update_progress_after_processing(progress_callback, filename, result, is_overwrite, index, total_files)

    # Create summary
    batch_result = {
        "success": failed_uploads == 0,
        "total_files": total_files,
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads,
        "skipped_uploads": skipped_uploads,
        "overwrite_uploads": overwrite_uploads,
        "results": results,
        "message": f"Processed {total_files} files: {successful_uploads} successful ({overwrite_uploads} overwrites), {skipped_uploads} skipped, {failed_uploads} failed",
    }

    logger.info(
        "batch_upload_completed",
        total_files=total_files,
        successful=successful_uploads,
        failed=failed_uploads,
        skipped=skipped_uploads,
        overwrites=overwrite_uploads,
    )

    return batch_result


def process_single_upload_with_progress(
    file_info: dict[str, Any],
    progress_callback: Any = None,
    file_index: int = 0,
    total_files: int = 1,
    is_overwrite: bool = False,
) -> dict[str, Any]:
    """
    Process a single file upload with detailed progress tracking.

    Args:
        file_info: Dictionary containing file information from validation
        progress_callback: Optional callback function for progress updates
        file_index: Index of current file in batch
        total_files: Total number of files in batch
        is_overwrite: Whether this is an overwrite operation

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
        operation_type = "overwrite" if is_overwrite else "new_upload"
        logger.info("upload_processing_started", filename=filename, size=len(file_data), operation_type=operation_type)
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
            created_at = image_processor.extract_created_at(file_data)
        except Exception as e:
            logger.warning("exif_extraction_failed", filename=filename, error=str(e))
            # Use current time as fallback
            created_at = datetime.now()

        # Step 2: Generate thumbnail
        update_progress("🖼️ Generating thumbnail...")
        logger.info("generating_thumbnail", filename=filename)
        thumbnail_data = image_processor.generate_thumbnail(file_data)

        # Step 3: Upload original image to GCS
        operation_text = "Overwriting" if is_overwrite else "Uploading"
        update_progress(f"☁️ {operation_text} original image...")
        logger.info("uploading_original_image", filename=filename, is_overwrite=is_overwrite)
        original_upload_result = storage_service.upload_original_photo(user_info.user_id, file_data, filename)
        original_gcs_path = original_upload_result["gcs_path"]

        # Step 4: Upload thumbnail to GCS
        update_progress(f"🔄 {operation_text} thumbnail...")
        logger.info("uploading_thumbnail", filename=filename, is_overwrite=is_overwrite)
        thumbnail_upload_result = storage_service.upload_thumbnail(user_info.user_id, thumbnail_data, filename)
        thumbnail_gcs_path = thumbnail_upload_result["gcs_path"]

        # Step 5: Save or update metadata in DuckDB
        metadata_text = "Updating" if is_overwrite else "Saving"
        update_progress(f"💾 {metadata_text} metadata...")
        logger.info("saving_metadata", filename=filename, is_overwrite=is_overwrite)

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
            created_at=created_at,
            uploaded_at=datetime.now(),
        )

        # Use the new save_or_update method based on operation type
        metadata_service.save_or_update_photo_metadata(photo_metadata, is_overwrite=is_overwrite)

        completion_text = "✅ Overwrite completed!" if is_overwrite else "✅ Upload completed!"
        update_progress(completion_text, "success")
        logger.info("upload_processing_completed", filename=filename, operation_type=operation_type)

        operation_message = "overwritten" if is_overwrite else "uploaded"
        processing_steps = [
            "Authentication verified",
            "EXIF metadata extracted",
            "Thumbnail generated",
            f"Original image {'overwritten' if is_overwrite else 'uploaded'} to GCS",
            f"Thumbnail {'overwritten' if is_overwrite else 'uploaded'} to GCS",
            f"Metadata {'updated' if is_overwrite else 'saved'} in database",
        ]

        return {
            "success": True,
            "filename": filename,
            "original_path": original_gcs_path,
            "thumbnail_path": thumbnail_gcs_path,
            "created_at": created_at,
            "file_size": len(file_data),
            "is_overwrite": is_overwrite,
            "processing_steps": processing_steps,
            "message": f"Successfully {operation_message} {filename}",
        }

    except Exception as e:
        operation_type = "overwrite" if is_overwrite else "upload"
        update_progress(f"❌ Error: {str(e)}", "error")
        logger.error("upload_processing_failed", filename=filename, error=str(e), operation_type=operation_type)
        return {
            "success": False,
            "filename": filename,
            "error": str(e),
            "error_type": type(e).__name__,
            "is_overwrite": is_overwrite,
            "message": f"Failed to {operation_type} {filename}: {str(e)}",
        }


def clear_upload_session_state() -> None:
    """Clear upload-related session state variables."""
    session_keys_to_clear = [
        "valid_files",
        "validation_errors",
        "upload_validated",
        "upload_in_progress",
        "upload_results",
        "last_upload_result",
        "upload_progress",
    ]

    # Clear specific keys
    for key in session_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

    # Clear collision decision keys (pattern-based)
    for key in list(st.session_state.keys()):  # type: ignore
        if isinstance(key, str) and (key.startswith("collision_decision_") or key.startswith("decision_start_")):
            del st.session_state[key]


def _get_collision_detection_error_message(error: Exception) -> str:
    """
    Generate user-friendly error message for collision detection failures.

    Args:
        error: The exception that occurred

    Returns:
        str: User-friendly error message
    """
    error_str = str(error)

    if "timeout" in error_str.lower():
        return "データベースへの接続がタイムアウトしました。ネットワーク接続を確認してください。"
    elif "connection" in error_str.lower():
        return "データベースに接続できませんでした。しばらく待ってから再試行してください。"
    elif "permission" in error_str.lower() or "access" in error_str.lower():
        return "データベースへのアクセス権限に問題があります。管理者にお問い合わせください。"
    elif "high failure rate" in error_str.lower():
        return "多数のファイルで衝突検出に失敗しました。システムに一時的な問題が発生している可能性があります。"
    elif isinstance(error, CollisionDetectionRecoveryError):
        return "衝突検出の復旧に失敗しました。システムが一時的に不安定な状態です。"
    else:
        return f"衝突検出中にエラーが発生しました: {error_str[:100]}{'...' if len(error_str) > 100 else ''}"


def collect_user_collision_decisions(collision_results: dict, user_id: str) -> dict:
    """
    Collect and monitor user decisions for collision handling.

    Args:
        collision_results: Dictionary mapping filename to collision info
        user_id: ID of the user making decisions

    Returns:
        dict: Updated collision results with user decisions and monitoring
    """
    import time

    updated_results = {}

    for filename, collision_info in collision_results.items():
        decision_key = f"collision_decision_{filename}"

        # Get current decision from session state
        current_decision = st.session_state.get(decision_key, "pending")

        # Record decision start time if not already recorded
        decision_start_key = f"decision_start_{filename}"
        if decision_start_key not in st.session_state:
            st.session_state[decision_start_key] = time.perf_counter()

        # Update collision info with current decision
        updated_collision_info = collision_info.copy()
        updated_collision_info["user_decision"] = current_decision
        updated_results[filename] = updated_collision_info

    return updated_results


def get_collision_decision_statistics(user_id: str) -> dict:
    """
    Get collision decision statistics for a user.

    Args:
        user_id: ID of the user

    Returns:
        dict: Statistics about collision decisions
    """
    # Monitoring functionality removed for personal development use
    return {
        "total_decisions": 0,
        "overwrite_decisions": 0,
        "skip_decisions": 0,
        "average_decision_time": 0.0,
        "user_id": user_id,
    }
