"""Unit tests for MetadataService collision detection functionality."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.imgstream.services.metadata import MetadataService, MetadataError
from src.imgstream.models.photo import PhotoMetadata


class TestMetadataServiceCollisionDetection:
    """Test collision detection functionality in MetadataService."""

    @pytest.fixture
    def metadata_service(self):
        """Create a MetadataService instance for testing."""
        with patch("src.imgstream.services.metadata.get_storage_service"):
            service = MetadataService("test_user_123", "/tmp/test")
            # Mock database manager with context manager support
            mock_db_manager = MagicMock()
            mock_db_manager.__enter__ = Mock(return_value=mock_db_manager)
            mock_db_manager.__exit__ = Mock(return_value=None)
            service._db_manager = mock_db_manager
            # Mock ensure_local_database to avoid GCS calls
            service.ensure_local_database = Mock()
            return service

    @pytest.fixture
    def sample_photo_metadata(self):
        """Create sample PhotoMetadata for testing."""
        return PhotoMetadata(
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

    def test_check_filename_exists_no_collision(self, metadata_service):
        """Test check_filename_exists when no collision exists."""
        # Mock database query to return no results
        metadata_service._db_manager.execute_query.return_value = []

        result = metadata_service.check_filename_exists("new_photo.jpg")

        assert result is None
        metadata_service._db_manager.execute_query.assert_called_once()

    def test_check_filename_exists_collision_found(self, metadata_service, sample_photo_metadata):
        """Test check_filename_exists when collision is found."""
        # Mock database query to return existing photo
        mock_row = [
            sample_photo_metadata.id,
            sample_photo_metadata.user_id,
            sample_photo_metadata.filename,
            sample_photo_metadata.original_path,
            sample_photo_metadata.thumbnail_path,
            sample_photo_metadata.created_at,
            sample_photo_metadata.uploaded_at,
            sample_photo_metadata.file_size,
            sample_photo_metadata.mime_type,
        ]
        metadata_service._db_manager.execute_query.return_value = [mock_row]

        result = metadata_service.check_filename_exists("test_photo.jpg")

        assert result is not None
        assert "existing_photo" in result
        assert "existing_file_info" in result
        assert result["user_decision"] == "pending"
        assert result["warning_shown"] is False

        # Check existing photo data
        existing_photo = result["existing_photo"]
        assert existing_photo.filename == "test_photo.jpg"
        assert existing_photo.user_id == "test_user_123"
        assert existing_photo.file_size == 1024000

        # Check file info for UI
        file_info = result["existing_file_info"]
        assert file_info["file_size"] == 1024000
        assert file_info["photo_id"] == "photo_123"
        assert file_info["upload_date"] == sample_photo_metadata.uploaded_at
        assert file_info["creation_date"] == sample_photo_metadata.created_at

    def test_check_filename_exists_database_error(self, metadata_service):
        """Test check_filename_exists when database query fails."""
        # Mock database query to raise exception
        metadata_service._db_manager.execute_query.side_effect = Exception("Database error")

        with pytest.raises(MetadataError, match="Failed to check filename collision"):
            metadata_service.check_filename_exists("test_photo.jpg")

    def test_check_filename_exists_special_characters(self, metadata_service):
        """Test check_filename_exists with special characters in filename."""
        # Mock database query to return no results
        metadata_service._db_manager.execute_query.return_value = []

        special_filename = "test_photo_日本語_@#$%.jpg"
        result = metadata_service.check_filename_exists(special_filename)

        assert result is None
        # Verify the query was called with the special filename
        call_args = metadata_service._db_manager.execute_query.call_args
        assert special_filename in call_args[0][1]

    def test_check_filename_exists_case_sensitivity(self, metadata_service, sample_photo_metadata):
        """Test that filename collision detection is case sensitive."""
        # Mock database query to return no results for different case
        metadata_service._db_manager.execute_query.return_value = []

        result = metadata_service.check_filename_exists("TEST_PHOTO.JPG")

        assert result is None
        # Verify exact case was used in query
        call_args = metadata_service._db_manager.execute_query.call_args
        assert "TEST_PHOTO.JPG" in call_args[0][1]

    @patch("src.imgstream.services.metadata.logger")
    def test_check_filename_exists_logging(self, mock_logger, metadata_service, sample_photo_metadata):
        """Test that collision detection events are properly logged."""
        # Mock database query to return existing photo
        mock_row = [
            sample_photo_metadata.id,
            sample_photo_metadata.user_id,
            sample_photo_metadata.filename,
            sample_photo_metadata.original_path,
            sample_photo_metadata.thumbnail_path,
            sample_photo_metadata.created_at,
            sample_photo_metadata.uploaded_at,
            sample_photo_metadata.file_size,
            sample_photo_metadata.mime_type,
        ]
        metadata_service._db_manager.execute_query.return_value = [mock_row]

        result = metadata_service.check_filename_exists("test_photo.jpg")

        # Verify collision was logged
        mock_logger.info.assert_called_with(
            "filename_collision_detected",
            user_id="test_user_123",
            filename="test_photo.jpg",
            existing_photo_id="photo_123",
            existing_upload_date=sample_photo_metadata.uploaded_at.isoformat(),
            existing_file_size=1024000,
        )

    def test_check_filename_exists_ensure_database_called(self, metadata_service):
        """Test that ensure_local_database is called before collision check."""
        metadata_service.ensure_local_database = Mock()
        metadata_service._db_manager.execute_query.return_value = []

        metadata_service.check_filename_exists("test_photo.jpg")

        metadata_service.ensure_local_database.assert_called_once()


class TestMetadataServiceUpdateOperations:
    """Test UPDATE operations in MetadataService."""

    @pytest.fixture
    def metadata_service(self):
        """Create a MetadataService instance for testing."""
        with patch("src.imgstream.services.metadata.get_storage_service"):
            service = MetadataService("test_user_123", "/tmp/test")
            # Mock database manager with context manager support
            mock_db_manager = MagicMock()
            mock_db_manager.__enter__ = Mock(return_value=mock_db_manager)
            mock_db_manager.__exit__ = Mock(return_value=None)
            service._db_manager = mock_db_manager
            # Mock ensure_local_database to avoid GCS calls
            service.ensure_local_database = Mock()
            service.trigger_async_sync = Mock()
            return service

    @pytest.fixture
    def sample_photo_metadata(self):
        """Create sample PhotoMetadata for testing."""
        return PhotoMetadata(
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

    def test_update_photo_metadata_with_preservation(self, metadata_service, sample_photo_metadata):
        """Test update_photo_metadata with creation info preservation."""
        # Mock existing record
        existing_id = "existing_photo_123"
        existing_created_at = "2024-01-10T09:00:00"
        metadata_service._db_manager.execute_query.side_effect = [
            [(existing_id, existing_created_at)],  # First call: get existing record
            None,  # Second call: UPDATE query
        ]

        metadata_service.update_photo_metadata(sample_photo_metadata, preserve_creation_info=True)

        # Verify queries were called correctly
        assert metadata_service._db_manager.execute_query.call_count == 2

        # Check first call (SELECT existing)
        first_call = metadata_service._db_manager.execute_query.call_args_list[0]
        assert "SELECT id, created_at FROM photos WHERE filename = ?" in first_call[0][0]
        assert first_call[0][1] == ("test_photo.jpg", "test_user_123")

        # Check second call (UPDATE)
        second_call = metadata_service._db_manager.execute_query.call_args_list[1]
        assert "UPDATE photos SET" in second_call[0][0]
        assert existing_id in second_call[0][1]

    def test_update_photo_metadata_without_preservation(self, metadata_service, sample_photo_metadata):
        """Test update_photo_metadata without creation info preservation."""
        # Mock UPDATE result
        metadata_service._db_manager.execute_query.side_effect = [
            None,  # UPDATE query
            [(1,)],  # changes() query - 1 row affected
        ]

        metadata_service.update_photo_metadata(sample_photo_metadata, preserve_creation_info=False)

        # Verify queries were called correctly
        assert metadata_service._db_manager.execute_query.call_count == 2

        # Check UPDATE call
        first_call = metadata_service._db_manager.execute_query.call_args_list[0]
        assert "UPDATE photos SET" in first_call[0][0]
        assert sample_photo_metadata.id in first_call[0][1]

    def test_update_photo_metadata_not_found_with_preservation(self, metadata_service, sample_photo_metadata):
        """Test update_photo_metadata when photo not found with preservation."""
        # Mock no existing record
        metadata_service._db_manager.execute_query.return_value = []

        with pytest.raises(MetadataError, match="not found for update"):
            metadata_service.update_photo_metadata(sample_photo_metadata, preserve_creation_info=True)

    def test_update_photo_metadata_not_found_without_preservation(self, metadata_service, sample_photo_metadata):
        """Test update_photo_metadata when photo not found without preservation."""
        # Mock UPDATE with no rows affected
        metadata_service._db_manager.execute_query.side_effect = [
            None,  # UPDATE query
            [(0,)],  # changes() query - 0 rows affected
        ]

        with pytest.raises(MetadataError, match="not found for update"):
            metadata_service.update_photo_metadata(sample_photo_metadata, preserve_creation_info=False)

    def test_save_or_update_photo_metadata_overwrite(self, metadata_service, sample_photo_metadata):
        """Test save_or_update_photo_metadata for overwrite operation."""
        # Mock update_photo_metadata
        metadata_service.update_photo_metadata = Mock()

        metadata_service.save_or_update_photo_metadata(sample_photo_metadata, is_overwrite=True)

        # Verify update_photo_metadata was called with preservation
        metadata_service.update_photo_metadata.assert_called_once_with(
            sample_photo_metadata, preserve_creation_info=True
        )

    def test_save_or_update_photo_metadata_new_upload(self, metadata_service, sample_photo_metadata):
        """Test save_or_update_photo_metadata for new upload."""
        # Mock save_photo_metadata
        metadata_service.save_photo_metadata = Mock()

        metadata_service.save_or_update_photo_metadata(sample_photo_metadata, is_overwrite=False)

        # Verify save_photo_metadata was called
        metadata_service.save_photo_metadata.assert_called_once_with(sample_photo_metadata)

    def test_update_photo_metadata_invalid_metadata(self, metadata_service, sample_photo_metadata):
        """Test update_photo_metadata with invalid metadata."""
        # Mock invalid metadata
        sample_photo_metadata.validate = Mock(return_value=False)

        with pytest.raises(MetadataError, match="Invalid photo metadata"):
            metadata_service.update_photo_metadata(sample_photo_metadata)

    def test_update_photo_metadata_user_id_mismatch(self, metadata_service, sample_photo_metadata):
        """Test update_photo_metadata with user ID mismatch."""
        # Change user_id to create mismatch
        sample_photo_metadata.user_id = "different_user"

        with pytest.raises(MetadataError, match="User ID mismatch"):
            metadata_service.update_photo_metadata(sample_photo_metadata)

    def test_update_photo_metadata_database_error(self, metadata_service, sample_photo_metadata):
        """Test update_photo_metadata with database error."""
        # Mock database error
        metadata_service._db_manager.execute_query.side_effect = Exception("Database error")

        with pytest.raises(MetadataError, match="Failed to update photo metadata"):
            metadata_service.update_photo_metadata(sample_photo_metadata)


class TestMetadataServiceDatabaseReset:
    """Test database reset functionality in MetadataService."""

    @pytest.fixture
    def metadata_service(self):
        """Create a MetadataService instance for testing."""
        with patch("src.imgstream.services.metadata.get_storage_service"):
            service = MetadataService("test_user_123", "/tmp/test")
            service._db_manager = Mock()
            return service

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    def test_force_reload_from_gcs_success(self, mock_unlink, mock_exists, metadata_service):
        """Test successful force reload from GCS."""
        # Mock local file exists
        mock_exists.return_value = True

        # Mock GCS database exists and download succeeds
        metadata_service._gcs_database_exists = Mock(return_value=True)
        metadata_service._download_from_gcs = Mock(return_value=True)

        result = metadata_service.force_reload_from_gcs()

        assert result is True
        mock_unlink.assert_called_once()
        metadata_service._download_from_gcs.assert_called_once()

    @patch("pathlib.Path.exists")
    def test_force_reload_from_gcs_no_gcs_database(self, mock_exists, metadata_service):
        """Test force reload when no GCS database exists."""
        # Mock no GCS database exists
        mock_exists.return_value = False
        metadata_service._gcs_database_exists = Mock(return_value=False)
        metadata_service._create_new_database = Mock()

        result = metadata_service.force_reload_from_gcs()

        assert result is False
        metadata_service._create_new_database.assert_called_once()

    @patch("pathlib.Path.exists")
    def test_force_reload_from_gcs_download_fails(self, mock_exists, metadata_service):
        """Test force reload when GCS download fails."""
        # Mock GCS database exists but download fails
        mock_exists.return_value = False
        metadata_service._gcs_database_exists = Mock(return_value=True)
        metadata_service._download_from_gcs = Mock(return_value=False)
        metadata_service._create_new_database = Mock()

        result = metadata_service.force_reload_from_gcs()

        assert result is False
        metadata_service._create_new_database.assert_called_once()

    @patch("pathlib.Path.exists")
    def test_force_reload_from_gcs_closes_db_manager(self, mock_exists, metadata_service):
        """Test that force reload properly closes database manager."""
        mock_exists.return_value = False
        metadata_service._gcs_database_exists = Mock(return_value=False)
        metadata_service._create_new_database = Mock()

        # Store reference to original db_manager before it gets set to None
        original_db_manager = metadata_service._db_manager

        metadata_service.force_reload_from_gcs()

        # Verify database manager was closed and reset
        original_db_manager.close.assert_called_once()
        assert metadata_service._db_manager is None

    def test_force_reload_from_gcs_error_handling(self, metadata_service):
        """Test error handling in force reload."""
        # Mock exception during reload
        metadata_service._gcs_database_exists = Mock(side_effect=Exception("GCS error"))

        with pytest.raises(MetadataError, match="Failed to force reload database from GCS"):
            metadata_service.force_reload_from_gcs()

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    @patch("src.imgstream.services.metadata.log_user_action")
    def test_force_reload_from_gcs_logging(self, mock_log_action, mock_unlink, mock_exists, metadata_service):
        """Test that force reload events are properly logged."""
        mock_exists.return_value = True
        metadata_service._gcs_database_exists = Mock(return_value=True)
        metadata_service._download_from_gcs = Mock(return_value=True)

        metadata_service.force_reload_from_gcs()

        # Verify completion was logged
        mock_log_action.assert_called_with(
            "test_user_123",
            "force_reload_from_gcs_completed",
            gcs_path=metadata_service.gcs_db_path,
            local_path=str(metadata_service.local_db_path),
        )
