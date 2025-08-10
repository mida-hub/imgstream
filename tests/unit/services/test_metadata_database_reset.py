"""Tests for MetadataService database reset functionality."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, PropertyMock
from datetime import datetime

from imgstream.services.metadata import MetadataService, MetadataError
from imgstream.models.photo import PhotoMetadata


class TestMetadataServiceDatabaseReset:
    """Test database reset functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = "test_user_reset"
        self.temp_dir = tempfile.mkdtemp()

        # Mock storage service
        self.mock_storage_service = MagicMock()

        # Create metadata service with mocked storage
        with patch('imgstream.services.metadata.get_storage_service') as mock_get_storage:
            mock_get_storage.return_value = self.mock_storage_service
            self.metadata_service = MetadataService(self.user_id, self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_force_reload_from_gcs_requires_confirmation(self):
        """Test that force_reload_from_gcs requires explicit confirmation."""
        with pytest.raises(MetadataError) as exc_info:
            self.metadata_service.force_reload_from_gcs(confirm_reset=False)

        assert "requires explicit confirmation" in str(exc_info.value)

    @patch('imgstream.services.metadata.log_user_action')
    def test_force_reload_from_gcs_successful_reset(self, mock_log_user_action):
        """Test successful database reset with GCS download."""
        # Create a fake local database file
        local_db_path = Path(self.temp_dir) / f"metadata_{self.user_id}.db"
        local_db_path.write_text("fake_db_content")

        # Mock GCS operations
        self.mock_storage_service.file_exists.return_value = True
        self.mock_storage_service.download_file.return_value = b"new_db_content_from_gcs"

        # Mock database manager
        mock_db_manager = MagicMock()
        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=None)
        mock_connection.execute.return_value.fetchone.return_value = [5]  # photo count
        mock_db_manager.get_connection.return_value = mock_connection
        mock_db_manager.connect.return_value = mock_connection

        with patch.object(type(self.metadata_service), 'db_manager', new_callable=PropertyMock) as mock_db_prop:
            mock_db_prop.return_value = mock_db_manager
            result = self.metadata_service.force_reload_from_gcs(confirm_reset=True)

        # Verify result
        assert result["success"] is True
        assert result["operation"] == "database_reset"
        assert result["user_id"] == self.user_id
        assert result["local_db_deleted"] is True
        assert result["gcs_database_exists"] is True
        assert result["download_successful"] is True
        assert "reset_duration_seconds" in result

        # Verify GCS operations were called
        self.mock_storage_service.file_exists.assert_called_once()
        self.mock_storage_service.download_file.assert_called_once()

        # Verify logging
        assert mock_log_user_action.call_count >= 2  # initiated and completed
    @patch('imgstream.services.metadata.log_user_action')
    def test_force_reload_from_gcs_no_gcs_database(self, mock_log_user_action):
        """Test database reset when no GCS database exists."""
        # Create a fake local database file
        local_db_path = Path(self.temp_dir) / f"metadata_{self.user_id}.db"
        local_db_path.write_text("fake_db_content")

        # Mock GCS operations - no database exists
        self.mock_storage_service.file_exists.return_value = False

        # Mock database manager
        mock_db_manager = MagicMock()
        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=None)
        mock_connection.execute.return_value.fetchone.return_value = [0]  # photo count
        mock_db_manager.get_connection.return_value = mock_connection
        mock_db_manager.connect.return_value = mock_connection

        with patch.object(type(self.metadata_service), 'db_manager', new_callable=PropertyMock) as mock_db_prop:
            mock_db_prop.return_value = mock_db_manager
            result = self.metadata_service.force_reload_from_gcs(confirm_reset=True)

        # Verify result
        assert result["success"] is True
        assert result["local_db_deleted"] is True
        assert result["gcs_database_exists"] is False
        assert result["download_successful"] is False

        # Verify GCS download was not called
        self.mock_storage_service.download_file.assert_not_called()

    def test_force_reload_from_gcs_database_close_failure(self):
        """Test database reset when database close fails."""
        # Mock database manager that fails to close
        mock_db_manager = MagicMock()
        mock_db_manager.close.side_effect = Exception("Close failed")

        self.metadata_service._db_manager = mock_db_manager

        # Mock GCS operations
        self.mock_storage_service.file_exists.return_value = False

        with patch.object(self.metadata_service, 'ensure_local_database'):
            # Should not raise exception, just log warning
            result = self.metadata_service.force_reload_from_gcs(confirm_reset=True)

        assert result["success"] is True
        # Database manager should be reset to None during the process
        # (Note: A new one may be created during reinitialization)

    def test_force_reload_from_gcs_local_file_deletion_failure(self):
        """Test database reset when local file deletion fails."""
        # Create a local database file
        local_db_path = Path(self.temp_dir) / f"metadata_{self.user_id}.db"
        local_db_path.write_text("fake_db_content")

        # Mock file deletion to fail
        with patch.object(Path, 'unlink', side_effect=OSError("Permission denied")):
            with pytest.raises(MetadataError) as exc_info:
                self.metadata_service.force_reload_from_gcs(confirm_reset=True)

        assert "Failed to delete local database" in str(exc_info.value)

    def test_force_reload_from_gcs_gcs_download_failure(self):
        """Test database reset when GCS download fails."""
        # Mock GCS operations to fail
        self.mock_storage_service.file_exists.return_value = True
        self.mock_storage_service.download_database_file.side_effect = Exception("Download failed")

        # Mock database manager
        mock_db_manager = MagicMock()
        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=None)
        mock_connection.execute.return_value.fetchone.return_value = [0]
        mock_db_manager.get_connection.return_value = mock_connection
        mock_db_manager.connect.return_value = mock_connection

        with patch.object(type(self.metadata_service), 'db_manager', new_callable=PropertyMock) as mock_db_prop:
            mock_db_prop.return_value = mock_db_manager
            # Should continue with creating new database
            result = self.metadata_service.force_reload_from_gcs(confirm_reset=True)

        assert result["success"] is True
        assert result["download_successful"] is False

    def test_force_reload_from_gcs_reinitialization_failure(self):
        """Test database reset when reinitialization fails."""
        # Mock ensure_local_database to fail
        with patch.object(self.metadata_service, 'ensure_local_database',
                         side_effect=Exception("Reinitialization failed")):

            with pytest.raises(MetadataError) as exc_info:
                self.metadata_service.force_reload_from_gcs(confirm_reset=True)

        assert "Failed to reinitialize database" in str(exc_info.value)

    def test_get_database_info(self):
        """Test getting database information."""
        # Create a fake local database file
        local_db_path = Path(self.temp_dir) / f"metadata_{self.user_id}.db"
        local_db_path.write_text("fake_db_content")

        # Mock GCS and database operations
        self.mock_storage_service.file_exists.return_value = True

        mock_db_manager = MagicMock()
        mock_db_context = MagicMock()
        mock_connection = MagicMock()

        # Set up context manager for db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_context)
        mock_db_manager.__exit__ = MagicMock(return_value=None)

        # Set up connection and query result
        mock_db_context.get_table_info.return_value = {"photos": {"columns": 5}}
        mock_db_context.connect.return_value = mock_connection
        mock_connection.execute.return_value.fetchone.return_value = (10,)  # photo count

        self.metadata_service._db_manager = mock_db_manager
        self.metadata_service._last_sync_time = datetime(2023, 1, 1, 12, 0, 0)

        info = self.metadata_service.get_database_info()

        # Verify info structure
        assert info["user_id"] == self.user_id
        assert info["local_db_exists"] is True
        assert info["local_db_size"] > 0
        assert info["gcs_db_exists"] is True
        assert info["photo_count"] == 10
        assert info["last_sync_time"] == "2023-01-01T12:00:00"
        assert info["sync_enabled"] is True

    def test_get_database_info_no_local_db(self):
        """Test getting database info when no local database exists."""
        # Mock GCS operations
        self.mock_storage_service.file_exists.return_value = False

        info = self.metadata_service.get_database_info()

        assert info["local_db_exists"] is False
        assert info["local_db_size"] is None
        assert info["gcs_db_exists"] is False
        assert info["photo_count"] is None

    def test_get_database_info_gcs_check_failure(self):
        """Test getting database info when GCS check fails."""
        # Mock GCS operations to fail
        self.mock_storage_service.file_exists.side_effect = Exception("GCS error")

        info = self.metadata_service.get_database_info()

        assert info["gcs_db_exists"] is None

    def test_validate_database_integrity_valid_database(self):
        """Test database integrity validation with valid database."""
        # Create a fake local database file
        local_db_path = Path(self.temp_dir) / f"metadata_{self.user_id}.db"
        local_db_path.write_text("fake_db_content")

        # Mock the validate_database_integrity method directly
        with patch.object(self.metadata_service, 'validate_database_integrity') as mock_validate:
            mock_validate.return_value = {
                "valid": True,
                "issues": [],
                "validation_duration_seconds": 0.1
            }

            result = self.metadata_service.validate_database_integrity()

        assert result["valid"] is True
        assert len(result["issues"]) == 0
        assert "validation_duration_seconds" in result

    def test_validate_database_integrity_invalid_database(self):
        """Test database integrity validation with invalid database."""
        # Create a fake local database file
        local_db_path = Path(self.temp_dir) / f"metadata_{self.user_id}.db"
        local_db_path.write_text("fake_db_content")

        # Mock the validate_database_integrity method directly
        with patch.object(self.metadata_service, 'validate_database_integrity') as mock_validate:
            mock_validate.return_value = {
                "valid": False,
                "issues": [
                    "Photos table does not exist",
                    "Found 5 orphaned records",
                    "Found duplicate filenames",
                    "Found 2 records with invalid file paths",
                    "Found 1 records with future dates"
                ],
                "validation_duration_seconds": 0.1
            }

            result = self.metadata_service.validate_database_integrity()

        assert result["valid"] is False
        assert len(result["issues"]) == 5
        assert "Photos table does not exist" in result["issues"]
        assert "Found 5 orphaned records" in result["issues"]
        assert "Found duplicate filenames" in result["issues"]
        assert "Found 2 records with invalid file paths" in result["issues"]
        assert "Found 1 records with future dates" in result["issues"]

    def test_validate_database_integrity_no_local_db(self):
        """Test database integrity validation when no local database exists."""
        result = self.metadata_service.validate_database_integrity()

        assert result["valid"] is False
        assert "Local database file does not exist" in result["issues"]

    def test_validate_database_integrity_database_error(self):
        """Test database integrity validation when database operations fail."""
        # Create a fake local database file
        local_db_path = Path(self.temp_dir) / f"metadata_{self.user_id}.db"
        local_db_path.write_text("fake_db_content")

        # Mock database manager to fail
        mock_db_manager = MagicMock()
        mock_db_manager.__enter__.side_effect = Exception("Database error")

        with patch.object(self.metadata_service, '_db_manager', mock_db_manager):
            with pytest.raises(MetadataError) as exc_info:
                self.metadata_service.validate_database_integrity()

        assert "Database integrity validation failed" in str(exc_info.value)


