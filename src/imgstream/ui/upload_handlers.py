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
from imgstream.utils.collision_detection import (
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


def render_file_validation_results_with_collisions(
    valid_files: list, validation_errors: list, collision_results: dict
) -> None:
    """
    Render the results of file validation including collision information.

    Args:
        valid_files: List of valid file objects
        validation_errors: List of validation error objects
        collision_results: Dictionary mapping filename to collision info
    """
    # First show standard validation results
    render_file_validation_results(valid_files, validation_errors)

    # Show enhanced error messages for collision-related errors
    collision_errors = [error for error in validation_errors if "衝突" in error.get("error", "")]
    if collision_errors:
        render_collision_error_messages(collision_errors)

    # Then show collision information if any
    if collision_results:
        # Check if any collisions are in fallback mode
        fallback_collisions = [
            filename for filename, info in collision_results.items() if info.get("fallback_mode", False)
        ]

        if fallback_collisions:
            st.warning(f"⚠️ {len(collision_results)} file(s) have filename conflicts (安全モードで検出)")
            st.info(
                "🛡️ **安全モード:** 衝突検出システムに問題が発生したため、安全のためすべてのファイルで"
                "既存ファイルの確認を求めています。実際には衝突していない可能性もあります。"
            )
        else:
            st.warning(f"⚠️ {len(collision_results)} file(s) have filename conflicts")

        with st.expander("🔄 Filename Conflicts", expanded=True):
            st.markdown("以下のファイルは既に存在します。上書きするかスキップするかを選択してください。")

            for filename, collision_info in collision_results.items():
                existing_file_info = collision_info["existing_file_info"]

                # Create a container for each collision
                with st.container():
                    st.markdown(f"**📷 {filename}**")

                    # Show fallback warning if applicable
                    if collision_info.get("fallback_mode", False):
                        st.warning(f"⚠️ {collision_info.get('warning_message', '安全モードで検出されました')}")

                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.markdown("**既存ファイル情報:**")
                        if not collision_info.get("fallback_mode", False):
                            st.write(
                                f"• アップロード日時: {existing_file_info['upload_date'].strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                            st.write(f"• ファイルサイズ: {format_file_size(existing_file_info['file_size'])}")
                            if existing_file_info["creation_date"]:
                                st.write(
                                    f"• 作成日時: {existing_file_info['creation_date'].strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                        else:
                            st.write("• 詳細情報: 安全モードのため取得できません")
                            st.write("• 推奨: 上書きを選択する前に既存ファイルを確認してください")

                    with col2:
                        # User decision selection
                        decision_key = f"collision_decision_{filename}"
                        current_decision = collision_info.get("user_decision", "pending")

                        if current_decision == "pending":
                            st.selectbox(
                                "選択してください:",
                                options=["pending", "overwrite", "skip"],
                                format_func=lambda x: {
                                    "pending": "決定待ち",
                                    "overwrite": "上書きする",
                                    "skip": "スキップする",
                                }[x],
                                key=decision_key,
                                index=0,
                            )
                        else:
                            # Show current decision
                            decision_text = {"overwrite": "✅ 上書きする", "skip": "❌ スキップする"}.get(
                                current_decision, "決定待ち"
                            )
                            st.write(f"**決定:** {decision_text}")

                    st.divider()

    elif valid_files:
        # Show positive message when no collisions
        st.info("✅ ファイル名の衝突は検出されませんでした。すべてのファイルを安全にアップロードできます。")


def render_collision_error_messages(collision_errors: list) -> None:
    """
    Render enhanced error messages for collision-related errors.

    Args:
        collision_errors: List of collision-related error objects
    """
    for error in collision_errors:
        error_type = error.get("error", "")

        if "フォールバック" in error_type:
            st.warning("🛡️ **安全モード有効**")
            st.info(error["details"])
        elif "失敗" in error_type:
            st.error("❌ **衝突検出エラー**")
            st.error(error["details"])

            # Show recovery options if available
            if "recovery_options" in error:
                st.markdown("**復旧オプション:**")
                for option in error["recovery_options"]:
                    st.write(f"• {option}")
        else:
            st.warning("⚠️ **衝突検出警告**")
            st.warning(error["details"])


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
            creation_date = image_processor.extract_creation_date(file_data)
        except Exception as e:
            logger.warning("exif_extraction_failed", filename=filename, error=str(e))
            # Use current time as fallback
            creation_date = datetime.now()

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
            created_at=creation_date,
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
            "creation_date": creation_date,
            "is_overwrite": is_overwrite,
            "message": f"Successfully {operation_message} {filename}",
        }

    except Exception as e:
        operation_type = "overwrite" if is_overwrite else "upload"
        logger.error("upload_processing_failed", filename=filename, error=str(e), operation_type=operation_type)
        return {
            "success": False,
            "filename": filename,
            "error": str(e),
            "is_overwrite": is_overwrite,
            "message": f"Failed to {operation_type} {filename}: {str(e)}",
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
            created_at=creation_date,
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
            "creation_date": creation_date,
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


def _render_overall_status(batch_result: dict[str, Any]) -> None:
    """Render the overall status message for batch upload results."""
    total_files = batch_result["total_files"]
    successful_uploads = batch_result["successful_uploads"]
    failed_uploads = batch_result["failed_uploads"]
    skipped_uploads = batch_result.get("skipped_uploads", 0)
    overwrite_uploads = batch_result.get("overwrite_uploads", 0)

    if batch_result["success"]:
        if total_files == 1:
            if overwrite_uploads > 0:
                st.success("🎉 Successfully overwritten 1 photo!")
            elif skipped_uploads > 0:
                st.info("⏭️ 1 photo was skipped as requested")
            else:
                st.success("🎉 Successfully uploaded 1 photo!")
        else:
            success_parts = []
            if successful_uploads - overwrite_uploads > 0:
                success_parts.append(f"{successful_uploads - overwrite_uploads} uploaded")
            if overwrite_uploads > 0:
                success_parts.append(f"{overwrite_uploads} overwritten")
            if skipped_uploads > 0:
                success_parts.append(f"{skipped_uploads} skipped")

            if success_parts:
                st.success(f"🎉 Successfully processed all {total_files} photos: {', '.join(success_parts)}")
            else:
                st.success(f"🎉 Successfully processed all {total_files} photos!")
    elif successful_uploads > 0 or skipped_uploads > 0:
        status_parts = []
        if successful_uploads > 0:
            if overwrite_uploads > 0:
                status_parts.append(f"{successful_uploads} successful ({overwrite_uploads} overwrites)")
            else:
                status_parts.append(f"{successful_uploads} successful")
        if skipped_uploads > 0:
            status_parts.append(f"{skipped_uploads} skipped")
        if failed_uploads > 0:
            status_parts.append(f"{failed_uploads} failed")

        st.warning(f"⚠️ Partial success: {', '.join(status_parts)}")
    else:
        st.error(f"❌ Upload failed: All {failed_uploads} files encountered errors")


def _render_summary_metrics(batch_result: dict[str, Any], processing_time: float | None = None) -> None:
    """Render summary metrics for batch upload results."""
    total_files = batch_result["total_files"]
    successful_uploads = batch_result["successful_uploads"]
    failed_uploads = batch_result["failed_uploads"]
    skipped_uploads = batch_result.get("skipped_uploads", 0)
    overwrite_uploads = batch_result.get("overwrite_uploads", 0)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Files", total_files)
    with col2:
        st.metric("Successful", successful_uploads, delta=successful_uploads if successful_uploads > 0 else None)
    with col3:
        if overwrite_uploads > 0:
            st.metric("Overwrites", overwrite_uploads, delta=overwrite_uploads)
        else:
            st.metric("Failed", failed_uploads, delta=-failed_uploads if failed_uploads > 0 else None)
    with col4:
        if skipped_uploads > 0:
            st.metric("Skipped", skipped_uploads)
        elif processing_time:
            st.metric("Processing Time", f"{processing_time:.1f}s")
        else:
            success_rate = (successful_uploads / total_files * 100) if total_files > 0 else 0
            st.metric("Success Rate", f"{success_rate:.1f}%")
    with col5:
        if processing_time and (overwrite_uploads > 0 or skipped_uploads > 0):
            st.metric("Processing Time", f"{processing_time:.1f}s")
        elif failed_uploads > 0 and not (overwrite_uploads > 0 or skipped_uploads > 0):
            st.metric("Failed", failed_uploads, delta=-failed_uploads)


def _render_new_uploads(new_upload_results: list[dict[str, Any]]) -> None:
    """Render new upload results."""
    if not new_upload_results:
        return

    with st.expander(f"✅ New Uploads ({len(new_upload_results)})", expanded=len(new_upload_results) <= 3):
        for result in new_upload_results:
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
                st.markdown("✅ **New Upload**")


def _render_overwrites(overwrite_results: list[dict[str, Any]]) -> None:
    """Render overwrite results."""
    if not overwrite_results:
        return

    with st.expander(f"🔄 Overwrites ({len(overwrite_results)})", expanded=len(overwrite_results) <= 3):
        st.markdown("**以下のファイルは既存の写真を上書きしました:**")
        st.divider()

        for result in overwrite_results:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.info(f"📷 **{result['filename']}**")

                # Show new file information
                st.markdown("**新しいファイル情報:**")
                if "creation_date" in result:
                    st.write(f"   📅 撮影日時: {result['creation_date'].strftime('%Y-%m-%d %H:%M:%S')}")
                if "file_size" in result:
                    file_size_mb = result["file_size"] / (1024 * 1024)
                    st.write(f"   💾 ファイルサイズ: {file_size_mb:.1f} MB")

                # Show overwrite confirmation
                st.success("   ✅ **上書き完了 - 既存の写真が新しいバージョンに置き換えられました**")

                # Show what was preserved
                st.markdown("**保持された情報:**")
                st.write("   🔒 元の作成日時とファイルIDは保持されています")
                st.write("   📊 メタデータは新しいファイルの情報に更新されました")

                if "processing_steps" in result:
                    with st.expander(f"上書き処理ステップ: {result['filename']}", expanded=False):
                        for step in result["processing_steps"]:
                            st.write(f"• {step}")
            with col2:
                st.markdown("🔄 **上書き完了**")
                st.markdown("---")
                st.markdown("**操作結果:**")
                st.write("✅ 成功")
                st.write("🔄 既存ファイル更新")
                st.write("🔒 ID・作成日保持")


def _render_skipped_files(skipped_results: list[dict[str, Any]]) -> None:
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


def _render_failed_uploads(failed_results: list[dict[str, Any]]) -> None:
    """Render failed upload results."""
    if not failed_results:
        return

    with st.expander(f"❌ 失敗したアップロード ({len(failed_results)})", expanded=True):
        # Separate overwrite failures from regular failures
        overwrite_failures = [r for r in failed_results if r.get("is_overwrite", False)]
        regular_failures = [r for r in failed_results if not r.get("is_overwrite", False)]

        # Show overwrite-specific failures first
        if overwrite_failures:
            _render_overwrite_failures(overwrite_failures)

        # Show regular failures
        if regular_failures:
            _render_regular_failures(regular_failures, bool(overwrite_failures))


def _render_overwrite_failures(overwrite_failures: list[dict[str, Any]]) -> None:
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


def _render_regular_failures(regular_failures: list[dict[str, Any]], has_overwrite_failures: bool) -> None:
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


def _render_detailed_results(batch_result: dict[str, Any]) -> None:
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
    _render_new_uploads(new_upload_results)
    _render_overwrites(overwrite_results)
    _render_skipped_files(skipped_results)
    _render_failed_uploads(failed_results)


def _render_processing_summary(batch_result: dict[str, Any]) -> None:
    """Render processing summary for mixed operations."""
    overwrite_uploads = batch_result.get("overwrite_uploads", 0)
    skipped_uploads = batch_result.get("skipped_uploads", 0)
    failed_uploads = batch_result["failed_uploads"]
    successful_uploads = batch_result["successful_uploads"]

    if overwrite_uploads > 0 or skipped_uploads > 0:
        st.markdown("### 📊 処理サマリー")

        # Create summary cards
        summary_cols = st.columns(4)

        with summary_cols[0]:
            new_uploads = successful_uploads - overwrite_uploads
            if new_uploads > 0:
                st.metric(label="🆕 新規アップロード", value=new_uploads, help="新しく追加された写真の数")

        with summary_cols[1]:
            if overwrite_uploads > 0:
                st.metric(label="🔄 上書き更新", value=overwrite_uploads, help="既存の写真を更新した数")

        with summary_cols[2]:
            if skipped_uploads > 0:
                st.metric(label="⏭️ スキップ", value=skipped_uploads, help="ユーザー選択によりスキップされた数")

        with summary_cols[3]:
            if failed_uploads > 0:
                st.metric(
                    label="❌ 失敗", value=failed_uploads, delta=-failed_uploads, help="処理に失敗したファイルの数"
                )

        # Show operation impact summary
        if overwrite_uploads > 0:
            st.info(
                f"🔄 **上書き操作について:** {overwrite_uploads}個のファイルが既存の写真を更新しました。"
                "元の作成日時とファイルIDは保持され、メタデータのみが更新されています。"
            )

        if skipped_uploads > 0:
            st.warning(
                f"⏭️ **スキップされたファイル:** {skipped_uploads}個のファイルがスキップされました。"
                "これらのファイルは処理されておらず、既存のファイルも変更されていません。"
            )


def _render_next_steps(batch_result: dict[str, Any]) -> None:
    """Render next steps section."""
    successful_uploads = batch_result["successful_uploads"]
    failed_uploads = batch_result["failed_uploads"]

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


    elif failed_uploads > 0:
        st.markdown("### 🔧 Need Help?")
        st.info(
            "If you continue to experience upload issues, please check your internet connection and file formats. "
            "Supported formats: HEIC, HEIF, JPG, JPEG"
        )

        if st.button("🔄 Try Again", use_container_width=True, type="primary"):
            st.rerun()


def render_upload_results(batch_result: dict[str, Any], processing_time: float | None = None) -> None:
    """
    Render enhanced results of batch upload processing with detailed feedback.

    Args:
        batch_result: Dictionary containing batch processing results
        processing_time: Total processing time in seconds
    """
    # Render overall status
    _render_overall_status(batch_result)

    # Render summary metrics
    _render_summary_metrics(batch_result, processing_time)

    # Render detailed results
    _render_detailed_results(batch_result)

    # Enhanced processing summary for mixed operations
    st.divider()
    _render_processing_summary(batch_result)

    # Render next steps
    _render_next_steps(batch_result)

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


def handle_overwrite_operation_error(error: Exception, filename: str, operation: str) -> dict[str, Any]:
    """
    Handle errors that occur during overwrite operations with appropriate recovery.

    Args:
        error: The exception that occurred
        filename: Name of the file being processed
        operation: Type of operation (e.g., "metadata_update", "file_upload")

    Returns:
        dict: Error result with recovery information
    """
    from imgstream.services.metadata import MetadataError

    error_type = type(error).__name__
    error_str = str(error)

    # Determine error category and recovery options
    if isinstance(error, MetadataError):
        if "not found" in error_str.lower():
            recovery_message = "対象のファイルが見つかりません。ファイルが削除されている可能性があります。"
            recovery_options = ["新規アップロードとして再試行する", "ファイルリストを更新して確認する"]
        elif "permission" in error_str.lower() or "access" in error_str.lower():
            recovery_message = "ファイルへのアクセス権限がありません。"
            recovery_options = ["管理者に権限の確認を依頼する", "別のファイル名で新規アップロードする"]
        elif "database" in error_str.lower():
            recovery_message = "データベースの更新に失敗しました。"
            recovery_options = ["しばらく待ってから再試行する", "ページを再読み込みして再試行する"]
        else:
            recovery_message = f"メタデータの更新に失敗しました: {error_str}"
            recovery_options = ["再試行する", "新規アップロードとして処理する"]
    elif "StorageError" in error_type or "StorageError" in error_str:
        recovery_message = "ファイルのアップロードに失敗しました。"
        recovery_options = [
            "ネットワーク接続を確認して再試行する",
            "ファイルサイズを確認する",
            "しばらく待ってから再試行する",
        ]
    else:
        recovery_message = f"上書き操作中に予期しないエラーが発生しました: {error_str}"
        recovery_options = ["再試行する", "新規アップロードとして処理する", "管理者に問い合わせる"]

    return {
        "success": False,
        "filename": filename,
        "error": error_str,
        "error_type": error_type,
        "operation": operation,
        "is_overwrite": True,
        "recovery_message": recovery_message,
        "recovery_options": recovery_options,
        "message": f"Failed to {operation} {filename}: {recovery_message}",
    }


def handle_collision_decision_monitoring(
    user_id: str, filename: str, decision: str, decision_start_time: float | None = None, **collision_context
) -> None:
    """
    Handle monitoring of user collision decisions.

    Args:
        user_id: ID of the user making the decision
        filename: Name of the file with collision
        decision: User's decision ('overwrite', 'skip', 'pending')
        decision_start_time: When the decision process started (for timing)
        **collision_context: Additional context about the collision
    """
    # Monitoring functionality removed for personal development use
    # Calculate decision time if start time provided would be here
    # Log the user decision would be here
    pass


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
    import streamlit as st

    updated_results = {}

    for filename, collision_info in collision_results.items():
        decision_key = f"collision_decision_{filename}"

        # Get current decision from session state
        current_decision = st.session_state.get(decision_key, "pending")

        # Check if decision changed from previous state
        previous_decision = collision_info.get("user_decision", "pending")

        # Record decision start time if not already recorded
        decision_start_key = f"decision_start_{filename}"
        if decision_start_key not in st.session_state:
            st.session_state[decision_start_key] = time.perf_counter()

        decision_start_time = st.session_state[decision_start_key]

        # If decision changed, log it
        if current_decision != previous_decision and current_decision != "pending":
            handle_collision_decision_monitoring(
                user_id=user_id,
                filename=filename,
                decision=current_decision,
                decision_start_time=decision_start_time,
                existing_photo_id=collision_info.get("existing_photo", {}).get("id"),
                fallback_mode=collision_info.get("fallback_mode", False),
                file_size=collision_info.get("existing_file_info", {}).get("file_size"),
                upload_date=collision_info.get("existing_file_info", {}).get("upload_date"),
            )

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
        dict: Statistics about user's collision decisions
    """
    # Monitoring functionality removed for personal development use
    return {"pattern": "unknown", "statistics": {}}


def render_collision_decision_help() -> None:
    """Render help information for collision decisions."""
    with st.expander("❓ 衝突処理について", expanded=False):
        st.markdown(
            """
        ### 📋 衝突処理オプション

        **🔄 上書きする:**
        - 既存のファイルを新しいファイルで置き換えます
        - 元の作成日時とファイルIDは保持されます
        - メタデータ（ファイルサイズ、撮影日時など）は新しいファイルの情報に更新されます

        **⏭️ スキップする:**
        - 既存のファイルをそのまま保持します
        - 新しいファイルはアップロードされません
        - 後でファイル名を変更してアップロードすることができます

        ### 💡 推奨事項
        - 同じ写真の高画質版がある場合は「上書き」を選択
        - 異なる写真の場合は「スキップ」を選択してファイル名を変更
        - 不明な場合は既存ファイルの詳細を確認してから決定
        """
        )


def monitor_batch_collision_processing(
    user_id: str, filenames: list, collision_results: dict, processing_time_ms: float
) -> None:
    """
    Monitor batch collision processing metrics.

    Args:
        user_id: ID of the user
        filenames: List of filenames processed
        collision_results: Results of collision detection
        processing_time_ms: Time taken for processing
    """
    # Monitoring functionality removed for personal development use
    pass
