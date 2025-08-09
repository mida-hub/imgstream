"""Tests for comprehensive error handling functionality."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import time

from src.imgstream.utils.collision_detection import (
    check_filename_collisions_with_retry,
    check_filename_collisions_with_fallback,
    CollisionDetectionError,
    CollisionDetectionRecoveryError,
    _create_fallback_collision_results,
)
from src.imgstream.services.metadata import MetadataService, MetadataError
from src.imgstream.ui.upload_handlers import (
    _get_collision_detection_error_message,
    handle_overwrite_operation_error,
    clear_upload_session_state,
)


class TestCollisionDetectionErrorHandling:
    """Test error handling in collision detection."""

    @pytest.fixture
    def sample_filenames(self):
        """Create sample filenames for testing."""
        return ["photo1.jpg", "photo2.jpg", "photo3.jpg"]

    @patch("src.imgstream.utils.collision_detection.check_filename_collisions")
    def test_collision_detection_with_retry_success_first_attempt(self, mock_check, sample_filenames):
        """Test successful collision detection on first attempt."""
        expected_result = {"photo1.jpg": {"collision": True}}
        mock_check.return_value = expected_result

        result = check_filename_collisions_with_retry("user123", sample_filenames)

        assert result == expected_result
        assert mock_check.call_count == 1

    @patch("src.imgstream.utils.collision_detection.check_filename_collisions")
    @patch("src.imgstream.utils.collision_detection.time.sleep")
    def test_collision_detection_with_retry_success_after_retry(self, mock_sleep, mock_check, sample_filenames):
        """Test successful collision detection after retry."""
        expected_result = {"photo1.jpg": {"collision": True}}
        mock_check.side_effect = [
            CollisionDetectionError("First attempt failed"),
            expected_result
        ]

        result = check_filename_collisions_with_retry("user123", sample_filenames, max_retries=2)

        assert result == expected_result
        assert mock_check.call_count == 2
        # The sleep is called with exponential backoff, so it should be 2.0 on the second attempt
        mock_sleep.assert_called_once_with(2.0)

    @patch("src.imgstream.utils.collision_detection.check_filename_collisions")
    @patch("src.imgstream.utils.collision_detection.time.sleep")
    def test_collision_detection_with_retry_all_attempts_fail(self, mock_sleep, mock_check, sample_filenames):
        """Test collision detection failure after all retry attempts."""
        mock_check.side_effect = CollisionDetectionError("Persistent failure")

        with pytest.raises(CollisionDetectionRecoveryError):
            check_filename_collisions_with_retry("user123", sample_filenames, max_retries=2)

        assert mock_check.call_count == 3  # Initial + 2 retries
        assert mock_sleep.call_count == 2

    @patch("src.imgstream.utils.collision_detection.check_filename_collisions_with_retry")
    def test_collision_detection_with_fallback_success(self, mock_retry, sample_filenames):
        """Test successful collision detection without fallback."""
        expected_result = {"photo1.jpg": {"collision": True}}
        mock_retry.return_value = expected_result

        result, fallback_used = check_filename_collisions_with_fallback("user123", sample_filenames)

        assert result == expected_result
        assert fallback_used is False

    @patch("src.imgstream.utils.collision_detection.check_filename_collisions_with_retry")
    def test_collision_detection_with_fallback_used(self, mock_retry, sample_filenames):
        """Test collision detection with fallback mode."""
        mock_retry.side_effect = CollisionDetectionRecoveryError("All retries failed")

        result, fallback_used = check_filename_collisions_with_fallback("user123", sample_filenames)

        assert fallback_used is True
        assert len(result) == len(sample_filenames)
        for filename in sample_filenames:
            assert filename in result
            assert result[filename]["fallback_mode"] is True

    @patch("src.imgstream.utils.collision_detection.check_filename_collisions_with_retry")
    def test_collision_detection_with_fallback_disabled(self, mock_retry, sample_filenames):
        """Test collision detection with fallback disabled."""
        mock_retry.side_effect = CollisionDetectionRecoveryError("All retries failed")

        with pytest.raises(CollisionDetectionRecoveryError):
            check_filename_collisions_with_fallback("user123", sample_filenames, enable_fallback=False)

    def test_create_fallback_collision_results(self, sample_filenames):
        """Test creation of fallback collision results."""
        result = _create_fallback_collision_results("user123", sample_filenames)

        assert len(result) == len(sample_filenames)
        for filename in sample_filenames:
            assert filename in result
            assert result[filename]["collision_detected"] is True
            assert result[filename]["fallback_mode"] is True
            assert "warning_message" in result[filename]


class TestMetadataServiceErrorHandling:
    """Test error handling in MetadataService."""

    @pytest.fixture
    def metadata_service(self):
        """Create a MetadataService instance for testing."""
        with patch('src.imgstream.services.metadata.get_storage_service'):
            service = MetadataService("test_user_123", "/tmp/test")
            # Mock database manager
            mock_db_manager = MagicMock()
            mock_db_manager.__enter__ = Mock(return_value=mock_db_manager)
            mock_db_manager.__exit__ = Mock(return_value=None)
            service._db_manager = mock_db_manager
            service.ensure_local_database = Mock()
            service.upload_to_gcs = Mock()
            return service

    @pytest.fixture
    def sample_photo_metadata(self):
        """Create sample PhotoMetadata for testing."""
        from src.imgstream.models.photo import PhotoMetadata
        return PhotoMetadata(
            id="photo_123",
            user_id="test_user_123",
            filename="test_photo.jpg",
            original_path="photos/test_user_123/original/test_photo.jpg",
            thumbnail_path="photos/test_user_123/thumbs/test_photo_thumb.jpg",
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            uploaded_at=datetime(2024, 1, 16, 14, 0, 0),
            file_size=2048000,
            mime_type="image/jpeg"
        )

    def test_save_or_update_photo_metadata_with_fallback_success(self, metadata_service, sample_photo_metadata):
        """Test successful save/update without fallback."""
        metadata_service.save_or_update_photo_metadata = Mock()

        result = metadata_service.save_or_update_photo_metadata_with_fallback(
            sample_photo_metadata, is_overwrite=True
        )

        assert result["success"] is True
        assert result["fallback_used"] is False
        assert result["operation"] == "overwrite"

    def test_save_or_update_photo_metadata_with_fallback_used(self, metadata_service, sample_photo_metadata):
        """Test fallback when overwrite fails."""
        # Mock the primary operation to fail
        metadata_service.save_or_update_photo_metadata = Mock(
            side_effect=MetadataError("Update failed")
        )
        # Mock the fallback to succeed
        metadata_service._attempt_overwrite_fallback = Mock(return_value={
            "success": True,
            "operation": "fallback_save",
            "filename": "test_photo.jpg",
            "fallback_filename": "test_photo_overwrite_20240116.jpg",
            "fallback_used": True,
            "strategy": "timestamp_suffix",
        })

        result = metadata_service.save_or_update_photo_metadata_with_fallback(
            sample_photo_metadata, is_overwrite=True
        )

        assert result["success"] is True
        assert result["fallback_used"] is True
        assert result["strategy"] == "timestamp_suffix"

    def test_save_or_update_photo_metadata_with_fallback_disabled(self, metadata_service, sample_photo_metadata):
        """Test behavior when fallback is disabled."""
        metadata_service.save_or_update_photo_metadata = Mock(
            side_effect=MetadataError("Update failed")
        )

        with pytest.raises(MetadataError):
            metadata_service.save_or_update_photo_metadata_with_fallback(
                sample_photo_metadata, is_overwrite=True, enable_fallback=False
            )

    def test_attempt_overwrite_fallback_timestamp_strategy(self, metadata_service, sample_photo_metadata):
        """Test fallback with timestamp strategy."""
        metadata_service.save_photo_metadata = Mock()

        result = metadata_service._attempt_overwrite_fallback(
            sample_photo_metadata, MetadataError("Original error")
        )

        assert result["success"] is True
        assert result["strategy"] == "timestamp_suffix"
        assert "overwrite_" in result["fallback_filename"]
        assert result["fallback_filename"].endswith(".jpg")

    def test_attempt_overwrite_fallback_uuid_strategy(self, metadata_service, sample_photo_metadata):
        """Test fallback with UUID strategy when timestamp fails."""
        # Mock timestamp strategy to fail, UUID to succeed
        metadata_service.save_photo_metadata = Mock(side_effect=[
            MetadataError("Timestamp strategy failed"),
            None  # UUID strategy succeeds
        ])

        result = metadata_service._attempt_overwrite_fallback(
            sample_photo_metadata, MetadataError("Original error")
        )

        assert result["success"] is True
        assert result["strategy"] == "uuid_suffix"
        assert "overwrite_" in result["fallback_filename"]

    def test_attempt_overwrite_fallback_all_strategies_fail(self, metadata_service, sample_photo_metadata):
        """Test fallback when all strategies fail."""
        metadata_service.save_photo_metadata = Mock(side_effect=MetadataError("All strategies failed"))

        with pytest.raises(MetadataError, match="All fallback strategies failed"):
            metadata_service._attempt_overwrite_fallback(
                sample_photo_metadata, MetadataError("Original error")
            )


class TestUploadHandlerErrorHandling:
    """Test error handling in upload handlers."""

    def test_get_collision_detection_error_message_timeout(self):
        """Test error message generation for timeout errors."""
        error = CollisionDetectionError("Connection timeout occurred")
        message = _get_collision_detection_error_message(error)

        assert "タイムアウト" in message
        assert "ネットワーク接続" in message

    def test_get_collision_detection_error_message_connection(self):
        """Test error message generation for connection errors."""
        error = CollisionDetectionError("Database connection failed")
        message = _get_collision_detection_error_message(error)

        assert "接続できませんでした" in message
        assert "再試行" in message

    def test_get_collision_detection_error_message_permission(self):
        """Test error message generation for permission errors."""
        error = CollisionDetectionError("Access denied to database")
        message = _get_collision_detection_error_message(error)

        assert "アクセス権限" in message
        assert "管理者" in message

    def test_get_collision_detection_error_message_high_failure_rate(self):
        """Test error message generation for high failure rate."""
        error = CollisionDetectionError("High failure rate in collision detection")
        message = _get_collision_detection_error_message(error)

        assert "多数のファイル" in message
        assert "一時的な問題" in message

    def test_get_collision_detection_error_message_recovery_error(self):
        """Test error message generation for recovery errors."""
        error = CollisionDetectionRecoveryError("Recovery failed after retries")
        message = _get_collision_detection_error_message(error)

        # The function should detect CollisionDetectionRecoveryError type
        assert ("復旧に失敗" in message or "Recovery failed" in message)

    def test_handle_overwrite_operation_error_metadata_not_found(self):
        """Test handling of metadata not found error."""
        from src.imgstream.services.metadata import MetadataError
        error = MetadataError("Photo with filename 'test.jpg' not found")
        result = handle_overwrite_operation_error(error, "test.jpg", "metadata_update")

        assert result["success"] is False
        assert result["is_overwrite"] is True
        assert ("見つかりません" in result["recovery_message"] or "not found" in result["recovery_message"])
        assert any("新規アップロード" in option for option in result["recovery_options"])

    def test_handle_overwrite_operation_error_permission(self):
        """Test handling of permission error."""
        from src.imgstream.services.metadata import MetadataError
        error = MetadataError("Access denied to photo")
        result = handle_overwrite_operation_error(error, "test.jpg", "metadata_update")

        assert result["success"] is False
        assert ("アクセス権限" in result["recovery_message"] or "access" in result["recovery_message"].lower())
        assert any("管理者" in option for option in result["recovery_options"])

    def test_handle_overwrite_operation_error_database(self):
        """Test handling of database error."""
        from src.imgstream.services.metadata import MetadataError
        error = MetadataError("Database update failed")
        result = handle_overwrite_operation_error(error, "test.jpg", "metadata_update")

        assert result["success"] is False
        assert ("データベース" in result["recovery_message"] or "database" in result["recovery_message"].lower())
        assert any("再試行" in option for option in result["recovery_options"])

    def test_handle_overwrite_operation_error_storage(self):
        """Test handling of storage error."""
        error = Exception("StorageError: Upload failed")
        result = handle_overwrite_operation_error(error, "test.jpg", "file_upload")

        assert result["success"] is False
        assert ("アップロード" in result["recovery_message"] or "upload" in result["recovery_message"].lower())
        assert any("ネットワーク" in option or "network" in option.lower() for option in result["recovery_options"])

    def test_handle_overwrite_operation_error_unexpected(self):
        """Test handling of unexpected error."""
        error = ValueError("Unexpected error occurred")
        result = handle_overwrite_operation_error(error, "test.jpg", "unknown_operation")

        assert result["success"] is False
        assert "予期しないエラー" in result["recovery_message"]
        assert "管理者に問い合わせる" in result["recovery_options"]


class TestErrorRecoveryIntegration:
    """Test integration of error recovery mechanisms."""

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_collision_detection_high_failure_rate_triggers_error(self, mock_get_service):
        """Test that high failure rate triggers system error."""
        from src.imgstream.utils.collision_detection import check_filename_collisions

        # Mock metadata service to fail for batch operation
        mock_service = Mock()
        mock_service.check_multiple_filename_exists.side_effect = MetadataError("High failure rate detected")
        mock_get_service.return_value = mock_service

        filenames = ["file1.jpg", "file2.jpg", "file3.jpg", "file4.jpg"]

        with pytest.raises(CollisionDetectionError, match="High failure rate"):
            check_filename_collisions("user123", filenames)

    def test_error_message_truncation(self):
        """Test that very long error messages are truncated."""
        long_error_message = "A" * 200  # 200 character error
        error = CollisionDetectionError(long_error_message)

        message = _get_collision_detection_error_message(error)

        # Should be truncated to ~100 chars plus "..."
        assert len(message) < 150
        assert message.endswith("...")

    @patch("streamlit.session_state", new_callable=dict)
    def test_clear_upload_session_state(self, mock_session_state):
        """Test clearing of upload session state."""
        from src.imgstream.ui.upload_handlers import clear_upload_session_state

        # Set up session state with upload-related keys
        mock_session_state.update({
            "uploaded_files": ["file1.jpg"],
            "validation_results": {"valid": True},
            "collision_results": {"file1.jpg": {}},
            "upload_results": {"success": True},
            "upload_in_progress": True,
            "collision_decisions": {"file1.jpg": "overwrite"},
            "other_key": "should_remain"  # Non-upload related key
        })

        clear_upload_session_state()

        # Upload-related keys that should be cleared (based on actual implementation)
        upload_keys = [
            "valid_files", "validation_errors", "upload_validated",
            "upload_results", "upload_in_progress", "last_upload_result"
        ]
        for key in upload_keys:
            if key in ["upload_results", "upload_in_progress"]:  # These were in the test data
                assert key not in mock_session_state

        # Other keys should remain
        assert "other_key" in mock_session_state
        assert mock_session_state["other_key"] == "should_remain"
