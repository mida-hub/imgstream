"""Upload handlers for imgstream application."""

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


def get_file_size_limits() -> tuple[int, int]:
    """
    Get current file size limits from ImageProcessor.

    Returns:
        tuple: (min_size, max_size) in bytes
    """
    image_processor = ImageProcessor()
    return image_processor.MIN_FILE_SIZE, image_processor.MAX_FILE_SIZE


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

    # Process each file
    for _index, file_info in enumerate(valid_files):
        filename = file_info["filename"]

        try:
            # Check for collision decision
            collision_info = collision_results.get(filename) if collision_results else None
            user_decision = collision_info.get("user_decision", "upload") if collision_info else "upload"

            if user_decision == "skip":
                # User chose to skip this file
                result = {
                    "success": True,
                    "filename": filename,
                    "skipped": True,
                    "message": f"ユーザーの選択により {filename} をスキップしました",
                }
                results.append(result)
                skipped_uploads += 1
                continue

            # Determine if this is an overwrite operation
            is_overwrite = collision_info is not None and user_decision == "overwrite"

            # Process the file (simplified version)
            result = process_single_upload(file_info, is_overwrite)

            if result["success"]:
                if is_overwrite:
                    overwrite_uploads += 1
                successful_uploads += 1
            else:
                failed_uploads += 1

            results.append(result)

        except Exception as e:
            logger.error("batch_upload_error", filename=filename, error=str(e))
            result = {
                "success": False,
                "filename": filename,
                "error": str(e),
                "message": f"アップロード中にエラーが発生しました: {filename}",
            }
            results.append(result)
            failed_uploads += 1

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


def process_single_upload(file_info: dict[str, Any], is_overwrite: bool = False) -> dict[str, Any]:
    """
    Process a single file upload (simplified version).

    Args:
        file_info: File information dictionary
        is_overwrite: Whether this is an overwrite operation

    Returns:
        dict: Upload result
    """
    filename = file_info["filename"]

    try:
        # Get services
        auth_service = get_auth_service()
        user_id = auth_service.get_current_user_id()

        if not user_id:
            return {
                "success": False,
                "filename": filename,
                "error": "User not authenticated",
                "message": f"認証が必要です: {filename}",
            }

        storage_service = get_storage_service()
        metadata_service = get_metadata_service()
        image_processor = ImageProcessor()

        # Process the image
        file_data = file_info["data"]
        processed_result = image_processor.process_image(file_data, filename)

        # Create photo metadata
        photo_metadata = PhotoMetadata(
            filename=filename,
            user_id=user_id,
            file_size=len(file_data),
            mime_type=processed_result.get("mime_type", "image/jpeg"),
            created_at=processed_result.get("creation_date"),
            camera_make=processed_result.get("camera_make"),
            camera_model=processed_result.get("camera_model"),
            gps_latitude=processed_result.get("gps_latitude"),
            gps_longitude=processed_result.get("gps_longitude"),
        )

        # Upload to storage
        storage_path = storage_service.upload_photo(file_data, filename, user_id)
        photo_metadata.storage_path = storage_path

        # Save metadata
        if is_overwrite:
            metadata_service.update_photo_metadata(photo_metadata)
        else:
            metadata_service.save_photo_metadata(photo_metadata)

        return {
            "success": True,
            "filename": filename,
            "file_size": len(file_data),
            "creation_date": processed_result.get("creation_date"),
            "storage_path": storage_path,
            "is_overwrite": is_overwrite,
            "message": f"正常にアップロードしました: {filename}",
        }

    except Exception as e:
        logger.error("single_upload_error", filename=filename, error=str(e))
        return {
            "success": False,
            "filename": filename,
            "error": str(e),
            "message": f"アップロードに失敗しました: {filename}",
        }


def validate_uploaded_files_with_collision_check(uploaded_files: list) -> tuple[list, list, dict]:
    """
    Validate uploaded files for format, size, and filename collisions.

    Args:
        uploaded_files: List of uploaded file objects from Streamlit

    Returns:
        tuple: (valid_files, validation_errors, collision_results)
    """
    # First perform standard validation
    valid_files, validation_errors = validate_uploaded_files(uploaded_files)

    if not valid_files:
        return valid_files, validation_errors, {}

    # Get current user
    auth_service = get_auth_service()
    user_id = auth_service.get_current_user_id()

    if not user_id:
        validation_errors.append(
            {
                "filename": "authentication",
                "error": "User not authenticated",
                "details": "Please log in to upload files",
            }
        )
        return valid_files, validation_errors, {}

    # Check for filename collisions
    try:
        filenames = [file_info["filename"] for file_info in valid_files]
        collision_results = check_filename_collisions_optimized(filenames, user_id)
        return valid_files, validation_errors, collision_results

    except CollisionDetectionError as e:
        logger.error("collision_detection_error", error=str(e), user_id=user_id)

        # Try fallback collision detection
        try:
            collision_results = check_filename_collisions_with_fallback(filenames, user_id)
            logger.info("collision_detection_fallback_success", user_id=user_id, file_count=len(filenames))
            return valid_files, validation_errors, collision_results

        except (CollisionDetectionError, CollisionDetectionRecoveryError) as fallback_error:
            logger.error("collision_detection_fallback_failed", error=str(fallback_error), user_id=user_id)

            # Add collision detection error to validation errors
            validation_errors.append(
                {
                    "filename": "collision_detection",
                    "error": _get_collision_detection_error_message(fallback_error),
                    "error_type": "CollisionDetectionError",
                    "recovery_message": "衝突検出に失敗しましたが、アップロードは続行できます。",
                    "recovery_options": [
                        "アップロードを続行する（注意が必要）",
                        "ページを再読み込みして再試行する",
                        "ファイルを個別にアップロードする",
                    ],
                }
            )
            return valid_files, validation_errors, {}


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
