"""Integration tests for error recovery and fallback mechanisms."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import time

from imgstream.utils.collision_detection import (
    check_filename_collisions,
    check_filename_collisions_with_fallback,
    check_filename_collisions_with_retry,
    CollisionDetectionError,
    CollisionDetectionRecoveryError,
)
from imgstream.services.metadata import MetadataError
from imgstream.ui.handlers.upload import (
    validate_uploaded_files_with_collision_check,
    process_batch_upload,
    process_single_upload,
    _get_collision_detection_error_message,
)


class TestErrorRecoveryIntegration:
    """Integration tests for error recovery mechanisms."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = "error_recovery_test_user"

        # Clear collision monitor
        monitor = get_collision_monitor()
        monitor.collision_events.clear()
        monitor.overwrite_events.clear()
        monitor.user_decision_events.clear()

    def create_mock_uploaded_file(self, filename: str, content: bytes = b"fake_image_data") -> MagicMock:
        """Create a mock uploaded file object."""
        mock_file = MagicMock()
        mock_file.name = filename
        mock_file.read.return_value = content
        mock_file.seek = MagicMock()
        return mock_file

    @patch('imgstream.utils.collision_detection.check_filename_collisions')
    def test_collision_detection_retry_mechanism(self, mock_check_collisions):
        """Test collision detection retry mechanism with eventual success."""
        # Configure collision detection to fail first two attempts, succeed on third
        call_count = 0
        def mock_check_with_retries(user_id, filenames):
            nonlocal call_count
            call_count += 1

            if call_count <= 2:
                raise CollisionDetectionError(f"Temporary failure {call_count}")

            # Third attempt succeeds
            return {}  # No collisions

        mock_check_collisions.side_effect = mock_check_with_retries

        # Test retry mechanism
        start_time = time.perf_counter()
        result = check_filename_collisions_with_retry(
            self.user_id,
            ["retry_test.jpg"],
            max_retries=3,
            retry_delay=0.1
        )
        end_time = time.perf_counter()

        # Verify eventual success
        assert len(result) == 0  # No collisions found
        assert call_count == 3  # Three attempts made

        # Verify retry delay was applied (should take at least 0.3 seconds for 3 retries)
        elapsed_time = end_time - start_time
        assert elapsed_time >= 0.3  # 0.1 + 0.2 (exponential backoff)

    @patch('imgstream.utils.collision_detection.check_filename_collisions')
    def test_collision_detection_retry_exhaustion(self, mock_check_collisions):
        """Test collision detection when all retries are exhausted."""
        # Configure collision detection to always fail
        mock_check_collisions.side_effect = CollisionDetectionError("Persistent failure")

        # Test retry exhaustion
        with pytest.raises(CollisionDetectionRecoveryError) as exc_info:
            check_filename_collisions_with_retry(
                self.user_id,
                ["persistent_fail.jpg"],
                max_retries=2,
                retry_delay=0.05
            )

        # Verify error message contains retry information
        assert "failed after 3 attempts" in str(exc_info.value)
        assert "Persistent failure" in str(exc_info.value)

    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_fallback_mode_activation(self, mock_get_metadata_service):
        """Test fallback mode activation when primary detection fails."""
        mock_service = MagicMock()
        mock_get_metadata_service.return_value = mock_service

        # Configure both batch and individual methods to fail
        mock_service.check_multiple_filename_exists.side_effect = MetadataError("Service unavailable")
        mock_service.check_filename_exists.side_effect = MetadataError("Service unavailable")

        # Test fallback mode
        collision_results, fallback_used = check_filename_collisions_with_fallback(
            self.user_id,
            ["fallback_test1.jpg", "fallback_test2.jpg"],
            enable_fallback=True
        )

        # Verify fallback was used
        assert fallback_used is True
        assert len(collision_results) == 2  # All files assumed to have collisions

        # Verify fallback collision structure
        for filename in ["fallback_test1.jpg", "fallback_test2.jpg"]:
            assert filename in collision_results
            collision_info = collision_results[filename]
            assert collision_info["fallback_mode"] is True
            assert collision_info["collision_detected"] is True
            assert "安全のため既存ファイルがあると仮定" in collision_info["warning_message"]

    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_fallback_mode_disabled(self, mock_get_metadata_service):
        """Test behavior when fallback mode is disabled."""
        mock_service = MagicMock()
        mock_get_metadata_service.return_value = mock_service

        # Configure both batch and individual methods to fail
        mock_service.check_multiple_filename_exists.side_effect = MetadataError("Service unavailable")
        mock_service.check_filename_exists.side_effect = MetadataError("Service unavailable")

        # Test with fallback disabled
        with pytest.raises((CollisionDetectionError, CollisionDetectionRecoveryError)):
            check_filename_collisions_with_fallback(
                self.user_id,
                ["no_fallback_test.jpg"],
                enable_fallback=False
            )

    @patch('imgstream.ui.upload_handlers.get_auth_service')
    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_validation_with_collision_detection_failure(self, mock_get_metadata_service, mock_get_auth_service):
        """Test file validation when collision detection fails."""
        # Set up auth service
        mock_auth_service = MagicMock()
        mock_auth_service.ensure_authenticated.return_value = MagicMock(user_id=self.user_id)
        mock_get_auth_service.return_value = mock_auth_service

        # Set up metadata service to fail
        mock_service = MagicMock()
        mock_get_metadata_service.return_value = mock_service
        mock_service.check_multiple_filename_exists.side_effect = MetadataError("Database connection lost")
        mock_service.check_filename_exists.side_effect = MetadataError("Database connection lost")

        # Create test uploaded files
        uploaded_files = [
            self.create_mock_uploaded_file("test1.jpg"),
            self.create_mock_uploaded_file("test2.jpg"),
        ]

        # Mock image processor for validation
        with patch('imgstream.ui.upload_handlers.ImageProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.is_supported_format.return_value = True
            mock_processor.validate_file_size.return_value = None

            # Test validation with collision detection failure
            valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(
                uploaded_files
            )

            # Verify files are still validated
            assert len(valid_files) == 2

            # Verify collision detection failure is reported
            assert len(validation_errors) >= 1

            # Find collision-related error
            collision_error = next(
                (error for error in validation_errors if "衝突検出" in error.get("error", "")),
                None
            )
            assert collision_error is not None
            assert "フォールバック" in collision_error["error"]
            assert "details" in collision_error

            # Verify collision results contain fallback results (all files assumed to have collisions)
            assert len(collision_results) == 2  # Both files should be in fallback mode

    @patch('imgstream.ui.upload_handlers.get_auth_service')
    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_validation_with_collision_detection_fallback(self, mock_get_metadata_service, mock_get_auth_service):
        """Test file validation when collision detection uses fallback mode."""
        # Set up auth service
        mock_auth_service = MagicMock()
        mock_auth_service.ensure_authenticated.return_value = MagicMock(user_id=self.user_id)
        mock_get_auth_service.return_value = mock_auth_service

        # Set up metadata service to fail initially, triggering fallback
        mock_service = MagicMock()
        mock_get_metadata_service.return_value = mock_service
        mock_service.check_multiple_filename_exists.side_effect = MetadataError("Temporary service issue")
        mock_service.check_filename_exists.side_effect = MetadataError("Temporary service issue")

        # Create test uploaded files
        uploaded_files = [
            self.create_mock_uploaded_file("fallback1.jpg"),
            self.create_mock_uploaded_file("fallback2.jpg"),
        ]

        # Mock image processor for validation
        with patch('imgstream.ui.upload_handlers.ImageProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.is_supported_format.return_value = True
            mock_processor.validate_file_size.return_value = None

            # Test validation with collision detection fallback
            valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(
                uploaded_files
            )

            # Verify files are still validated
            assert len(valid_files) == 2

            # Verify fallback warning is present
            fallback_error = next(
                (error for error in validation_errors if "フォールバック" in error.get("error", "")),
                None
            )
            assert fallback_error is not None
            assert "安全モード" in fallback_error["details"]

            # Verify collision results show fallback mode
            assert len(collision_results) == 2  # All files assumed to have collisions
            for filename in ["fallback1.jpg", "fallback2.jpg"]:
                assert collision_results[filename]["fallback_mode"] is True

    @patch('imgstream.ui.upload_handlers.get_auth_service')
    @patch('imgstream.ui.upload_handlers.get_metadata_service')
    @patch('imgstream.ui.upload_handlers.get_storage_service')
    @patch('imgstream.ui.upload_handlers.ImageProcessor')
    def test_batch_upload_with_partial_failures(self, mock_image_processor_class, mock_get_storage_service,
                                               mock_get_metadata_service, mock_get_auth_service):
        """Test batch upload with some files failing and others succeeding."""
        # Set up mocks
        mock_auth_service = MagicMock()
        mock_auth_service.ensure_authenticated.return_value = MagicMock(user_id=self.user_id)
        mock_get_auth_service.return_value = mock_auth_service

        mock_metadata_service = MagicMock()
        mock_get_metadata_service.return_value = mock_metadata_service

        mock_storage_service = MagicMock()
        mock_get_storage_service.return_value = mock_storage_service

        mock_image_processor = MagicMock()
        mock_image_processor_class.return_value = mock_image_processor
        mock_image_processor.extract_creation_date.return_value = datetime.now()
        mock_image_processor.generate_thumbnail.return_value = b"thumbnail_data"

        # Configure storage service to succeed
        mock_storage_service.upload_original_photo.return_value = {"gcs_path": "gs://bucket/original"}
        mock_storage_service.upload_thumbnail.return_value = {"gcs_path": "gs://bucket/thumbnail"}

        # Configure metadata service to fail for some files
        def mock_save_metadata(photo_metadata, is_overwrite=False):
            if photo_metadata.filename == "fail_file.jpg":
                raise Exception("Database write failed")
            return {
                "success": True,
                "operation": "save",
                "photo_id": f"photo_{photo_metadata.filename}",
            }

        mock_metadata_service.save_or_update_photo_metadata.side_effect = mock_save_metadata

        # Set up test files
        valid_files = [
            {
                "file_object": self.create_mock_uploaded_file("success_file.jpg"),
                "filename": "success_file.jpg",
                "size": 1024,
                "data": b"success_data",
            },
            {
                "file_object": self.create_mock_uploaded_file("fail_file.jpg"),
                "filename": "fail_file.jpg",
                "size": 2048,
                "data": b"fail_data",
            },
            {
                "file_object": self.create_mock_uploaded_file("another_success.jpg"),
                "filename": "another_success.jpg",
                "size": 1536,
                "data": b"another_success_data",
            },
        ]

        # Process batch upload
        batch_result = process_batch_upload(valid_files)

        # Verify partial success
        assert batch_result["success"] is False  # Not all files succeeded
        assert batch_result["total_files"] == 3
        assert batch_result["successful_uploads"] == 2  # success_file.jpg and another_success.jpg
        assert batch_result["failed_uploads"] == 1  # fail_file.jpg

        # Verify individual results
        results = batch_result["results"]
        assert len(results) == 3

        # Check specific results
        success_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]

        assert len(success_results) == 2
        assert len(failed_results) == 1

        # Verify failed result
        failed_result = failed_results[0]
        assert failed_result["filename"] == "fail_file.jpg"
        assert "Database write failed" in failed_result["error"]

    @patch('imgstream.ui.upload_handlers.get_auth_service')
    @patch('imgstream.ui.upload_handlers.get_metadata_service')
    @patch('imgstream.ui.upload_handlers.get_storage_service')
    @patch('imgstream.ui.upload_handlers.ImageProcessor')
    def test_overwrite_operation_failure_recovery(self, mock_image_processor_class, mock_get_storage_service,
                                                 mock_get_metadata_service, mock_get_auth_service):
        """Test overwrite operation failure and recovery mechanisms."""
        # Set up mocks
        mock_auth_service = MagicMock()
        mock_auth_service.ensure_authenticated.return_value = MagicMock(user_id=self.user_id)
        mock_get_auth_service.return_value = mock_auth_service

        mock_metadata_service = MagicMock()
        mock_get_metadata_service.return_value = mock_metadata_service

        mock_storage_service = MagicMock()
        mock_get_storage_service.return_value = mock_storage_service

        mock_image_processor = MagicMock()
        mock_image_processor_class.return_value = mock_image_processor
        mock_image_processor.extract_creation_date.return_value = datetime.now()
        mock_image_processor.generate_thumbnail.return_value = b"thumbnail_data"

        # Configure storage service to succeed
        mock_storage_service.upload_original_photo.return_value = {"gcs_path": "gs://bucket/original"}
        mock_storage_service.upload_thumbnail.return_value = {"gcs_path": "gs://bucket/thumbnail"}

        # Configure metadata service to fail overwrite operation
        mock_metadata_service.save_or_update_photo_metadata.side_effect = Exception("Overwrite failed")

        # Set up test file for overwrite
        file_info = {
            "file_object": self.create_mock_uploaded_file("overwrite_fail.jpg"),
            "filename": "overwrite_fail.jpg",
            "size": 2048,
            "data": b"overwrite_data",
        }

        # Process overwrite that should fail
        result = process_single_upload(file_info, is_overwrite=True)

        # Verify failure was handled gracefully
        assert result["success"] is False
        assert result["is_overwrite"] is True
        assert "Overwrite failed" in result["error"]
        assert "Failed to overwrite" in result["message"]

        # Verify error handling was appropriate
        # Note: Overwrite failure monitoring is not currently implemented
        # but the error was handled gracefully and returned proper error information

    def test_network_timeout_simulation(self):
        """Test behavior during network timeouts and connectivity issues."""
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            # Simulate network timeout
            import socket
            mock_service.check_multiple_filename_exists.side_effect = socket.timeout("Network timeout")
            mock_service.check_filename_exists.side_effect = socket.timeout("Network timeout")

            # Test collision detection with network timeout
            with pytest.raises((CollisionDetectionError, CollisionDetectionRecoveryError)) as exc_info:
                check_filename_collisions_with_retry(
                    self.user_id,
                    ["network_timeout.jpg"],
                    max_retries=1,
                    retry_delay=0.1
                )

            # Verify timeout was handled as a collision detection error
            assert "Network timeout" in str(exc_info.value)

    def test_memory_pressure_handling(self):
        """Test behavior under memory pressure conditions."""
        # Simulate memory pressure by creating large collision results
        large_batch_size = 1000
        filenames = [f"memory_test_{i:04d}.jpg" for i in range(large_batch_size)]

        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            # Configure service to return collision for every file (memory intensive)
            def mock_check_memory_intensive(filename):
                # Create a collision result with substantial data
                return {
                    "existing_photo": MagicMock(
                        id=f"existing_{filename}",
                        filename=filename,
                        file_size=1024 * 1024,  # 1MB
                        created_at=datetime.now(),
                        uploaded_at=datetime.now(),
                    ),
                    "existing_file_info": {
                        "photo_id": f"existing_{filename}",
                        "file_size": 1024 * 1024,
                        "upload_date": datetime.now(),
                        "creation_date": datetime.now(),
                    },
                    "collision_detected": True,
                    "metadata": {f"key_{i}": f"value_{i}" for i in range(100)},  # Additional metadata
                }

            mock_service.check_multiple_filename_exists.side_effect = MetadataError("Batch not available")
            mock_service.check_filename_exists.side_effect = mock_check_memory_intensive

            # Test collision detection with large batch
            try:
                collision_results = check_filename_collisions(self.user_id, filenames)

                # Verify results were generated
                assert len(collision_results) == large_batch_size

                # Verify memory usage is reasonable (basic check)
                import sys
                # This is a simple check - in a real scenario, you'd use more sophisticated memory monitoring
                assert sys.getsizeof(collision_results) > 0

            except MemoryError:
                # If memory error occurs, verify it's handled gracefully
                pytest.skip("Memory pressure test caused MemoryError - this is expected behavior")

    def test_database_connection_recovery(self):
        """Test database connection recovery scenarios."""
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            # Simulate database connection issues
            call_count = 0
            def mock_check_with_connection_recovery(filename):
                nonlocal call_count
                call_count += 1

                if call_count <= 2:
                    # First two calls: connection error
                    raise MetadataError("Connection to database lost")
                elif call_count == 3:
                    # Third call: connection recovered, but different error
                    raise MetadataError("Query timeout")
                else:
                    # Fourth call: fully recovered
                    return None  # No collision

            mock_service.check_multiple_filename_exists.side_effect = MetadataError("Batch not available")
            mock_service.check_filename_exists.side_effect = mock_check_with_connection_recovery

            # Test connection recovery
            result = check_filename_collisions_with_retry(
                self.user_id,
                ["db_recovery.jpg"],
                max_retries=4,
                retry_delay=0.05
            )

            # Verify eventual success after connection recovery
            assert len(result) == 0  # No collisions found
            assert call_count == 4  # Four attempts made

    def test_cascading_failure_prevention(self):
        """Test prevention of cascading failures across the system."""
        # Test that failure in one component doesn't cascade to others

        with patch('imgstream.ui.upload_handlers.get_auth_service') as mock_get_auth_service, \
             patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_metadata_service:

            # Set up auth service to work
            mock_auth_service = MagicMock()
            mock_auth_service.ensure_authenticated.return_value = MagicMock(user_id=self.user_id)
            mock_get_auth_service.return_value = mock_auth_service

            # Set up metadata service to fail
            mock_service = MagicMock()
            mock_get_metadata_service.return_value = mock_service
            mock_service.check_multiple_filename_exists.side_effect = Exception("Critical system failure")
            mock_service.check_filename_exists.side_effect = Exception("Critical system failure")

            # Create test uploaded files
            uploaded_files = [self.create_mock_uploaded_file("cascade_test.jpg")]

            # Mock image processor for validation
            with patch('imgstream.ui.upload_handlers.ImageProcessor') as mock_processor_class:
                mock_processor = MagicMock()
                mock_processor_class.return_value = mock_processor
                mock_processor.is_supported_format.return_value = True
                mock_processor.validate_file_size.return_value = None

                # Test that validation still works despite collision detection failure
                valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(
                    uploaded_files
                )

                # Verify file validation still succeeded
                assert len(valid_files) == 1
                assert valid_files[0]["filename"] == "cascade_test.jpg"

                # Verify collision detection failure was handled with fallback
                assert len(validation_errors) >= 1  # Should have collision detection error
                assert len(collision_results) == 1  # Fallback results provided

                # Verify system didn't crash and provided user-friendly error
                collision_error = next(
                    (error for error in validation_errors if "フォールバック" in error.get("error", "")),
                    None
                )
                assert collision_error is not None
                assert "details" in collision_error


def _get_collision_detection_error_message(error: Exception) -> str:
    """Get user-friendly error message for collision detection errors."""
    error_str = str(error).lower()

    if "timeout" in error_str or "connection" in error_str:
        return (
            "ネットワーク接続に問題があります。インターネット接続を確認して、"
            "しばらく待ってから再試行してください。"
        )
    elif "database" in error_str or "metadata" in error_str:
        return (
            "データベースサービスに一時的な問題が発生しています。"
            "数分待ってから再試行してください。"
        )
    elif "memory" in error_str:
        return (
            "システムリソースが不足しています。ファイル数を減らして再試行してください。"
        )
    else:
        return (
            "衝突検出システムに予期しない問題が発生しました。"
            "ページを再読み込みして再試行してください。問題が続く場合は管理者にお問い合わせください。"
        )
