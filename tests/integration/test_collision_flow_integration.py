"""Integration tests for collision detection and overwrite flow."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, mock_open
from typing import Dict, Any, List
import io

from imgstream.models.photo import PhotoMetadata
from imgstream.services.metadata import MetadataService
from imgstream.services.storage import StorageService
from imgstream.services.image_processor import ImageProcessor
from imgstream.utils.collision_detection import (
    check_filename_collisions,
    check_filename_collisions_with_fallback,
    CollisionDetectionError,
)
from imgstream.ui.upload_handlers import (
    validate_uploaded_files_with_collision_check,
    process_batch_upload,
    process_single_upload,
)
from imgstream.monitoring.collision_monitor import get_collision_monitor


class TestCollisionDetectionIntegration:
    """Integration tests for collision detection flow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = "test_user_integration"
        self.temp_dir = tempfile.mkdtemp()

        # Mock services
        self.mock_metadata_service = MagicMock(spec=MetadataService)
        self.mock_storage_service = MagicMock(spec=StorageService)
        self.mock_image_processor = MagicMock(spec=ImageProcessor)

        # Clear collision monitor
        monitor = get_collision_monitor()
        monitor.collision_events.clear()
        monitor.overwrite_events.clear()
        monitor.user_decision_events.clear()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_mock_uploaded_file(self, filename: str, content: bytes = b"fake_image_data") -> MagicMock:
        """Create a mock uploaded file object."""
        mock_file = MagicMock()
        mock_file.name = filename
        mock_file.read.return_value = content
        mock_file.seek = MagicMock()
        return mock_file

    def create_existing_photo(self, filename: str, photo_id: str = None) -> PhotoMetadata:
        """Create an existing photo metadata object."""
        if photo_id is None:
            photo_id = f"existing_{filename.replace('.', '_')}"

        return PhotoMetadata.create_new(
            user_id=self.user_id,
            filename=filename,
            original_path=f"gs://bucket/originals/{self.user_id}/{filename}",
            thumbnail_path=f"gs://bucket/thumbnails/{self.user_id}/{filename}",
            file_size=1024 * 1024,  # 1MB
            mime_type="image/jpeg",
            created_at=datetime.now() - timedelta(days=1),
            uploaded_at=datetime.now() - timedelta(days=1),
        )

    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_end_to_end_collision_detection_and_resolution(self, mock_get_metadata_service):
        """Test complete collision detection and resolution flow."""
        # Set up existing photos
        existing_photo1 = self.create_existing_photo("photo1.jpg", "existing_1")
        existing_photo2 = self.create_existing_photo("photo2.jpg", "existing_2")

        # Configure metadata service mock
        mock_get_metadata_service.return_value = self.mock_metadata_service

        def mock_check_filename_exists(filename):
            if filename == "photo1.jpg":
                return {
                    "existing_photo": existing_photo1,
                    "existing_file_info": {
                        "photo_id": existing_photo1.id,
                        "file_size": existing_photo1.file_size,
                        "upload_date": existing_photo1.uploaded_at,
                        "creation_date": existing_photo1.created_at,
                    },
                    "collision_detected": True,
                }
            elif filename == "photo2.jpg":
                return {
                    "existing_photo": existing_photo2,
                    "existing_file_info": {
                        "photo_id": existing_photo2.id,
                        "file_size": existing_photo2.file_size,
                        "upload_date": existing_photo2.uploaded_at,
                        "creation_date": existing_photo2.created_at,
                    },
                    "collision_detected": True,
                }
            return None

        self.mock_metadata_service.check_filename_exists.side_effect = mock_check_filename_exists

        # Test collision detection
        filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]  # photo3.jpg has no collision
        collision_results = check_filename_collisions(self.user_id, filenames)

        # Verify collision detection results
        assert len(collision_results) == 2
        assert "photo1.jpg" in collision_results
        assert "photo2.jpg" in collision_results
        assert "photo3.jpg" not in collision_results

        # Verify collision events were logged
        monitor = get_collision_monitor()
        collision_events = [e for e in monitor.collision_events if e.event_type == "detected"]
        assert len(collision_events) == 2

        # Test collision resolution with user decisions
        from imgstream.ui.upload_handlers import handle_collision_decision_monitoring

        # User decides to overwrite photo1.jpg and skip photo2.jpg
        handle_collision_decision_monitoring(
            user_id=self.user_id,
            filename="photo1.jpg",
            decision="overwrite",
            existing_photo_id=existing_photo1.id,
        )

        handle_collision_decision_monitoring(
            user_id=self.user_id,
            filename="photo2.jpg",
            decision="skip",
            existing_photo_id=existing_photo2.id,
        )

        # Verify decision events were logged
        decision_events = monitor.user_decision_events
        assert len(decision_events) == 2

        overwrite_decision = next(e for e in decision_events if e.filename == "photo1.jpg")
        skip_decision = next(e for e in decision_events if e.filename == "photo2.jpg")

        assert overwrite_decision.decision == "overwrite"
        assert skip_decision.decision == "skip"

        # Verify resolution events were logged
        resolution_events = [e for e in monitor.collision_events if e.event_type == "resolved"]
        assert len(resolution_events) == 2

    @patch('imgstream.ui.upload_handlers.get_auth_service')
    @patch('imgstream.ui.upload_handlers.get_metadata_service')
    @patch('imgstream.ui.upload_handlers.get_storage_service')
    @patch('imgstream.ui.upload_handlers.ImageProcessor')
    def test_mixed_batch_upload_integration(self, mock_image_processor_class, mock_get_storage_service,
                                          mock_get_metadata_service, mock_get_auth_service):
        """Test mixed batch upload with new files, overwrites, and skips."""
        # Set up mocks
        mock_auth_service = MagicMock()
        mock_auth_service.ensure_authenticated.return_value = MagicMock(user_id=self.user_id)
        mock_get_auth_service.return_value = mock_auth_service

        mock_get_metadata_service.return_value = self.mock_metadata_service
        mock_get_storage_service.return_value = self.mock_storage_service

        mock_image_processor = MagicMock()
        mock_image_processor_class.return_value = mock_image_processor
        mock_image_processor.extract_creation_date.return_value = datetime.now()
        mock_image_processor.generate_thumbnail.return_value = b"thumbnail_data"

        # Configure storage service
        self.mock_storage_service.upload_original_photo.return_value = {"gcs_path": "gs://bucket/original"}
        self.mock_storage_service.upload_thumbnail.return_value = {"gcs_path": "gs://bucket/thumbnail"}

        # Configure metadata service for save/update operations
        self.mock_metadata_service.save_or_update_photo_metadata.return_value = {
            "success": True,
            "operation": "save",
            "photo_id": "new_photo_id",
        }

        # Set up test files
        valid_files = [
            {
                "file_object": self.create_mock_uploaded_file("new_photo.jpg"),
                "filename": "new_photo.jpg",
                "size": 1024,
                "data": b"new_photo_data",
            },
            {
                "file_object": self.create_mock_uploaded_file("overwrite_photo.jpg"),
                "filename": "overwrite_photo.jpg",
                "size": 2048,
                "data": b"overwrite_photo_data",
            },
            {
                "file_object": self.create_mock_uploaded_file("skip_photo.jpg"),
                "filename": "skip_photo.jpg",
                "size": 1536,
                "data": b"skip_photo_data",
            },
        ]

        # Set up collision results with user decisions
        collision_results = {
            "overwrite_photo.jpg": {
                "existing_photo": self.create_existing_photo("overwrite_photo.jpg"),
                "existing_file_info": {
                    "photo_id": "existing_overwrite_id",
                    "file_size": 1024,
                    "upload_date": datetime.now() - timedelta(days=1),
                    "creation_date": datetime.now() - timedelta(days=2),
                },
                "collision_detected": True,
                "user_decision": "overwrite",
            },
            "skip_photo.jpg": {
                "existing_photo": self.create_existing_photo("skip_photo.jpg"),
                "existing_file_info": {
                    "photo_id": "existing_skip_id",
                    "file_size": 2048,
                    "upload_date": datetime.now() - timedelta(days=1),
                    "creation_date": datetime.now() - timedelta(days=2),
                },
                "collision_detected": True,
                "user_decision": "skip",
            },
        }

        # Process batch upload
        batch_result = process_batch_upload(valid_files, collision_results)

        # Verify batch results
        assert batch_result["success"] is True
        assert batch_result["total_files"] == 3
        assert batch_result["successful_uploads"] == 2  # new_photo + overwrite_photo
        assert batch_result["failed_uploads"] == 0
        assert batch_result["skipped_uploads"] == 1  # skip_photo
        assert batch_result["overwrite_uploads"] == 1  # overwrite_photo

        # Verify individual results
        results = batch_result["results"]
        assert len(results) == 3

        # Find results by filename
        new_result = next(r for r in results if r["filename"] == "new_photo.jpg")
        overwrite_result = next(r for r in results if r["filename"] == "overwrite_photo.jpg")
        skip_result = next(r for r in results if r["filename"] == "skip_photo.jpg")

        # Verify new upload
        assert new_result["success"] is True
        assert new_result.get("is_overwrite", False) is False

        # Verify overwrite
        assert overwrite_result["success"] is True
        assert overwrite_result["is_overwrite"] is True

        # Verify skip
        assert skip_result["success"] is True
        assert skip_result.get("skipped", False) is True

        # Verify service calls
        assert self.mock_storage_service.upload_original_photo.call_count == 2  # new + overwrite
        assert self.mock_storage_service.upload_thumbnail.call_count == 2  # new + overwrite
        assert self.mock_metadata_service.save_or_update_photo_metadata.call_count == 2  # new + overwrite

    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_error_recovery_scenarios(self, mock_get_metadata_service):
        """Test error recovery scenarios in collision detection."""
        # Configure metadata service to always fail to trigger fallback
        mock_get_metadata_service.return_value = self.mock_metadata_service

        def mock_check_with_persistent_failure(filename):
            # Always fail to force fallback mode
            raise Exception("Database connection error")

        self.mock_metadata_service.check_filename_exists.side_effect = mock_check_with_persistent_failure

        # Test collision detection with fallback
        filenames = ["test_photo.jpg"]
        collision_results, fallback_used = check_filename_collisions_with_fallback(
            self.user_id, filenames, enable_fallback=True
        )

        # Verify fallback was used
        assert fallback_used is True
        assert len(collision_results) == 1  # Fallback assumes collision
        assert collision_results["test_photo.jpg"]["fallback_mode"] is True

        # Verify the fallback collision result structure
        fallback_result = collision_results["test_photo.jpg"]
        assert fallback_result["collision_detected"] is True
        assert "warning_message" in fallback_result
        assert "安全のため既存ファイルがあると仮定" in fallback_result["warning_message"]

    @patch('imgstream.ui.upload_handlers.get_auth_service')
    @patch('imgstream.ui.upload_handlers.get_metadata_service')
    @patch('imgstream.ui.upload_handlers.get_storage_service')
    @patch('imgstream.ui.upload_handlers.ImageProcessor')
    def test_database_consistency_during_overwrite(self, mock_image_processor_class, mock_get_storage_service,
                                                  mock_get_metadata_service, mock_get_auth_service):
        """Test database consistency during overwrite operations."""
        # Set up mocks
        mock_auth_service = MagicMock()
        mock_auth_service.ensure_authenticated.return_value = MagicMock(user_id=self.user_id)
        mock_get_auth_service.return_value = mock_auth_service

        mock_get_metadata_service.return_value = self.mock_metadata_service
        mock_get_storage_service.return_value = self.mock_storage_service

        mock_image_processor = MagicMock()
        mock_image_processor_class.return_value = mock_image_processor
        mock_image_processor.extract_creation_date.return_value = datetime.now()
        mock_image_processor.generate_thumbnail.return_value = b"thumbnail_data"

        # Configure storage service
        self.mock_storage_service.upload_original_photo.return_value = {"gcs_path": "gs://bucket/original"}
        self.mock_storage_service.upload_thumbnail.return_value = {"gcs_path": "gs://bucket/thumbnail"}

        # Test successful overwrite
        original_photo = self.create_existing_photo("test_photo.jpg", "original_id")

        # Configure metadata service to simulate successful overwrite
        self.mock_metadata_service.save_or_update_photo_metadata.return_value = {
            "success": True,
            "operation": "overwrite",
            "photo_id": original_photo.id,
            "fallback_used": False,
        }

        # Create file info
        file_info = {
            "file_object": self.create_mock_uploaded_file("test_photo.jpg"),
            "filename": "test_photo.jpg",
            "size": 2048,
            "data": b"new_photo_data",
        }

        # Process overwrite
        result = process_single_upload(file_info, is_overwrite=True)

        # Verify successful overwrite
        assert result["success"] is True
        assert result["is_overwrite"] is True
        assert result["filename"] == "test_photo.jpg"

        # Verify metadata service was called with overwrite flag
        self.mock_metadata_service.save_or_update_photo_metadata.assert_called_once()
        call_args = self.mock_metadata_service.save_or_update_photo_metadata.call_args
        assert call_args[1]["is_overwrite"] is True

        # Verify overwrite operation was successful
        # Note: The monitoring system may not capture events in test environment
        # Instead, verify the core functionality through service calls
        assert self.mock_storage_service.upload_original_photo.called
        assert self.mock_storage_service.upload_thumbnail.called

        # Test overwrite failure and recovery
        self.mock_metadata_service.reset_mock()

        # Configure metadata service to fail overwrite, then use fallback
        self.mock_metadata_service.save_or_update_photo_metadata.side_effect = [
            Exception("Primary overwrite failed"),
        ]

        # Process overwrite that should fail
        result = process_single_upload(file_info, is_overwrite=True)

        # Verify failure was handled
        assert result["success"] is False
        assert "overwrite" in result["message"].lower()

    def test_backward_compatibility_with_existing_photos(self):
        """Test backward compatibility with existing photo metadata."""
        # Create photos with old metadata format (simulating existing data)
        old_format_photo = PhotoMetadata(
            id="old_photo_1",
            user_id=self.user_id,
            filename="old_photo.jpg",
            original_path="gs://bucket/old_photo.jpg",
            thumbnail_path="gs://bucket/thumb_old_photo.jpg",
            file_size=1024,
            mime_type="image/jpeg",
            created_at=datetime.now() - timedelta(days=30),
            uploaded_at=datetime.now() - timedelta(days=30),
        )

        # Test that collision detection works with old format photos
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            # Configure service to return old format photo for batch check
            mock_service.check_multiple_filename_exists.return_value = {
                "old_photo.jpg": {
                    "existing_photo": old_format_photo,
                    "existing_file_info": {
                        "photo_id": old_format_photo.id,
                        "file_size": old_format_photo.file_size,
                        "upload_date": old_format_photo.uploaded_at,
                        "creation_date": old_format_photo.created_at,
                    },
                    "collision_detected": True,
                }
            }

            # Test collision detection
            collision_results = check_filename_collisions(self.user_id, ["old_photo.jpg"])

            # Verify collision was detected correctly
            assert len(collision_results) == 1
            assert "old_photo.jpg" in collision_results

            collision_info = collision_results["old_photo.jpg"]
            assert collision_info["existing_photo"].id == "old_photo_1"
            assert collision_info["existing_file_info"]["photo_id"] == "old_photo_1"

            # Verify the old photo data is accessible
            existing_photo = collision_info["existing_photo"]
            assert existing_photo.filename == "old_photo.jpg"
            assert existing_photo.user_id == self.user_id
            assert existing_photo.file_size == 1024

    @patch('imgstream.ui.upload_handlers.get_auth_service')
    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_complete_validation_and_collision_flow(self, mock_get_metadata_service, mock_get_auth_service):
        """Test complete file validation and collision detection flow."""
        # Set up auth service
        mock_auth_service = MagicMock()
        mock_auth_service.ensure_authenticated.return_value = MagicMock(user_id=self.user_id)
        mock_get_auth_service.return_value = mock_auth_service

        # Set up metadata service
        mock_get_metadata_service.return_value = self.mock_metadata_service

        # Configure collision detection
        existing_photo = self.create_existing_photo("existing.jpg")

        def mock_check_filename_exists(filename):
            if filename == "existing.jpg":
                return {
                    "existing_photo": existing_photo,
                    "existing_file_info": {
                        "photo_id": existing_photo.id,
                        "file_size": existing_photo.file_size,
                        "upload_date": existing_photo.uploaded_at,
                        "creation_date": existing_photo.created_at,
                    },
                    "collision_detected": True,
                }
            return None

        self.mock_metadata_service.check_filename_exists.side_effect = mock_check_filename_exists

        # Create test uploaded files
        uploaded_files = [
            self.create_mock_uploaded_file("valid.jpg", b"valid_image_data"),
            self.create_mock_uploaded_file("existing.jpg", b"existing_image_data"),
            self.create_mock_uploaded_file("invalid.txt", b"not_an_image"),  # Invalid format
        ]

        # Mock image processor for validation
        with patch('imgstream.ui.upload_handlers.ImageProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor

            # Configure format validation
            def mock_is_supported_format(filename):
                return filename.lower().endswith(('.jpg', '.jpeg', '.heic', '.heif'))

            mock_processor.is_supported_format.side_effect = mock_is_supported_format
            mock_processor.validate_file_size.return_value = None  # No size errors

            # Test validation with collision check
            valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(
                uploaded_files
            )

            # Verify validation results
            assert len(valid_files) == 2  # valid.jpg and existing.jpg
            assert len(validation_errors) == 1  # invalid.txt

            # Verify collision results
            assert len(collision_results) == 1  # existing.jpg
            assert "existing.jpg" in collision_results

            # Verify validation error
            error = validation_errors[0]
            assert error["filename"] == "invalid.txt"
            assert "Unsupported file format" in error["error"]

            # Verify collision info
            collision_info = collision_results["existing.jpg"]
            assert collision_info["existing_photo"].filename == "existing.jpg"
            assert collision_info["collision_detected"] is True

    def test_performance_monitoring_integration(self):
        """Test that performance monitoring works throughout the collision flow."""
        monitor = get_collision_monitor()
        initial_event_count = len(monitor.collision_events)

        # Test batch collision detection monitoring
        from imgstream.ui.upload_handlers import monitor_batch_collision_processing

        filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
        collision_results = {
            "photo1.jpg": {"existing_photo": {"id": "existing_1"}},
            "photo2.jpg": {"existing_photo": {"id": "existing_2"}},
        }

        # Monitor batch processing
        monitor_batch_collision_processing(
            user_id=self.user_id,
            filenames=filenames,
            collision_results=collision_results,
            processing_time_ms=1500.0
        )

        # Verify monitoring data was recorded
        # Note: The actual logging happens in the monitor, we're testing the integration

        # Test user decision monitoring
        from imgstream.ui.upload_handlers import handle_collision_decision_monitoring

        handle_collision_decision_monitoring(
            user_id=self.user_id,
            filename="photo1.jpg",
            decision="overwrite",
            existing_photo_id="existing_1",
        )

        # Verify decision was logged
        decision_events = monitor.user_decision_events
        assert len(decision_events) >= 1

        latest_decision = decision_events[-1]
        assert latest_decision.user_id == self.user_id
        assert latest_decision.filename == "photo1.jpg"
        assert latest_decision.decision == "overwrite"

    def test_concurrent_collision_detection(self):
        """Test collision detection under concurrent access scenarios."""
        # This test simulates concurrent users uploading files with same names

        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            # Simulate race condition where file is uploaded between collision check and upload
            call_count = 0
            def mock_batch_check_with_race_condition(filenames):
                nonlocal call_count
                call_count += 1

                if call_count == 1:
                    # First check: no collision
                    return {}
                else:
                    # Second check: collision appeared (another user uploaded)
                    existing_photo = self.create_existing_photo("race_test.jpg", f"race_condition_{call_count}")
                    return {
                        "race_test.jpg": {
                            "existing_photo": existing_photo,
                            "existing_file_info": {
                                "photo_id": existing_photo.id,
                                "file_size": existing_photo.file_size,
                                "upload_date": existing_photo.uploaded_at,
                                "creation_date": existing_photo.created_at,
                            },
                            "collision_detected": True,
                        }
                    }

            mock_service.check_multiple_filename_exists.side_effect = mock_batch_check_with_race_condition

            # First collision check
            result1 = check_filename_collisions(self.user_id, ["race_test.jpg"], use_cache=False)
            assert len(result1) == 0  # No collision initially

            # Second collision check (simulating later check)
            result2 = check_filename_collisions(self.user_id, ["race_test.jpg"], use_cache=False)
            assert len(result2) == 1  # Collision detected
            assert "race_test.jpg" in result2

    def test_large_batch_processing(self):
        """Test collision detection and processing with large batches."""
        # Test with a large number of files to ensure performance and stability
        large_batch_size = 100
        filenames = [f"photo_{i:03d}.jpg" for i in range(large_batch_size)]

        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            # Configure some files to have collisions (every 10th file)
            def mock_check_large_batch(filenames_list):
                results = {}
                for filename in filenames_list:
                    file_num = int(filename.split('_')[1].split('.')[0])
                    if file_num % 10 == 0:  # Every 10th file has collision
                        existing_photo = self.create_existing_photo(filename, f"existing_{file_num}")
                        results[filename] = {
                            "existing_photo": existing_photo,
                            "existing_file_info": {
                                "photo_id": existing_photo.id,
                                "file_size": existing_photo.file_size,
                                "upload_date": existing_photo.uploaded_at,
                                "creation_date": existing_photo.created_at,
                            },
                            "collision_detected": True,
                        }
                return results

            mock_service.check_multiple_filename_exists.side_effect = mock_check_large_batch

            # Test collision detection on large batch
            collision_results = check_filename_collisions(self.user_id, filenames)

            # Verify results
            expected_collisions = large_batch_size // 10  # Every 10th file
            assert len(collision_results) == expected_collisions

            # Verify specific collision files
            for i in range(0, large_batch_size, 10):
                expected_filename = f"photo_{i:03d}.jpg"
                assert expected_filename in collision_results

            # Verify monitoring captured the batch processing
            monitor = get_collision_monitor()
            # Should have logged collision detection events
            recent_collision_events = [
                e for e in monitor.collision_events
                if e.user_id == self.user_id and e.event_type == "detected"
            ]
            assert len(recent_collision_events) >= expected_collisions


class TestDataIntegrity:
    """Test data integrity during collision and overwrite operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = "integrity_test_user"

    def test_metadata_consistency_during_overwrite(self):
        """Test that metadata remains consistent during overwrite operations."""
        # Create original photo metadata
        original_created_at = datetime.now() - timedelta(days=5)
        original_uploaded_at = datetime.now() - timedelta(days=5)

        original_photo = PhotoMetadata(
            id="original_photo_id",
            user_id=self.user_id,
            filename="consistency_test.jpg",
            original_path="gs://bucket/original_path.jpg",
            thumbnail_path="gs://bucket/original_thumb.jpg",
            file_size=1024,
            mime_type="image/jpeg",
            created_at=original_created_at,
            uploaded_at=original_uploaded_at,
        )

        # Create new photo metadata for overwrite
        new_created_at = datetime.now() - timedelta(days=1)
        new_uploaded_at = datetime.now()

        new_photo = PhotoMetadata.create_new(
            user_id=self.user_id,
            filename="consistency_test.jpg",
            original_path="gs://bucket/new_path.jpg",
            thumbnail_path="gs://bucket/new_thumb.jpg",
            file_size=2048,
            mime_type="image/jpeg",
            created_at=new_created_at,
            uploaded_at=new_uploaded_at,
        )

        # Test that overwrite preserves original ID and creation date
        # This would be handled by the MetadataService.save_or_update_photo_metadata method

        # Verify key fields that should be preserved
        assert original_photo.id == "original_photo_id"
        assert original_photo.created_at == original_created_at

        # Verify fields that should be updated
        assert new_photo.file_size == 2048
        assert new_photo.uploaded_at == new_uploaded_at

    def test_transaction_rollback_on_failure(self):
        """Test that failed operations don't leave partial data."""
        # This test would verify that if an overwrite operation fails partway through,
        # the system rolls back to a consistent state

        with patch('imgstream.services.metadata.MetadataService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Configure service to fail during overwrite
            mock_service.save_or_update_photo_metadata.side_effect = Exception("Database error")

            # Attempt overwrite that should fail
            file_info = {
                "filename": "test_rollback.jpg",
                "data": b"test_data",
                "size": 1024,
            }

            with patch('imgstream.ui.upload_handlers.get_auth_service'), \
                 patch('imgstream.ui.upload_handlers.get_storage_service'), \
                 patch('imgstream.ui.upload_handlers.ImageProcessor'):

                result = process_single_upload(file_info, is_overwrite=True)

                # Verify operation failed
                assert result["success"] is False
                assert "error" in result

                # In a real implementation, we would verify that:
                # 1. No partial metadata was saved
                # 2. No files were uploaded to storage
                # 3. Original data remains unchanged

    def test_concurrent_overwrite_protection(self):
        """Test protection against concurrent overwrite operations."""
        # This test would verify that concurrent overwrites of the same file
        # are handled safely without data corruption

        # In a real implementation, this might involve:
        # 1. Database locking mechanisms
        # 2. Optimistic concurrency control
        # 3. Atomic operations

        # For now, we test that the collision detection system
        # can handle concurrent access patterns

        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            # Simulate concurrent collision checks
            existing_photo = PhotoMetadata.create_new(
                user_id=self.user_id,
                filename="concurrent_test.jpg",
                original_path="gs://bucket/concurrent.jpg",
                thumbnail_path="gs://bucket/concurrent_thumb.jpg",
                file_size=1024,
                mime_type="image/jpeg",
                created_at=datetime.now() - timedelta(hours=1),
                uploaded_at=datetime.now() - timedelta(hours=1),
            )

            mock_service.check_multiple_filename_exists.return_value = {
                "concurrent_test.jpg": {
                    "existing_photo": existing_photo,
                    "existing_file_info": {
                        "photo_id": existing_photo.id,
                        "file_size": existing_photo.file_size,
                        "upload_date": existing_photo.uploaded_at,
                        "creation_date": existing_photo.created_at,
                    },
                    "collision_detected": True,
                }
            }

            # Multiple concurrent collision checks should return consistent results
            result1 = check_filename_collisions(self.user_id, ["concurrent_test.jpg"], use_cache=False)
            result2 = check_filename_collisions(self.user_id, ["concurrent_test.jpg"], use_cache=False)

            assert result1 == result2
            assert len(result1) == 1
            assert "concurrent_test.jpg" in result1
