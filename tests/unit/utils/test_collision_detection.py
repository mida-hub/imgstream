"""Unit tests for collision detection utilities."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.imgstream.utils.collision_detection import (
    check_filename_collisions,
    process_collision_results,
    filter_files_by_collision_decision,
    get_collision_summary_message,
    CollisionDetectionError,
)
from src.imgstream.models.photo import PhotoMetadata


class TestCollisionDetectionUtilities:
    """Test collision detection utility functions."""

    @pytest.fixture
    def sample_collision_info(self):
        """Create sample collision info for testing."""
        photo_metadata = PhotoMetadata(
            id="photo_123",
            user_id="test_user_123",
            filename="test_photo.jpg",
            original_path="photos/test_user_123/original/test_photo.jpg",
            thumbnail_path="photos/test_user_123/thumbs/test_photo_thumb.jpg",
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            uploaded_at=datetime(2024, 1, 15, 11, 0, 0),
            file_size=1024000,
            mime_type="image/jpeg",
        )

        return {
            "existing_photo": photo_metadata,
            "existing_file_info": {
                "upload_date": photo_metadata.uploaded_at,
                "file_size": photo_metadata.file_size,
                "creation_date": photo_metadata.created_at,
                "photo_id": photo_metadata.id,
            },
            "user_decision": "pending",
            "warning_shown": False,
        }

    @pytest.fixture
    def sample_valid_files(self):
        """Create sample valid files for testing."""
        return [
            {
                "filename": "photo1.jpg",
                "size": 1024000,
                "data": b"fake_image_data_1",
                "file_object": Mock(),
            },
            {
                "filename": "photo2.jpg",
                "size": 2048000,
                "data": b"fake_image_data_2",
                "file_object": Mock(),
            },
            {
                "filename": "photo3.jpg",
                "size": 512000,
                "data": b"fake_image_data_3",
                "file_object": Mock(),
            },
        ]

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_check_filename_collisions_no_collisions(self, mock_get_service):
        """Test check_filename_collisions when no collisions exist."""
        # Mock metadata service
        mock_service = Mock()
        mock_service.check_multiple_filename_exists.return_value = {}
        mock_get_service.return_value = mock_service

        filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
        result = check_filename_collisions("test_user_123", filenames)

        assert result == {}
        mock_service.check_multiple_filename_exists.assert_called_once_with(filenames)

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_check_filename_collisions_with_collisions(self, mock_get_service, sample_collision_info):
        """Test check_filename_collisions when collisions exist."""
        # Mock metadata service
        mock_service = Mock()
        mock_service.check_multiple_filename_exists.return_value = {
            "photo2.jpg": sample_collision_info
        }
        mock_get_service.return_value = mock_service

        filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
        result = check_filename_collisions("test_user_123", filenames)

        assert len(result) == 1
        assert "photo2.jpg" in result
        assert result["photo2.jpg"] == sample_collision_info

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_check_filename_collisions_empty_list(self, mock_get_service):
        """Test check_filename_collisions with empty filename list."""
        result = check_filename_collisions("test_user_123", [])

        assert result == {}
        mock_get_service.assert_not_called()

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_check_filename_collisions_service_error(self, mock_get_service):
        """Test check_filename_collisions when metadata service fails."""
        # Mock metadata service to raise exception
        mock_service = Mock()
        mock_service.check_multiple_filename_exists.side_effect = Exception("Service error")
        mock_get_service.return_value = mock_service

        with pytest.raises(CollisionDetectionError, match="Failed to check filename collisions"):
            check_filename_collisions("test_user_123", ["photo1.jpg"])

    def test_process_collision_results_no_collisions(self):
        """Test process_collision_results with no collisions."""
        result = process_collision_results({})

        expected = {
            "collisions": {},
            "summary": {
                "total_collisions": 0,
                "overwrite_count": 0,
                "skip_count": 0,
                "pending_count": 0,
            },
        }
        assert result == expected

    def test_process_collision_results_with_decisions(self, sample_collision_info):
        """Test process_collision_results with user decisions."""
        collision_results = {
            "photo1.jpg": sample_collision_info.copy(),
            "photo2.jpg": sample_collision_info.copy(),
            "photo3.jpg": sample_collision_info.copy(),
        }

        user_decisions = {
            "photo1.jpg": "overwrite",
            "photo2.jpg": "skip",
            # photo3.jpg has no decision (pending)
        }

        result = process_collision_results(collision_results, user_decisions)

        assert result["summary"]["total_collisions"] == 3
        assert result["summary"]["overwrite_count"] == 1
        assert result["summary"]["skip_count"] == 1
        assert result["summary"]["pending_count"] == 1

        # Check individual decisions
        assert result["collisions"]["photo1.jpg"]["user_decision"] == "overwrite"
        assert result["collisions"]["photo2.jpg"]["user_decision"] == "skip"
        assert result["collisions"]["photo3.jpg"]["user_decision"] == "pending"

    def test_filter_files_by_collision_decision_no_collisions(self, sample_valid_files):
        """Test filter_files_by_collision_decision with no collisions."""
        result = filter_files_by_collision_decision(sample_valid_files, {})

        assert len(result["proceed_files"]) == 3
        assert len(result["skip_files"]) == 0
        assert len(result["collision_files"]) == 0

        # All files should be marked as not overwrite
        for file_info in result["proceed_files"]:
            assert file_info["is_overwrite"] is False

    def test_filter_files_by_collision_decision_with_collisions(self, sample_valid_files, sample_collision_info):
        """Test filter_files_by_collision_decision with various collision decisions."""
        collision_results = {
            "photo1.jpg": {**sample_collision_info, "user_decision": "overwrite"},
            "photo2.jpg": {**sample_collision_info, "user_decision": "skip"},
            "photo3.jpg": {**sample_collision_info, "user_decision": "pending"},
        }

        # Add photo4.jpg to test files (no collision)
        files_with_extra = sample_valid_files + [
            {
                "filename": "photo4.jpg",
                "size": 256000,
                "data": b"fake_image_data_4",
                "file_object": Mock(),
            }
        ]

        result = filter_files_by_collision_decision(files_with_extra, collision_results)

        # photo1.jpg (overwrite) + photo4.jpg (new) should proceed
        assert len(result["proceed_files"]) == 2
        # photo2.jpg (skip) should be skipped
        assert len(result["skip_files"]) == 1
        # All collision files should be in collision_files
        assert len(result["collision_files"]) == 3

        # Check overwrite flag
        overwrite_files = [f for f in result["proceed_files"] if f["is_overwrite"]]
        new_files = [f for f in result["proceed_files"] if not f["is_overwrite"]]
        assert len(overwrite_files) == 1
        assert len(new_files) == 1
        assert overwrite_files[0]["filename"] == "photo1.jpg"
        assert new_files[0]["filename"] == "photo4.jpg"

    def test_get_collision_summary_message_no_collisions(self):
        """Test get_collision_summary_message with no collisions."""
        summary = {
            "total_collisions": 0,
            "overwrite_count": 0,
            "skip_count": 0,
            "pending_count": 0,
        }

        message = get_collision_summary_message(summary)
        assert message == "ファイル名の衝突は検出されませんでした。"

    def test_get_collision_summary_message_single_collision(self):
        """Test get_collision_summary_message with single collision."""
        summary = {
            "total_collisions": 1,
            "overwrite_count": 1,
            "skip_count": 0,
            "pending_count": 0,
        }

        message = get_collision_summary_message(summary)
        assert "1件のファイル名衝突が検出されました" in message
        assert "1件を上書き" in message

    def test_get_collision_summary_message_multiple_collisions(self):
        """Test get_collision_summary_message with multiple collisions."""
        summary = {
            "total_collisions": 5,
            "overwrite_count": 2,
            "skip_count": 1,
            "pending_count": 2,
        }

        message = get_collision_summary_message(summary)
        assert "5件のファイル名衝突が検出されました" in message
        assert "2件を上書き" in message
        assert "1件をスキップ" in message
        assert "2件が決定待ち" in message

    def test_get_collision_summary_message_mixed_decisions(self):
        """Test get_collision_summary_message with mixed decisions."""
        summary = {
            "total_collisions": 3,
            "overwrite_count": 1,
            "skip_count": 1,
            "pending_count": 1,
        }

        message = get_collision_summary_message(summary)
        assert "3件のファイル名衝突が検出されました" in message
        assert "1件を上書き" in message
        assert "1件をスキップ" in message
        assert "1件が決定待ち" in message

    def test_collision_detection_error_creation(self):
        """Test CollisionDetectionError creation."""
        original_error = ValueError("Original error")
        error = CollisionDetectionError("Test error", original_error)

        assert str(error) == "Test error"
        assert error.original_error == original_error

    def test_collision_detection_error_without_original(self):
        """Test CollisionDetectionError creation without original error."""
        error = CollisionDetectionError("Test error")

        assert str(error) == "Test error"
        assert error.original_error is None


class TestCollisionDetectionIntegration:
    """Integration tests for collision detection utilities."""

    @pytest.fixture
    def sample_collision_info(self):
        """Create sample collision info for testing."""
        photo_metadata = PhotoMetadata(
            id="photo_123",
            user_id="test_user_123",
            filename="test_photo.jpg",
            original_path="photos/test_user_123/original/test_photo.jpg",
            thumbnail_path="photos/test_user_123/thumbs/test_photo_thumb.jpg",
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            uploaded_at=datetime(2024, 1, 15, 11, 0, 0),
            file_size=1024000,
            mime_type="image/jpeg",
        )

        return {
            "existing_photo": photo_metadata,
            "existing_file_info": {
                "upload_date": photo_metadata.uploaded_at,
                "file_size": photo_metadata.file_size,
                "creation_date": photo_metadata.created_at,
                "photo_id": photo_metadata.id,
            },
            "user_decision": "pending",
            "warning_shown": False,
        }

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_full_collision_detection_workflow(self, mock_get_service, sample_collision_info):
        """Test complete collision detection workflow."""
        # Mock metadata service
        mock_service = Mock()
        mock_service.check_multiple_filename_exists.return_value = {
            "photo1.jpg": sample_collision_info
        }
        mock_get_service.return_value = mock_service

        # Step 1: Check collisions
        filenames = ["photo1.jpg", "photo2.jpg"]
        collision_results = check_filename_collisions("test_user_123", filenames)

        # Step 2: Process with user decisions
        user_decisions = {"photo1.jpg": "overwrite"}
        processed_results = process_collision_results(collision_results, user_decisions)

        # Step 3: Filter files
        valid_files = [
            {"filename": "photo1.jpg", "size": 1024000, "data": b"data1"},
            {"filename": "photo2.jpg", "size": 2048000, "data": b"data2"},
        ]
        filtered_files = filter_files_by_collision_decision(valid_files, processed_results["collisions"])

        # Step 4: Generate summary message
        summary_message = get_collision_summary_message(processed_results["summary"])

        # Verify results
        assert len(collision_results) == 1
        assert processed_results["summary"]["overwrite_count"] == 1
        assert len(filtered_files["proceed_files"]) == 2  # overwrite + new
        assert len(filtered_files["skip_files"]) == 0
        assert "1件のファイル名衝突が検出されました" in summary_message
        assert "1件を上書き" in summary_message
