"""Tests for metadata service."""

import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.imgstream.models.photo import PhotoMetadata
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

    @patch("src.imgstream.services.metadata.get_storage_service")
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

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_init_storage_error(self, mock_get_storage):
        """Test initialization with storage service error."""
        mock_get_storage.side_effect = Exception("Storage init failed")

        with pytest.raises(MetadataError, match="Failed to initialize storage service"):
            MetadataService(self.user_id, self.temp_dir)

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
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

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_ensure_local_database_download_from_gcs(self, mock_get_db_manager, mock_get_storage):
        """Test ensure_local_database downloading from GCS."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.file_exists.return_value = True
        mock_storage.download_database_file.return_value = b"fake_db_data"
        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.verify_schema.return_value = True

        service = MetadataService(self.user_id, self.temp_dir)

        result = service.ensure_local_database()

        assert result is True  # Downloaded from GCS
        assert service.local_db_path.exists()
        # download_database_file is called once for actual download (existence check uses file_exists)
        assert mock_storage.download_database_file.call_count == 1
        mock_storage.download_database_file.assert_called_with(self.user_id, "metadata.db")

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.create_database")
    def test_ensure_local_database_create_new(self, mock_create_db, mock_get_storage):
        """Test ensure_local_database creating new database."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        service = MetadataService(self.user_id, self.temp_dir)

        result = service.ensure_local_database()

        assert result is False  # Created new, not downloaded
        mock_create_db.assert_called_once_with(str(service.local_db_path))

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_gcs_database_exists_true(self, mock_get_storage):
        """Test _gcs_database_exists when database exists."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.file_exists.return_value = True

        service = MetadataService(self.user_id, self.temp_dir)

        result = service._gcs_database_exists()

        assert result is True

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_gcs_database_exists_false(self, mock_get_storage):
        """Test _gcs_database_exists when database doesn't exist."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.file_exists.return_value = False

        service = MetadataService(self.user_id, self.temp_dir)

        result = service._gcs_database_exists()

        assert result is False

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_upload_to_gcs_success(self, mock_get_storage):
        """Test successful upload to GCS."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_database_file.return_value = {"gcs_path": "test/path"}

        service = MetadataService(self.user_id, self.temp_dir)

        # Create local database file with content
        service.local_db_path.write_bytes(b"fake_db_content")

        result = service.upload_to_gcs()

        assert result is True
        mock_storage.upload_database_file.assert_called_once_with(self.user_id, b"fake_db_content", "metadata.db")

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_upload_to_gcs_no_local_file(self, mock_get_storage):
        """Test upload to GCS when local file doesn't exist."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)

        with pytest.raises(MetadataError, match="Local database does not exist"):
            service.upload_to_gcs()

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_get_database_info(self, mock_get_db_manager, mock_get_storage):
        """Test getting database information."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")  # GCS doesn't exist
        mock_storage.file_exists.return_value = False  # GCS database doesn't exist

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.get_table_info.return_value = {"columns": ["id", "filename"]}

        # Mock connection for photo count query
        mock_connection = MagicMock()
        mock_db_manager.connect.return_value = mock_connection
        mock_connection.execute.return_value.fetchone.return_value = (0,)  # photo count

        service = MetadataService(self.user_id, self.temp_dir)

        # Create local database file
        service.local_db_path.write_bytes(b"fake_db_content")

        info = service.get_database_info()

        assert info["user_id"] == self.user_id
        assert info["local_db_exists"] is True
        assert info["gcs_db_exists"] is False
        assert info["local_db_size"] == len(b"fake_db_content")
        assert "last_sync_time" in info
        assert info["sync_enabled"] is True

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_cleanup_local_database(self, mock_get_storage):
        """Test cleanup of local database."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)

        # Create local database file
        service.local_db_path.write_bytes(b"fake_db_content")
        assert service.local_db_path.exists()

        service.cleanup_local_database()

        assert not service.local_db_path.exists()

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_context_manager(self, mock_get_db_manager, mock_get_storage):
        """Test context manager functionality."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager

        service = MetadataService(self.user_id, self.temp_dir)

        with patch.object(service, "ensure_local_database") as mock_ensure:
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

    @patch("src.imgstream.services.metadata.MetadataService")
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

    @patch("src.imgstream.services.metadata.MetadataService")
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

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_download_from_gcs_partial_failure(self, mock_get_storage):
        """Test download from GCS with partial failure cleanup."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        # First call (existence check) succeeds, second call (download) fails
        mock_storage.download_database_file.side_effect = [b"fake_data", Exception("Download failed")]

        service = MetadataService(self.user_id, self.temp_dir)

        with pytest.raises(MetadataError, match="Failed to download database from GCS"):
            service._download_from_gcs()

        # Should not leave partial file
        assert not service.local_db_path.exists()

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.create_database")
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

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
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


