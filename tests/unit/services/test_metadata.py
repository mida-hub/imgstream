"""Tests for metadata service."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.imgstream.services.metadata import (
    MetadataError,
    MetadataService,
    cleanup_metadata_services,
    get_metadata_service,
)
from src.imgstream.services.storage import StorageError


class TestMetadataService:
    """Test cases for MetadataService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.user_id = "test_user_123"

    def teardown_method(self):
        """Clean up test fixtures."""
        cleanup_metadata_services()
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('src.imgstream.services.metadata.get_storage_service')
    def test_init_success(self, mock_get_storage):
        """Test successful initialization."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)

        assert service.user_id == self.user_id
        assert service.temp_dir == Path(self.temp_dir)
        assert service.local_db_path == Path(self.temp_dir) / f"metadata_{self.user_id}.db"
        assert service.gcs_db_path == f"databases/{self.user_id}/metadata.db"
        assert service.storage_service == mock_storage

    @patch('src.imgstream.services.metadata.get_storage_service')
    def test_init_storage_error(self, mock_get_storage):
        """Test initialization with storage service error."""
        mock_get_storage.side_effect = Exception("Storage init failed")

        with pytest.raises(MetadataError, match="Failed to initialize storage service"):
            MetadataService(self.user_id, self.temp_dir)

    @patch('src.imgstream.services.metadata.get_storage_service')
    @patch('src.imgstream.services.metadata.get_database_manager')
    def test_ensure_local_database_exists_locally(self, mock_get_db_manager, mock_get_storage):
        """Test ensure_local_database when database already exists locally."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager

        service = MetadataService(self.user_id, self.temp_dir)
        
        # Create local database file
        service.local_db_path.touch()

        result = service.ensure_local_database()

        assert result is False  # Not downloaded from GCS
        assert service.local_db_path.exists()

    @patch('src.imgstream.services.metadata.get_storage_service')
    @patch('src.imgstream.services.metadata.get_database_manager')
    def test_ensure_local_database_download_from_gcs(self, mock_get_db_manager, mock_get_storage):
        """Test ensure_local_database downloading from GCS."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_file.return_value = b'fake_db_data'
        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.verify_schema.return_value = True

        service = MetadataService(self.user_id, self.temp_dir)

        result = service.ensure_local_database()

        assert result is True  # Downloaded from GCS
        assert service.local_db_path.exists()
        # download_file is called twice: once for existence check, once for actual download
        assert mock_storage.download_file.call_count == 2
        mock_storage.download_file.assert_called_with(service.gcs_db_path)

    @patch('src.imgstream.services.metadata.get_storage_service')
    @patch('src.imgstream.services.metadata.create_database')
    def test_ensure_local_database_create_new(self, mock_create_db, mock_get_storage):
        """Test ensure_local_database creating new database."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_file.side_effect = StorageError("Not found")

        service = MetadataService(self.user_id, self.temp_dir)

        result = service.ensure_local_database()

        assert result is False  # Created new, not downloaded
        mock_create_db.assert_called_once_with(str(service.local_db_path))

    @patch('src.imgstream.services.metadata.get_storage_service')
    def test_gcs_database_exists_true(self, mock_get_storage):
        """Test _gcs_database_exists when database exists."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_file.return_value = b'fake_data'

        service = MetadataService(self.user_id, self.temp_dir)

        result = service._gcs_database_exists()

        assert result is True

    @patch('src.imgstream.services.metadata.get_storage_service')
    def test_gcs_database_exists_false(self, mock_get_storage):
        """Test _gcs_database_exists when database doesn't exist."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_file.side_effect = StorageError("Not found")

        service = MetadataService(self.user_id, self.temp_dir)

        result = service._gcs_database_exists()

        assert result is False

    @patch('src.imgstream.services.metadata.get_storage_service')
    def test_upload_to_gcs_success(self, mock_get_storage):
        """Test successful upload to GCS."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_original_photo.return_value = {'gcs_path': 'test/path'}

        service = MetadataService(self.user_id, self.temp_dir)
        
        # Create local database file with content
        service.local_db_path.write_bytes(b'fake_db_content')

        result = service.upload_to_gcs()

        assert result is True
        mock_storage.upload_original_photo.assert_called_once_with(
            self.user_id, b'fake_db_content', 'metadata.db'
        )

    @patch('src.imgstream.services.metadata.get_storage_service')
    def test_upload_to_gcs_no_local_file(self, mock_get_storage):
        """Test upload to GCS when local file doesn't exist."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)

        with pytest.raises(MetadataError, match="Local database does not exist"):
            service.upload_to_gcs()

    @patch('src.imgstream.services.metadata.get_storage_service')
    @patch('src.imgstream.services.metadata.get_database_manager')
    def test_get_database_info(self, mock_get_db_manager, mock_get_storage):
        """Test getting database information."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_file.side_effect = StorageError("Not found")  # GCS doesn't exist
        
        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.get_table_info.return_value = {'columns': ['id', 'filename']}

        service = MetadataService(self.user_id, self.temp_dir)
        
        # Create local database file
        service.local_db_path.write_bytes(b'fake_db_content')

        info = service.get_database_info()

        assert info['user_id'] == self.user_id
        assert info['local_exists'] is True
        assert info['gcs_exists'] is False
        assert info['local_size'] == len(b'fake_db_content')
        assert 'local_modified' in info
        assert info['table_info'] == {'columns': ['id', 'filename']}

    @patch('src.imgstream.services.metadata.get_storage_service')
    def test_cleanup_local_database(self, mock_get_storage):
        """Test cleanup of local database."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)
        
        # Create local database file
        service.local_db_path.write_bytes(b'fake_db_content')
        assert service.local_db_path.exists()

        service.cleanup_local_database()

        assert not service.local_db_path.exists()

    @patch('src.imgstream.services.metadata.get_storage_service')
    @patch('src.imgstream.services.metadata.get_database_manager')
    def test_context_manager(self, mock_get_db_manager, mock_get_storage):
        """Test context manager functionality."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_file.side_effect = StorageError("Not found")
        
        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager

        service = MetadataService(self.user_id, self.temp_dir)

        with patch.object(service, 'ensure_local_database') as mock_ensure:
            with service as ctx_service:
                assert ctx_service == service
                mock_ensure.assert_called_once()

        # Close is called on the database manager if it exists
        if service._db_manager:
            mock_db_manager.close.assert_called()


class TestMetadataServiceGlobal:
    """Test cases for global metadata service functions."""

    def teardown_method(self):
        """Clean up after each test."""
        cleanup_metadata_services()

    @patch('src.imgstream.services.metadata.MetadataService')
    def test_get_metadata_service(self, mock_metadata_service_class):
        """Test getting metadata service instance."""
        mock_service = MagicMock()
        mock_metadata_service_class.return_value = mock_service

        user_id = "test_user"
        service = get_metadata_service(user_id)

        assert service == mock_service
        mock_metadata_service_class.assert_called_once_with(user_id, "/tmp")

        # Second call should return same instance
        service2 = get_metadata_service(user_id)
        assert service2 == mock_service
        # Should not create new instance
        assert mock_metadata_service_class.call_count == 1

    @patch('src.imgstream.services.metadata.MetadataService')
    def test_cleanup_metadata_services(self, mock_metadata_service_class):
        """Test cleanup of all metadata services."""
        mock_service1 = MagicMock()
        mock_service2 = MagicMock()
        mock_service3 = MagicMock()
        mock_metadata_service_class.side_effect = [mock_service1, mock_service2, mock_service3]

        # Create services for two users
        get_metadata_service("user1")
        get_metadata_service("user2")

        cleanup_metadata_services()

        mock_service1.cleanup_local_database.assert_called_once()
        mock_service2.cleanup_local_database.assert_called_once()

        # Services should be cleared
        # Next call should create new instance
        get_metadata_service("user1")
        assert mock_metadata_service_class.call_count == 3


class TestMetadataServiceErrorHandling:
    """Test cases for error handling in metadata service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.user_id = "test_user_123"

    def teardown_method(self):
        """Clean up test fixtures."""
        cleanup_metadata_services()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('src.imgstream.services.metadata.get_storage_service')
    def test_download_from_gcs_partial_failure(self, mock_get_storage):
        """Test download from GCS with partial failure cleanup."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        # First call (existence check) succeeds, second call (download) fails
        mock_storage.download_file.side_effect = [b'fake_data', Exception("Download failed")]

        service = MetadataService(self.user_id, self.temp_dir)

        with pytest.raises(MetadataError, match="Failed to download database from GCS"):
            service._download_from_gcs()

        # Should not leave partial file
        assert not service.local_db_path.exists()

    @patch('src.imgstream.services.metadata.get_storage_service')
    @patch('src.imgstream.services.metadata.create_database')
    def test_create_new_database_failure_cleanup(self, mock_create_db, mock_get_storage):
        """Test create new database with failure cleanup."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_create_db.side_effect = Exception("Create failed")

        service = MetadataService(self.user_id, self.temp_dir)

        with pytest.raises(MetadataError, match="Failed to create new database"):
            service._create_new_database()

        # Should not leave partial file
        assert not service.local_db_path.exists()

    @patch('src.imgstream.services.metadata.get_storage_service')
    @patch('src.imgstream.services.metadata.get_database_manager')
    def test_verify_database_integrity_failure(self, mock_get_db_manager, mock_get_storage):
        """Test database integrity verification failure."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        
        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.verify_schema.return_value = False

        service = MetadataService(self.user_id, self.temp_dir)

        with pytest.raises(MetadataError, match="Database schema verification failed"):
            service._verify_database_integrity()
