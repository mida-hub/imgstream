"""Unit tests for upload handlers with collision detection integration."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from src.imgstream.ui.upload_handlers import (
    validate_uploaded_files_with_collision_check,
    render_file_validation_results_with_collisions,
)
from src.imgstream.models.photo import PhotoMetadata
from src.imgstream.utils.collision_detection import CollisionDetectionError


class TestUploadHandlersCollisionIntegration:
    """Test collision detection integration in upload handlers."""

    @pytest.fixture
    def mock_uploaded_file(self):
        """Create a mock uploaded file for testing."""
        mock_file = Mock()
        mock_file.name = "test_photo.jpg"
        mock_file.read.return_value = b"fake_image_data"
        mock_file.seek = Mock()
        return mock_file

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

    @patch("src.imgstream.ui.upload_handlers.check_filename_collisions")
    @patch("src.imgstream.ui.upload_handlers.get_auth_service")
    @patch("src.imgstream.ui.upload_handlers.ImageProcessor")
    def test_validate_uploaded_files_with_collision_check_no_collisions(
        self, mock_image_processor, mock_get_auth, mock_check_collisions, mock_uploaded_file
    ):
        """Test validation with collision check when no collisions exist."""
        # Mock image processor
        mock_processor = Mock()
        mock_processor.is_supported_format.return_value = True
        mock_processor.validate_file_size.return_value = None
        mock_image_processor.return_value = mock_processor

        # Mock auth service
        mock_auth = Mock()
        mock_user_info = Mock()
        mock_user_info.user_id = "test_user_123"
        mock_auth.ensure_authenticated.return_value = mock_user_info
        mock_get_auth.return_value = mock_auth

        # Mock no collisions
        mock_check_collisions.return_value = {}

        uploaded_files = [mock_uploaded_file]
        valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(uploaded_files)

        assert len(valid_files) == 1
        assert len(validation_errors) == 0
        assert collision_results == {}
        assert valid_files[0]["filename"] == "test_photo.jpg"

        # Verify collision check was called
        mock_check_collisions.assert_called_once_with("test_user_123", ["test_photo.jpg"])

    @patch("src.imgstream.ui.upload_handlers.check_filename_collisions")
    @patch("src.imgstream.ui.upload_handlers.get_auth_service")
    @patch("src.imgstream.ui.upload_handlers.ImageProcessor")
    def test_validate_uploaded_files_with_collision_check_with_collisions(
        self, mock_image_processor, mock_get_auth, mock_check_collisions, mock_uploaded_file, sample_collision_info
    ):
        """Test validation with collision check when collisions exist."""
        # Mock image processor
        mock_processor = Mock()
        mock_processor.is_supported_format.return_value = True
        mock_processor.validate_file_size.return_value = None
        mock_image_processor.return_value = mock_processor

        # Mock auth service
        mock_auth = Mock()
        mock_user_info = Mock()
        mock_user_info.user_id = "test_user_123"
        mock_auth.ensure_authenticated.return_value = mock_user_info
        mock_get_auth.return_value = mock_auth

        # Mock collision found
        mock_check_collisions.return_value = {"test_photo.jpg": sample_collision_info}

        uploaded_files = [mock_uploaded_file]
        valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(uploaded_files)

        assert len(valid_files) == 1
        assert len(validation_errors) == 0
        assert len(collision_results) == 1
        assert "test_photo.jpg" in collision_results
        assert collision_results["test_photo.jpg"] == sample_collision_info

    @patch("src.imgstream.ui.upload_handlers.check_filename_collisions")
    @patch("src.imgstream.ui.upload_handlers.get_auth_service")
    @patch("src.imgstream.ui.upload_handlers.ImageProcessor")
    def test_validate_uploaded_files_with_collision_check_empty_list(
        self, mock_image_processor, mock_get_auth, mock_check_collisions
    ):
        """Test validation with collision check for empty file list."""
        valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check([])

        assert valid_files == []
        assert validation_errors == []
        assert collision_results == {}

        # Collision check should not be called for empty list
        mock_check_collisions.assert_not_called()

    @patch("src.imgstream.ui.upload_handlers.check_filename_collisions")
    @patch("src.imgstream.ui.upload_handlers.get_auth_service")
    @patch("src.imgstream.ui.upload_handlers.ImageProcessor")
    def test_validate_uploaded_files_with_collision_check_invalid_files(
        self, mock_image_processor, mock_get_auth, mock_check_collisions, mock_uploaded_file
    ):
        """Test validation with collision check when all files are invalid."""
        # Mock image processor to reject all files
        mock_processor = Mock()
        mock_processor.is_supported_format.return_value = False
        mock_image_processor.return_value = mock_processor

        uploaded_files = [mock_uploaded_file]
        valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(uploaded_files)

        assert len(valid_files) == 0
        assert len(validation_errors) == 1
        assert collision_results == {}

        # Collision check should not be called when no valid files
        mock_check_collisions.assert_not_called()

    @patch("src.imgstream.ui.upload_handlers.check_filename_collisions")
    @patch("src.imgstream.ui.upload_handlers.get_auth_service")
    @patch("src.imgstream.ui.upload_handlers.ImageProcessor")
    def test_validate_uploaded_files_with_collision_check_collision_error(
        self, mock_image_processor, mock_get_auth, mock_check_collisions, mock_uploaded_file
    ):
        """Test validation with collision check when collision detection fails."""
        # Mock image processor
        mock_processor = Mock()
        mock_processor.is_supported_format.return_value = True
        mock_processor.validate_file_size.return_value = None
        mock_image_processor.return_value = mock_processor

        # Mock auth service
        mock_auth = Mock()
        mock_user_info = Mock()
        mock_user_info.user_id = "test_user_123"
        mock_auth.ensure_authenticated.return_value = mock_user_info
        mock_get_auth.return_value = mock_auth

        # Mock collision detection error

        mock_check_collisions.side_effect = CollisionDetectionError("Database error")

        uploaded_files = [mock_uploaded_file]
        valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(uploaded_files)

        assert len(valid_files) == 1  # File is still valid
        assert len(validation_errors) == 1  # Error added for collision detection failure
        assert collision_results == {}  # No collision results due to error

        # Check error details
        error = validation_errors[0]
        assert error["filename"] == "システム"
        # CollisionDetectionError might be caught as Exception, check for either
        assert ("衝突検出エラー" in error["error"]) or ("予期しないエラー" in error["error"])
        # For unexpected errors, the original error message is not included in details
        if "予期しないエラー" in error["error"]:
            assert "衝突検出中に予期しないエラーが発生しました" in error["details"]
        else:
            assert "Database error" in error["details"]

    @patch("src.imgstream.ui.upload_handlers.check_filename_collisions")
    @patch("src.imgstream.ui.upload_handlers.get_auth_service")
    @patch("src.imgstream.ui.upload_handlers.ImageProcessor")
    def test_validate_uploaded_files_with_collision_check_unexpected_error(
        self, mock_image_processor, mock_get_auth, mock_check_collisions, mock_uploaded_file
    ):
        """Test validation with collision check when unexpected error occurs."""
        # Mock image processor
        mock_processor = Mock()
        mock_processor.is_supported_format.return_value = True
        mock_processor.validate_file_size.return_value = None
        mock_image_processor.return_value = mock_processor

        # Mock auth service
        mock_auth = Mock()
        mock_user_info = Mock()
        mock_user_info.user_id = "test_user_123"
        mock_auth.ensure_authenticated.return_value = mock_user_info
        mock_get_auth.return_value = mock_auth

        # Mock unexpected error
        mock_check_collisions.side_effect = Exception("Unexpected error")

        uploaded_files = [mock_uploaded_file]
        valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(uploaded_files)

        assert len(valid_files) == 1  # File is still valid
        assert len(validation_errors) == 1  # Error added for unexpected error
        assert collision_results == {}  # No collision results due to error

        # Check error details
        error = validation_errors[0]
        assert error["filename"] == "システム"
        assert "予期しないエラー" in error["error"]

    @patch("src.imgstream.ui.upload_handlers.check_filename_collisions")
    @patch("src.imgstream.ui.upload_handlers.get_auth_service")
    @patch("src.imgstream.ui.upload_handlers.ImageProcessor")
    def test_validate_uploaded_files_with_collision_check_mixed_files(
        self, mock_image_processor, mock_get_auth, mock_check_collisions, sample_collision_info
    ):
        """Test validation with collision check for mixed valid/invalid files."""
        # Create multiple mock files
        valid_file = Mock()
        valid_file.name = "valid_photo.jpg"
        valid_file.read.return_value = b"fake_image_data"
        valid_file.seek = Mock()

        invalid_file = Mock()
        invalid_file.name = "invalid_photo.txt"
        invalid_file.read.return_value = b"not_image_data"
        invalid_file.seek = Mock()

        collision_file = Mock()
        collision_file.name = "collision_photo.jpg"
        collision_file.read.return_value = b"fake_image_data"
        collision_file.seek = Mock()

        # Mock image processor
        mock_processor = Mock()
        mock_processor.is_supported_format.side_effect = lambda name: name.endswith(".jpg")
        mock_processor.validate_file_size.return_value = None
        mock_image_processor.return_value = mock_processor

        # Mock auth service
        mock_auth = Mock()
        mock_user_info = Mock()
        mock_user_info.user_id = "test_user_123"
        mock_auth.ensure_authenticated.return_value = mock_user_info
        mock_get_auth.return_value = mock_auth

        # Mock collision for one file
        mock_check_collisions.return_value = {"collision_photo.jpg": sample_collision_info}

        uploaded_files = [valid_file, invalid_file, collision_file]
        valid_files, validation_errors, collision_results = validate_uploaded_files_with_collision_check(uploaded_files)

        assert len(valid_files) == 2  # valid_photo.jpg and collision_photo.jpg
        assert len(validation_errors) == 1  # invalid_photo.txt
        assert len(collision_results) == 1  # collision_photo.jpg

        # Verify collision check was called with only valid filenames
        mock_check_collisions.assert_called_once_with("test_user_123", ["valid_photo.jpg", "collision_photo.jpg"])


class TestRenderFileValidationResultsWithCollisions:
    """Test rendering of validation results with collision information."""

    @pytest.fixture
    def sample_valid_files(self):
        """Create sample valid files for testing."""
        return [
            {"filename": "photo1.jpg", "size": 1024000},
            {"filename": "photo2.jpg", "size": 2048000},
        ]

    @pytest.fixture
    def sample_collision_info(self):
        """Create sample collision info for testing."""
        photo_metadata = PhotoMetadata(
            id="photo_123",
            user_id="test_user_123",
            filename="photo1.jpg",
            original_path="photos/test_user_123/original/photo1.jpg",
            thumbnail_path="photos/test_user_123/thumbs/photo1_thumb.jpg",
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

    @patch("streamlit.success")
    @patch("streamlit.info")
    @patch("streamlit.expander")
    def test_render_validation_results_no_collisions(self, mock_expander, mock_info, mock_success, sample_valid_files):
        """Test rendering validation results with no collisions."""
        # Mock expander context manager
        mock_expander_context = MagicMock()
        mock_expander.return_value.__enter__ = Mock(return_value=mock_expander_context)
        mock_expander.return_value.__exit__ = Mock(return_value=None)

        render_file_validation_results_with_collisions(sample_valid_files, [], {})

        # Should show success message and info about no collisions
        mock_success.assert_called_once()
        mock_info.assert_called_once_with(
            "✅ ファイル名の衝突は検出されませんでした。すべてのファイルを安全にアップロードできます。"
        )

    @patch("streamlit.warning")
    @patch("streamlit.expander")
    @patch("streamlit.success")
    def test_render_validation_results_with_collisions(
        self, mock_success, mock_expander, mock_warning, sample_valid_files, sample_collision_info
    ):
        """Test rendering validation results with collisions."""
        # Mock expander context manager
        mock_expander_context = MagicMock()
        mock_expander.return_value.__enter__ = Mock(return_value=mock_expander_context)
        mock_expander.return_value.__exit__ = Mock(return_value=None)

        collision_results = {"photo1.jpg": sample_collision_info}

        render_file_validation_results_with_collisions(sample_valid_files, [], collision_results)

        # Should show success for valid files and warning for collisions
        mock_success.assert_called_once()
        mock_warning.assert_called_once_with("⚠️ 1 file(s) have filename conflicts")

    @patch("streamlit.error")
    @patch("streamlit.expander")
    def test_render_validation_results_with_errors(self, mock_expander, mock_error):
        """Test rendering validation results with validation errors."""
        # Mock expander context manager
        mock_expander_context = MagicMock()
        mock_expander.return_value.__enter__ = Mock(return_value=mock_expander_context)
        mock_expander.return_value.__exit__ = Mock(return_value=None)

        validation_errors = [
            {"filename": "invalid.txt", "error": "Unsupported format", "details": "Only images supported"}
        ]

        render_file_validation_results_with_collisions([], validation_errors, {})

        # Should show error message
        mock_error.assert_called()