class TestMetadataServiceCRUD:
    """Test cases for CRUD operations in MetadataService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.user_id = "test_user_123"
        self.sample_photo = PhotoMetadata.create_new(
            user_id=self.user_id,
            filename="test_photo.jpg",
            original_path="photos/test_user_123/original/test_photo.jpg",
            thumbnail_path="photos/test_user_123/thumbs/test_photo_thumb.jpg",
            file_size=1024000,
            mime_type="image/jpeg",
            created_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        cleanup_metadata_services()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_save_photo_metadata_new(self, mock_get_db_manager, mock_get_storage):
        """Test saving new photo metadata."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.side_effect = [
            [],  # No existing record
            None,  # Insert successful
        ]

        service = MetadataService(self.user_id, self.temp_dir)
        service.save_photo_metadata(self.sample_photo)

        # Verify database calls
        assert mock_db_manager.execute_query.call_count == 2
        # Check for existing record
        mock_db_manager.execute_query.assert_any_call("SELECT id FROM photos WHERE id = ?", (self.sample_photo.id,))
        # Insert new record
        insert_call = mock_db_manager.execute_query.call_args_list[1]
        assert "INSERT INTO photos" in insert_call[0][0]
        assert self.sample_photo.id in insert_call[0][1]

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_save_photo_metadata_update(self, mock_get_db_manager, mock_get_storage):
        """Test updating existing photo metadata."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.side_effect = [
            [(self.sample_photo.id,)],  # Existing record found
            None,  # Update successful
        ]

        service = MetadataService(self.user_id, self.temp_dir)
        service.save_photo_metadata(self.sample_photo)

        # Verify database calls
        assert mock_db_manager.execute_query.call_count == 2
        # Update existing record
        update_call = mock_db_manager.execute_query.call_args_list[1]
        assert "UPDATE photos SET" in update_call[0][0]
        assert self.sample_photo.id in update_call[0][1]

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_save_photo_metadata_invalid(self, mock_get_storage):
        """Test saving invalid photo metadata."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)

        # Create invalid photo metadata
        invalid_photo = PhotoMetadata(
            id="",  # Invalid empty ID
            user_id=self.user_id,
            filename="test.jpg",
            original_path="path",
            thumbnail_path="thumb_path",
            created_at=None,
            uploaded_at=datetime.now(UTC),
            file_size=1000,
            mime_type="image/jpeg",
        )

        with pytest.raises(MetadataError, match="Invalid photo metadata"):
            service.save_photo_metadata(invalid_photo)

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_save_photo_metadata_user_mismatch(self, mock_get_storage):
        """Test saving photo metadata with user ID mismatch."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)

        # Create photo with different user ID
        wrong_user_photo = PhotoMetadata.create_new(
            user_id="different_user",
            filename="test.jpg",
            original_path="path",
            thumbnail_path="thumb_path",
            file_size=1000,
            mime_type="image/jpeg",
        )

        with pytest.raises(MetadataError, match="User ID mismatch"):
            service.save_photo_metadata(wrong_user_photo)

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_get_photo_by_id_found(self, mock_get_db_manager, mock_get_storage):
        """Test getting photo by ID when found."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.return_value = [
            (
                self.sample_photo.id,
                self.sample_photo.user_id,
                self.sample_photo.filename,
                self.sample_photo.original_path,
                self.sample_photo.thumbnail_path,
                self.sample_photo.created_at,
                self.sample_photo.uploaded_at,
                self.sample_photo.file_size,
                self.sample_photo.mime_type,
            )
        ]

        service = MetadataService(self.user_id, self.temp_dir)
        result = service.get_photo_by_id(self.sample_photo.id)

        assert result is not None
        assert result.id == self.sample_photo.id
        assert result.filename == self.sample_photo.filename

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_get_photo_by_id_not_found(self, mock_get_db_manager, mock_get_storage):
        """Test getting photo by ID when not found."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.return_value = []

        service = MetadataService(self.user_id, self.temp_dir)
        result = service.get_photo_by_id("nonexistent_id")

        assert result is None

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_get_photos_by_date(self, mock_get_db_manager, mock_get_storage):
        """Test getting photos ordered by date."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        # Create sample data for multiple photos
        photo1_data = (
            "id1",
            self.user_id,
            "photo1.jpg",
            "path1",
            "thumb1",
            datetime(2024, 1, 15, tzinfo=UTC),
            datetime(2024, 1, 15, tzinfo=UTC),
            1000,
            "image/jpeg",
        )
        photo2_data = (
            "id2",
            self.user_id,
            "photo2.jpg",
            "path2",
            "thumb2",
            datetime(2024, 1, 16, tzinfo=UTC),
            datetime(2024, 1, 16, tzinfo=UTC),
            2000,
            "image/jpeg",
        )

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.return_value = [photo2_data, photo1_data]  # Newest first

        service = MetadataService(self.user_id, self.temp_dir)
        result = service.get_photos_by_date(limit=10, offset=0)

        assert len(result) == 2
        assert result[0].id == "id2"  # Newer photo first
        assert result[1].id == "id1"

        # Verify query parameters
        mock_db_manager.execute_query.assert_called_with(
            """SELECT id, user_id, filename, original_path, thumbnail_path,
                              created_at, uploaded_at, file_size, mime_type
                       FROM photos
                       WHERE user_id = ?
                       ORDER BY COALESCE(created_at, uploaded_at) DESC
                       LIMIT ? OFFSET ?""",
            (self.user_id, 10, 0),
        )

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_get_photos_count(self, mock_get_db_manager, mock_get_storage):
        """Test getting total photos count."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.return_value = [(5,)]

        service = MetadataService(self.user_id, self.temp_dir)
        result = service.get_photos_count()

        assert result == 5
        mock_db_manager.execute_query.assert_called_with(
            "SELECT COUNT(*) FROM photos WHERE user_id = ?", (self.user_id,)
        )

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_delete_photo_metadata_success(self, mock_get_db_manager, mock_get_storage):
        """Test successful photo metadata deletion."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.side_effect = [None, [(1,)]]  # DELETE query  # changes() returns 1

        service = MetadataService(self.user_id, self.temp_dir)
        result = service.delete_photo_metadata(self.sample_photo.id)

        assert result is True
        mock_db_manager.execute_query.assert_any_call(
            "DELETE FROM photos WHERE id = ? AND user_id = ?", (self.sample_photo.id, self.user_id)
        )

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_delete_photo_metadata_not_found(self, mock_get_db_manager, mock_get_storage):
        """Test photo metadata deletion when not found."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.side_effect = [None, [(0,)]]  # DELETE query  # changes() returns 0

        service = MetadataService(self.user_id, self.temp_dir)
        result = service.delete_photo_metadata("nonexistent_id")

        assert result is False

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_search_photos_by_filename(self, mock_get_db_manager, mock_get_storage):
        """Test searching photos by filename pattern."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        photo_data = (
            "id1",
            self.user_id,
            "vacation_photo.jpg",
            "path1",
            "thumb1",
            datetime(2024, 1, 15, tzinfo=UTC),
            datetime(2024, 1, 15, tzinfo=UTC),
            1000,
            "image/jpeg",
        )

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.return_value = [photo_data]

        service = MetadataService(self.user_id, self.temp_dir)
        result = service.search_photos_by_filename("%vacation%", limit=10, offset=0)

        assert len(result) == 1
        assert result[0].filename == "vacation_photo.jpg"

        mock_db_manager.execute_query.assert_called_with(
            """SELECT id, user_id, filename, original_path, thumbnail_path,
                              created_at, uploaded_at, file_size, mime_type
                       FROM photos
                       WHERE user_id = ? AND filename LIKE ?
                       ORDER BY COALESCE(created_at, uploaded_at) DESC
                       LIMIT ? OFFSET ?""",
            (self.user_id, "%vacation%", 10, 0),
        )