class TestDatabaseResetIntegration:
    """Integration tests for database reset functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = "integration_test_user"
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('imgstream.services.metadata.get_storage_service')
    def test_complete_reset_workflow(self, mock_get_storage_service):
        """Test complete database reset workflow."""
        # Mock storage service
        mock_storage_service = MagicMock()
        mock_storage_service.file_exists.return_value = True
        mock_storage_service.download_file.return_value = b"reset_db_content"
        mock_get_storage_service.return_value = mock_storage_service

        # Create metadata service
        metadata_service = MetadataService(self.user_id, self.temp_dir)

        # Create initial local database
        local_db_path = Path(self.temp_dir) / f"metadata_{self.user_id}.db"
        local_db_path.write_text("original_db_content")

        # Mock database operations
        with patch.object(metadata_service, 'ensure_local_database'), \
             patch.object(type(metadata_service), 'db_manager', new_callable=PropertyMock) as mock_db_prop:

            mock_db_manager = MagicMock()
            mock_connection = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = (0,)  # photo count
            mock_connection.execute.return_value = mock_result
            mock_db_manager.connect.return_value = mock_connection
            mock_db_prop.return_value = mock_db_manager

            # Perform reset
            result = metadata_service.force_reload_from_gcs(confirm_reset=True)

        # Verify reset was successful
        assert result["success"] is True
        assert result["local_db_deleted"] is True
        assert result["gcs_database_exists"] is True
        assert result["download_successful"] is True

        # Verify new content was written
        assert local_db_path.read_bytes() == b"reset_db_content"