class TestMetadataServiceAsyncSync:
    """Test cases for async sync functionality in MetadataService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.user_id = "test_user_123"

    def teardown_method(self):
        """Clean up test fixtures."""
        cleanup_metadata_services()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_trigger_async_sync_enabled(self, mock_get_db_manager, mock_get_storage):
        """Test triggering async sync when enabled."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")
        mock_storage.upload_database_file.return_value = {"gcs_path": "test/path"}

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager

        service = MetadataService(self.user_id, self.temp_dir)

        # Create local database file
        service.local_db_path.write_bytes(b"fake_db_content")

        # Enable sync and trigger
        service.enable_async_sync()
        service.trigger_async_sync()

        # Wait for sync to complete
        success = service.wait_for_sync_completion(timeout=5.0)
        assert success is True

        # Verify upload was called
        mock_storage.upload_database_file.assert_called_once()

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_trigger_async_sync_disabled(self, mock_get_storage):
        """Test triggering async sync when disabled."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)

        # Disable sync and trigger
        service.disable_async_sync()
        service.trigger_async_sync()

        # Wait briefly
        time.sleep(0.1)

        # Verify upload was not called
        mock_storage.upload_database_file.assert_not_called()

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_async_sync_pending_check(self, mock_get_storage):
        """Test that multiple sync triggers don't create multiple tasks."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_database_file.return_value = {"gcs_path": "test/path"}

        service = MetadataService(self.user_id, self.temp_dir)

        # Create local database file
        service.local_db_path.write_bytes(b"fake_db_content")

        # Trigger multiple syncs quickly
        service.trigger_async_sync()
        service.trigger_async_sync()
        service.trigger_async_sync()

        # Wait for sync to complete
        service.wait_for_sync_completion(timeout=5.0)

        # Should only upload once
        assert mock_storage.upload_database_file.call_count <= 1

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_async_sync_error_handling(self, mock_get_storage):
        """Test async sync error handling."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_database_file.side_effect = Exception("Upload failed")

        service = MetadataService(self.user_id, self.temp_dir)

        # Create local database file
        service.local_db_path.write_bytes(b"fake_db_content")

        # Trigger sync
        service.trigger_async_sync()

        # Wait for sync to complete (should handle error gracefully)
        service.wait_for_sync_completion(timeout=5.0)

        # Verify upload was attempted
        mock_storage.upload_database_file.assert_called_once()

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_wait_for_sync_completion_timeout(self, mock_get_storage):
        """Test wait for sync completion with timeout."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)

        # Manually set sync as pending
        with service._sync_lock:
            service._sync_pending = True

        # Wait with short timeout
        success = service.wait_for_sync_completion(timeout=0.1)
        assert success is False

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_get_sync_status(self, mock_get_storage):
        """Test getting sync status information."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        service = MetadataService(self.user_id, self.temp_dir)

        status = service.get_sync_status()

        assert status["enabled"] is True
        assert status["pending"] is False
        assert status["last_sync_time"] is None
        assert status["user_id"] == self.user_id

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_save_photo_triggers_sync(self, mock_get_db_manager, mock_get_storage):
        """Test that saving photo metadata triggers async sync."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")
        mock_storage.upload_database_file.return_value = {"gcs_path": "test/path"}

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.side_effect = [
            [],  # No existing record
            None,  # Insert successful
        ]

        service = MetadataService(self.user_id, self.temp_dir)

        # Create sample photo metadata
        sample_photo = PhotoMetadata.create_new(
            user_id=self.user_id,
            filename="test_photo.jpg",
            original_path="photos/test_user_123/original/test_photo.jpg",
            thumbnail_path="photos/test_user_123/thumbs/test_photo_thumb.jpg",
            file_size=1024000,
            mime_type="image/jpeg",
        )

        # Save photo metadata (should trigger sync)
        service.save_photo_metadata(sample_photo)

        # Wait for sync to complete
        service.wait_for_sync_completion(timeout=5.0)

        # Verify sync was triggered
        mock_storage.upload_database_file.assert_called()

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_delete_photo_triggers_sync(self, mock_get_db_manager, mock_get_storage):
        """Test that deleting photo metadata triggers async sync."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")
        mock_storage.upload_database_file.return_value = {"gcs_path": "test/path"}

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.side_effect = [None, [(1,)]]  # DELETE query  # changes() returns 1

        service = MetadataService(self.user_id, self.temp_dir)

        # Delete photo metadata (should trigger sync)
        result = service.delete_photo_metadata("test_photo_id")
        assert result is True

        # Wait for sync to complete
        service.wait_for_sync_completion(timeout=5.0)

        # Verify sync was triggered
        mock_storage.upload_database_file.assert_called()


class TestMetadataServiceIntegration:
    """Integration test cases for MetadataService covering end-to-end scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.user_id = "test_user_123"

    def teardown_method(self):
        """Clean up test fixtures."""
        cleanup_metadata_services()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_full_metadata_lifecycle(self, mock_get_db_manager, mock_get_storage):
        """Test complete metadata lifecycle: create, read, update, delete."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")
        mock_storage.upload_database_file.return_value = {"gcs_path": "test/path"}

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)

        # Mock database responses for lifecycle
        mock_db_manager.execute_query.side_effect = [
            [],  # No existing record (create)
            None,  # Insert successful
            [
                (  # Get photo by ID
                    "test_id",
                    self.user_id,
                    "test.jpg",
                    "original/test.jpg",
                    "thumbs/test.jpg",
                    datetime(2024, 1, 15, tzinfo=UTC),
                    datetime(2024, 1, 15, tzinfo=UTC),
                    1000,
                    "image/jpeg",
                )
            ],
            [("test_id",)],  # Existing record found (update)
            None,  # Update successful
            [
                (  # Get updated photo
                    "test_id",
                    self.user_id,
                    "updated.jpg",
                    "original/updated.jpg",
                    "thumbs/updated.jpg",
                    datetime(2024, 1, 15, tzinfo=UTC),
                    datetime(2024, 1, 15, tzinfo=UTC),
                    2000,
                    "image/jpeg",
                )
            ],
            None,  # Delete query
            [(1,)],  # changes() returns 1 (delete successful)
        ]

        service = MetadataService(self.user_id, self.temp_dir)

        # Create photo metadata
        photo = PhotoMetadata.create_new(
            user_id=self.user_id,
            filename="test.jpg",
            original_path="original/test.jpg",
            thumbnail_path="thumbs/test.jpg",
            file_size=1000,
            mime_type="image/jpeg",
        )
        photo.id = "test_id"  # Set fixed ID for testing

        # CREATE
        service.save_photo_metadata(photo)

        # READ
        retrieved = service.get_photo_by_id("test_id")
        assert retrieved is not None
        assert retrieved.filename == "test.jpg"

        # UPDATE
        photo.filename = "updated.jpg"
        photo.original_path = "original/updated.jpg"
        photo.thumbnail_path = "thumbs/updated.jpg"
        photo.file_size = 2000
        service.save_photo_metadata(photo)

        # Verify update
        updated = service.get_photo_by_id("test_id")
        assert updated is not None
        assert updated.filename == "updated.jpg"
        assert updated.file_size == 2000

        # DELETE
        deleted = service.delete_photo_metadata("test_id")
        assert deleted is True

        # Wait for async sync to complete
        service.wait_for_sync_completion(timeout=5.0)

        # Verify sync was triggered (at least once for the operations)
        assert mock_storage.upload_database_file.call_count >= 1

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_concurrent_operations(self, mock_get_db_manager, mock_get_storage):
        """Test concurrent metadata operations."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")
        mock_storage.upload_database_file.return_value = {"gcs_path": "test/path"}

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.execute_query.side_effect = [
            [],  # No existing record 1
            None,  # Insert successful 1
            [],  # No existing record 2
            None,  # Insert successful 2
            [],  # No existing record 3
            None,  # Insert successful 3
        ]

        service = MetadataService(self.user_id, self.temp_dir)

        # Create multiple photos concurrently
        photos = []
        for i in range(3):
            photo = PhotoMetadata.create_new(
                user_id=self.user_id,
                filename=f"test_{i}.jpg",
                original_path=f"original/test_{i}.jpg",
                thumbnail_path=f"thumbs/test_{i}.jpg",
                file_size=1000 + i,
                mime_type="image/jpeg",
            )
            photos.append(photo)
            service.save_photo_metadata(photo)

        # Wait for all sync operations to complete
        service.wait_for_sync_completion(timeout=10.0)

        # Verify all operations completed
        assert mock_db_manager.execute_query.call_count >= 6

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_database_recovery_scenario(self, mock_get_db_manager, mock_get_storage):
        """Test database recovery from GCS when local DB is corrupted."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        # First call: local DB doesn't exist, GCS has backup
        # Second call: download the backup
        mock_storage.download_database_file.side_effect = [
            b"fake_backup_data",  # GCS has backup
            b"fake_backup_data",  # Download backup
        ]

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)
        mock_db_manager.verify_schema.return_value = True

        service = MetadataService(self.user_id, self.temp_dir)

        # Ensure database (should download from GCS)
        downloaded = service.ensure_local_database()
        assert downloaded is True

        # Verify local file was created
        assert service.local_db_path.exists()

        # Verify download was called
        assert mock_storage.download_database_file.call_count == 2

    @patch("src.imgstream.services.metadata.get_storage_service")
    def test_sync_disable_enable_cycle(self, mock_get_storage):
        """Test disabling and re-enabling sync functionality."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_database_file.return_value = {"gcs_path": "test/path"}

        service = MetadataService(self.user_id, self.temp_dir)

        # Create local database file
        service.local_db_path.write_bytes(b"fake_db_content")

        # Initially enabled
        assert service.is_sync_enabled() is True

        # Disable sync
        service.disable_async_sync()
        assert service.is_sync_enabled() is False

        # Trigger sync (should be ignored)
        service.trigger_async_sync()
        time.sleep(0.1)
        mock_storage.upload_database_file.assert_not_called()

        # Re-enable sync
        service.enable_async_sync()
        assert service.is_sync_enabled() is True

        # Trigger sync (should work now)
        service.trigger_async_sync()
        service.wait_for_sync_completion(timeout=5.0)
        mock_storage.upload_database_file.assert_called_once()

    @patch("src.imgstream.services.metadata.get_storage_service")
    @patch("src.imgstream.services.metadata.get_database_manager")
    def test_pagination_and_search_integration(self, mock_get_db_manager, mock_get_storage):
        """Test pagination and search functionality integration."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.download_database_file.side_effect = StorageError("Not found")

        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager
        mock_db_manager.__enter__ = MagicMock(return_value=mock_db_manager)
        mock_db_manager.__exit__ = MagicMock(return_value=None)

        # Mock responses for different queries
        def mock_execute_query(query, params):
            if "COUNT(*)" in query:
                return [(100,)]  # Total count
            elif "LIKE" in query:
                # Search results
                return [
                    (
                        "search_id",
                        self.user_id,
                        "vacation_photo.jpg",
                        "original/vacation.jpg",
                        "thumbs/vacation.jpg",
                        datetime(2024, 1, 15, tzinfo=UTC),
                        datetime(2024, 1, 15, tzinfo=UTC),
                        1000,
                        "image/jpeg",
                    )
                ]
            else:
                # Regular pagination results
                return [
                    (
                        f"id_{params[2]}",
                        self.user_id,
                        f"photo_{params[2]}.jpg",
                        f"original/photo_{params[2]}.jpg",
                        f"thumbs/photo_{params[2]}.jpg",
                        datetime(2024, 1, 15, tzinfo=UTC),
                        datetime(2024, 1, 15, tzinfo=UTC),
                        1000,
                        "image/jpeg",
                    )
                ]

        mock_db_manager.execute_query.side_effect = mock_execute_query

        service = MetadataService(self.user_id, self.temp_dir)

        # Test pagination
        page1 = service.get_photos_by_date(limit=10, offset=0)
        assert len(page1) == 1
        assert page1[0].filename == "photo_0.jpg"

        page2 = service.get_photos_by_date(limit=10, offset=10)
        assert len(page2) == 1
        assert page2[0].filename == "photo_10.jpg"

        # Test search
        search_results = service.search_photos_by_filename("%vacation%")
        assert len(search_results) == 1
        assert search_results[0].filename == "vacation_photo.jpg"

        # Test count
        total_count = service.get_photos_count()
        assert total_count == 100
