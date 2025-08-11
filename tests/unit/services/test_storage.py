"""
Unit tests for storage service.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from google.cloud.exceptions import GoogleCloudError, NotFound

from src.imgstream.services.storage import StorageError, StorageService, get_storage_service


class TestStorageService:
    """Test cases for StorageService class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.mock_env = {
            "GCS_PHOTOS_BUCKET": "test-photos-bucket",
            "GCS_DATABASE_BUCKET": "test-database-bucket",
            "GOOGLE_CLOUD_PROJECT": "test-project"
        }

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_init_success(self, mock_client_class):
        """Test successful initialization."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_client_class.return_value = mock_client

        service = StorageService()

        assert service.photos_bucket_name == "test-photos-bucket"
        assert service.project_id == "test-project"
        assert service.client == mock_client
        assert service.photos_bucket == mock_bucket
        mock_client_class.assert_called_once_with(project="test-project")

    def test_init_missing_bucket_name(self):
        """Test initialization with missing bucket name."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(StorageError, match="GCS_PHOTOS_BUCKET environment variable is required"):
                StorageService()

    def test_init_missing_project_id(self):
        """Test initialization with missing project ID."""
        with patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket"}, clear=True):
            with pytest.raises(StorageError, match="GOOGLE_CLOUD_PROJECT environment variable is required"):
                StorageService()

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_init_client_error(self, mock_client_class):
        """Test initialization with client error."""
        mock_client_class.side_effect = Exception("Client initialization failed")

        with pytest.raises(StorageError, match="Failed to initialize GCS client"):
            StorageService()

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_user_original_path(self, mock_client_class):
        """Test user original path generation."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Test normal filename
        path = service._get_user_original_path("user123", "photo.jpg")
        assert path == "photos/user123/original/photo.jpg"

        # Test filename with path (should be sanitized)
        path = service._get_user_original_path("user123", "../../../etc/passwd")
        assert path == "photos/user123/original/passwd"

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_user_thumbnail_path(self, mock_client_class):
        """Test user thumbnail path generation."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Test normal filename
        path = service._get_user_thumbnail_path("user123", "photo.jpg")
        assert path == "photos/user123/thumbs/photo_thumb.jpg"

        # Test HEIC filename
        path = service._get_user_thumbnail_path("user123", "photo.heic")
        assert path == "photos/user123/thumbs/photo_thumb.jpg"

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_original_photo_success(self, mock_client_class):
        """Test successful original photo upload."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # First call returns False (file doesn't exist), second call returns True (after upload)
        mock_blob.exists.side_effect = [False, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        file_data = b"fake image data"
        result = service.upload_original_photo("user123", file_data, "photo.jpg")

        assert result["gcs_path"] == "photos/user123/original/photo.jpg"
        assert result["file_size"] == len(file_data)
        assert result["content_type"] == "image/jpeg"
        assert result["was_overwrite"] is False

        mock_bucket.blob.assert_called_once_with("photos/user123/original/photo.jpg")
        mock_blob.upload_from_string.assert_called_once_with(file_data, content_type="image/jpeg")

        # Check metadata was set
        assert mock_blob.metadata["user_id"] == "user123"
        assert mock_blob.metadata["original_filename"] == "photo.jpg"
        assert "uploaded_at" in mock_blob.metadata

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_original_photo_error(self, mock_client_class):
        """Test original photo upload with error."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.upload_from_string.side_effect = GoogleCloudError("Upload failed")
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="Failed to upload original photo"):
            service.upload_original_photo("user123", b"data", "photo.jpg")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_thumbnail_success(self, mock_client_class):
        """Test successful thumbnail upload."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # First call returns False (doesn't exist), second call returns True (after upload)
        mock_blob.exists.side_effect = [False, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        thumbnail_data = b"fake thumbnail data"
        result = service.upload_thumbnail("user123", thumbnail_data, "photo.jpg")

        assert result["gcs_path"] == "photos/user123/thumbs/photo_thumb.jpg"
        assert result["file_size"] == len(thumbnail_data)
        assert result["content_type"] == "image/jpeg"
        assert result["was_overwrite"] is False
        mock_bucket.blob.assert_called_once_with("photos/user123/thumbs/photo_thumb.jpg")
        mock_blob.upload_from_string.assert_called_once_with(thumbnail_data, content_type="image/jpeg")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_download_file_success(self, mock_client_class):
        """Test successful file download."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b"file data"
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.download_file("photos/user123/original/photo.jpg")

        assert result == b"file data"
        mock_blob.exists.assert_called_once()
        mock_blob.download_as_bytes.assert_called_once()

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_download_file_not_found(self, mock_client_class):
        """Test file download when file doesn't exist."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = False
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="File not found"):
            service.download_file("photos/user123/original/nonexistent.jpg")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_signed_url_success(self, mock_client_class):
        """Test successful signed URL generation."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.get_signed_url("photos/user123/original/photo.jpg", expiration=1800)

        assert result == "https://signed-url.example.com"
        mock_blob.generate_signed_url.assert_called_once()

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_delete_file_success(self, mock_client_class):
        """Test successful file deletion."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_client_class.return_value = mock_client

        service = StorageService()

        service.delete_file("photos/user123/original/photo.jpg")

        mock_blob.exists.assert_called_once()
        mock_blob.delete.assert_called_once()

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_delete_file_not_found(self, mock_client_class):
        """Test file deletion when file doesn't exist."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = False
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Should not raise an error
        service.delete_file("photos/user123/original/nonexistent.jpg")

        mock_blob.exists.assert_called_once()
        mock_blob.delete.assert_not_called()

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_list_user_files_success(self, mock_client_class):
        """Test successful user files listing."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()

        # Mock blob objects
        mock_blob1 = MagicMock()
        mock_blob1.name = "photos/user123/original/photo1.jpg"
        mock_blob2 = MagicMock()
        mock_blob2.name = "photos/user123/original/photo2.jpg"

        mock_client.list_blobs.return_value = [mock_blob1, mock_blob2]
        mock_client.bucket.return_value = mock_bucket
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.list_user_files("user123", "original/")

        assert result == ["photos/user123/original/photo1.jpg", "photos/user123/original/photo2.jpg"]
        mock_client.list_blobs.assert_called_once_with(mock_bucket, prefix="photos/user123/original/")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_content_type(self, mock_client_class):
        """Test content type detection."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = StorageService()

        assert service._get_content_type("photo.jpg") == "image/jpeg"
        assert service._get_content_type("photo.jpeg") == "image/jpeg"
        assert service._get_content_type("photo.heic") == "image/heic"
        assert service._get_content_type("photo.heif") == "image/heif"
        assert service._get_content_type("document.pdf") == "application/octet-stream"

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_check_bucket_exists_success(self, mock_client_class):
        """Test successful bucket existence check."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.check_bucket_exists()

        assert result is True
        mock_bucket.reload.assert_called_once()

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_check_bucket_exists_not_found(self, mock_client_class):
        """Test bucket existence check when bucket doesn't exist."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.reload.side_effect = NotFound("Bucket not found")
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.check_bucket_exists()

        assert result is False


class TestStorageServiceGlobal:
    """Test cases for global storage service functions."""

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_original_photo_with_progress(self, mock_client_class):
        """Test original photo upload with progress callback."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # First call returns False (file doesn't exist), second call returns True (after upload)
        mock_blob.exists.side_effect = [False, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Track progress calls
        progress_calls = []

        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))

        file_data = b"fake image data"
        result = service.upload_original_photo("user123", file_data, "photo.jpg", progress_callback)

        assert result["gcs_path"] == "photos/user123/original/photo.jpg"
        assert len(progress_calls) == 2  # Start and completion
        assert progress_calls[0] == (0, len(file_data), "Starting upload...")
        assert progress_calls[1] == (len(file_data), len(file_data), "Upload completed")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_original_photo_overwrite(self, mock_client_class):
        """Test original photo upload with file overwrite."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True  # File already exists
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        file_data = b"fake image data"
        result = service.upload_original_photo("user123", file_data, "photo.jpg")

        assert result["was_overwrite"] is True

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_multiple_photos_success(self, mock_client_class):
        """Test successful batch photo upload."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # Each photo: first call returns False (file doesn't exist), second call returns True (after upload)
        mock_blob.exists.side_effect = [False, True, False, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        photos = [
            (b"image data 1", "photo1.jpg"),
            (b"image data 2", "photo2.jpg"),
        ]

        # Track progress calls
        progress_calls = []

        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))

        results = service.upload_multiple_photos("user123", photos, progress_callback)

        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert results[0]["filename"] == "photo1.jpg"
        assert results[1]["filename"] == "photo2.jpg"

        # Check progress tracking
        assert len(progress_calls) == 3  # 2 individual + 1 completion
        assert progress_calls[-1][0] == 2  # Final progress

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_multiple_photos_partial_failure(self, mock_client_class):
        """Test batch photo upload with partial failures."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # First photo: exists check returns False, then True after upload
        # Second photo: exists check returns False, then True (but upload will fail)
        mock_blob.exists.side_effect = [False, True, False, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345

        # Make second upload fail by checking the blob path
        def upload_side_effect(data, content_type=None):
            # Get the current blob path from the mock
            current_path = mock_bucket.blob.call_args[0][0] if mock_bucket.blob.call_args else ""
            if "photo2.jpg" in current_path:
                raise GoogleCloudError("Upload failed")

        mock_blob.upload_from_string.side_effect = upload_side_effect
        mock_client_class.return_value = mock_client

        service = StorageService()

        photos = [
            (b"image data 1", "photo1.jpg"),
            (b"image data 2", "photo2.jpg"),
        ]

        results = service.upload_multiple_photos("user123", photos)

        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "error" in results[1]

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_upload_url_success(self, mock_client_class):
        """Test successful upload URL generation."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.generate_signed_url.return_value = "https://upload-url.example.com"
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.get_upload_url("user123", "photo.jpg", expiration=1800)

        assert result == "https://upload-url.example.com"
        mock_blob.generate_signed_url.assert_called_once()
        args, kwargs = mock_blob.generate_signed_url.call_args
        assert kwargs["method"] == "PUT"
        assert kwargs["content_type"] == "image/jpeg"

    @patch("src.imgstream.services.storage._storage_service", None)
    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_storage_service(self, mock_client_class):
        """Test getting global storage service instance."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = get_storage_service()

        assert isinstance(service, StorageService)

        # Should return the same instance
        service2 = get_storage_service()
        assert service is service2


class TestUploadProgress:
    """Test cases for UploadProgress class."""

    def test_upload_progress_initialization(self):
        """Test UploadProgress initialization."""
        from src.imgstream.services.storage import UploadProgress

        progress = UploadProgress(1000, "test.jpg")

        assert progress.total_bytes == 1000
        assert progress.uploaded_bytes == 0
        assert progress.filename == "test.jpg"
        assert progress.status == "pending"
        assert progress.progress_percentage == 0.0

    def test_upload_progress_update(self):
        """Test UploadProgress update functionality."""
        from src.imgstream.services.storage import UploadProgress

        progress = UploadProgress(1000, "test.jpg")
        progress.update(500, "uploading")

        assert progress.uploaded_bytes == 500
        assert progress.status == "uploading"
        assert progress.progress_percentage == 50.0

    def test_upload_progress_to_dict(self):
        """Test UploadProgress dictionary conversion."""
        from src.imgstream.services.storage import UploadProgress

        progress = UploadProgress(1000, "test.jpg")
        progress.update(750, "uploading")

        result = progress.to_dict()

        assert result["filename"] == "test.jpg"
        assert result["total_bytes"] == 1000
        assert result["uploaded_bytes"] == 750
        assert result["progress_percentage"] == 75.0
        assert result["status"] == "uploading"
        assert "elapsed_time" in result
        assert "upload_speed" in result

    def test_upload_progress_speed_calculation(self):
        """Test upload speed calculation."""
        import time

        from src.imgstream.services.storage import UploadProgress

        progress = UploadProgress(1000, "test.jpg")
        time.sleep(0.1)  # Small delay to ensure elapsed time > 0
        progress.update(500, "uploading")

        speed = progress.upload_speed
        assert speed > 0  # Should have some upload speed


class TestThumbnailUpload:
    """Test cases for enhanced thumbnail upload functionality."""

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_multiple_thumbnails_success(self, mock_client_class):
        """Test successful batch thumbnail upload."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # Each thumbnail: first call returns False (doesn't exist), second call returns True (after upload)
        mock_blob.exists.side_effect = [False, True, False, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        thumbnails = [
            (b"thumbnail data 1", "photo1.jpg"),
            (b"thumbnail data 2", "photo2.jpg"),
        ]

        # Track progress calls
        progress_calls = []

        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))

        results = service.upload_multiple_thumbnails("user123", thumbnails, progress_callback)

        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert len(progress_calls) >= 2  # At least start and completion

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_check_thumbnail_exists_true(self, mock_client_class):
        """Test checking existing thumbnail."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.size = 1024
        mock_blob.content_type = "image/jpeg"
        mock_blob.updated = datetime.now()
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_blob.metadata = {"user_id": "user123"}
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.check_thumbnail_exists("user123", "photo.jpg")

        assert result["exists"] is True
        assert result["file_size"] == 1024
        assert result["content_type"] == "image/jpeg"
        assert "updated" in result
        assert result["etag"] == "test-etag"

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_check_thumbnail_exists_false(self, mock_client_class):
        """Test checking non-existing thumbnail."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = False
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.check_thumbnail_exists("user123", "photo.jpg")

        assert result["exists"] is False
        assert "gcs_path" in result

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_thumbnail_with_deduplication_skip(self, mock_client_class):
        """Test thumbnail upload with deduplication - skip duplicate."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.size = 1024  # Same size as new thumbnail
        mock_blob.content_type = "image/jpeg"
        mock_blob.updated = datetime.now()
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_blob.metadata = {"user_id": "user123"}
        mock_client_class.return_value = mock_client

        service = StorageService()

        thumbnail_data = b"x" * 1024  # Same size as existing
        result = service.upload_thumbnail_with_deduplication("user123", thumbnail_data, "photo.jpg")

        assert result["skipped"] is True
        assert result["reason"] == "duplicate_size"
        assert "existing_info" in result

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_thumbnail_with_deduplication_upload(self, mock_client_class):
        """Test thumbnail upload with deduplication - upload different size."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # First exists check returns True (existing), then False and True for upload
        mock_blob.exists.side_effect = [True, False, True]
        mock_blob.size = 512  # Different size from new thumbnail
        mock_blob.content_type = "image/jpeg"
        mock_blob.updated = datetime.now()
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_blob.metadata = {"user_id": "user123"}
        mock_blob.storage_class = "STANDARD"
        mock_client_class.return_value = mock_client

        service = StorageService()

        thumbnail_data = b"x" * 1024  # Different size from existing
        result = service.upload_thumbnail_with_deduplication("user123", thumbnail_data, "photo.jpg")

        assert result["skipped"] is False
        assert result["was_duplicate"] is True
        assert "gcs_path" in result

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_thumbnail_with_deduplication_force_overwrite(self, mock_client_class):
        """Test thumbnail upload with forced overwrite."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # First exists check returns True, then upload sequence
        mock_blob.exists.side_effect = [True, True, True]  # Existing, then upload checks
        mock_blob.size = 1024  # Same size as new thumbnail
        mock_blob.content_type = "image/jpeg"
        mock_blob.updated = datetime.now()
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_blob.metadata = {"user_id": "user123"}
        mock_blob.storage_class = "STANDARD"
        mock_client_class.return_value = mock_client

        service = StorageService()

        thumbnail_data = b"x" * 1024
        result = service.upload_thumbnail_with_deduplication(
            "user123", thumbnail_data, "photo.jpg", force_overwrite=True
        )

        assert result["skipped"] is False
        assert result["was_duplicate"] is True
        mock_blob.upload_from_string.assert_called_once()


class TestSignedUrlGeneration:
    """Test cases for enhanced signed URL generation functionality."""

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_photo_display_url_original(self, mock_client_class):
        """Test generating display URL for original photo."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.size = 2048
        mock_blob.content_type = "image/jpeg"
        mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.get_photo_display_url("user123", "photo.jpg", "original", 3600)

        assert result["signed_url"] == "https://signed-url.example.com"
        assert result["photo_type"] == "original"
        assert result["filename"] == "photo.jpg"
        assert result["user_id"] == "user123"
        assert result["file_size"] == 2048
        assert result["content_type"] == "image/jpeg"
        assert result["expiration_seconds"] == 3600
        assert "expires_at" in result

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_photo_display_url_thumbnail(self, mock_client_class):
        """Test generating display URL for thumbnail."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.size = 512
        mock_blob.content_type = "image/jpeg"
        mock_blob.generate_signed_url.return_value = "https://signed-url-thumb.example.com"
        mock_client_class.return_value = mock_client

        service = StorageService()

        result = service.get_photo_display_url("user123", "photo.jpg", "thumbnail")

        assert result["signed_url"] == "https://signed-url-thumb.example.com"
        assert result["photo_type"] == "thumbnail"
        assert result["gcs_path"] == "photos/user123/thumbs/photo_thumb.jpg"

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_photo_display_url_not_found(self, mock_client_class):
        """Test generating display URL for non-existent photo."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = False
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="Photo not found"):
            service.get_photo_display_url("user123", "nonexistent.jpg", "original")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_photo_display_url_invalid_type(self, mock_client_class):
        """Test generating display URL with invalid photo type."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="Invalid photo_type"):
            service.get_photo_display_url("user123", "photo.jpg", "invalid_type")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_batch_photo_urls_success(self, mock_client_class):
        """Test batch photo URL generation."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.size = 1024
        mock_blob.content_type = "image/jpeg"
        mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"
        mock_client_class.return_value = mock_client

        service = StorageService()

        photo_requests = [
            {"filename": "photo1.jpg", "photo_type": "thumbnail"},
            {"filename": "photo2.jpg", "photo_type": "original"},
        ]

        results = service.get_batch_photo_urls("user123", photo_requests, 1800)

        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert results[0]["filename"] == "photo1.jpg"
        assert results[1]["filename"] == "photo2.jpg"

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_batch_photo_urls_partial_failure(self, mock_client_class):
        """Test batch photo URL generation with partial failures."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # First photo exists, second doesn't
        mock_blob.exists.side_effect = [True, False]
        mock_blob.size = 1024
        mock_blob.content_type = "image/jpeg"
        mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"
        mock_client_class.return_value = mock_client

        service = StorageService()

        photo_requests = [
            {"filename": "photo1.jpg"},
            {"filename": "nonexistent.jpg"},
        ]

        results = service.get_batch_photo_urls("user123", photo_requests)

        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "error" in results[1]

    def test_validate_user_access_valid(self):
        """Test user access validation for valid path."""
        service = StorageService()

        # Valid user path
        valid_path = "photos/user123/original/photo.jpg"
        assert service.validate_user_access("user123", valid_path) is True

    def test_validate_user_access_invalid(self):
        """Test user access validation for invalid path."""
        service = StorageService()

        # Invalid user path (different user)
        invalid_path = "photos/user456/original/photo.jpg"
        assert service.validate_user_access("user123", invalid_path) is False

        # Invalid path format
        invalid_format = "invalid/path/photo.jpg"
        assert service.validate_user_access("user123", invalid_format) is False

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_secure_photo_url_success(self, mock_client_class):
        """Test secure photo URL generation with valid access."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.generate_signed_url.return_value = "https://secure-url.example.com"
        mock_client_class.return_value = mock_client

        service = StorageService()

        gcs_path = "photos/user123/original/photo.jpg"
        result = service.get_secure_photo_url("user123", gcs_path, 3600)

        assert result == "https://secure-url.example.com"

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_secure_photo_url_access_denied(self, mock_client_class):
        """Test secure photo URL generation with access denied."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Try to access another user's photo
        gcs_path = "photos/user456/original/photo.jpg"

        with pytest.raises(StorageError, match="Access denied"):
            service.get_secure_photo_url("user123", gcs_path, 3600)


class TestStorageServiceErrorHandling:
    """Test cases for comprehensive error handling in storage service."""

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_original_photo_gcs_error(self, mock_client_class):
        """Test original photo upload with GCS error."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = False
        mock_blob.upload_from_string.side_effect = GoogleCloudError("GCS service unavailable")
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="Failed to upload original photo"):
            service.upload_original_photo("user123", b"test data", "photo.jpg")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_thumbnail_gcs_error(self, mock_client_class):
        """Test thumbnail upload with GCS error."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = False
        mock_blob.upload_from_string.side_effect = GoogleCloudError("Upload failed")
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="Failed to upload thumbnail"):
            service.upload_thumbnail("user123", b"thumbnail data", "photo.jpg")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_download_file_gcs_error(self, mock_client_class):
        """Test file download with GCS error."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.download_as_bytes.side_effect = GoogleCloudError("Download failed")
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="Failed to download file"):
            service.download_file("photos/user123/original/photo.jpg")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_signed_url_gcs_error(self, mock_client_class):
        """Test signed URL generation with GCS error."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.generate_signed_url.side_effect = GoogleCloudError("URL generation failed")
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="Failed to generate signed URL"):
            service.get_signed_url("photos/user123/original/photo.jpg")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_delete_file_gcs_error(self, mock_client_class):
        """Test file deletion with GCS error."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.delete.side_effect = GoogleCloudError("Delete failed")
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="Failed to delete file"):
            service.delete_file("photos/user123/original/photo.jpg")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_list_user_files_gcs_error(self, mock_client_class):
        """Test file listing with GCS error."""
        mock_client = MagicMock()
        mock_client.list_blobs.side_effect = GoogleCloudError("List failed")
        mock_client_class.return_value = mock_client

        service = StorageService()

        with pytest.raises(StorageError, match="Failed to list files"):
            service.list_user_files("user123")

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_check_bucket_exists_gcs_error(self, mock_client_class):
        """Test bucket existence check with GCS error."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.reload.side_effect = GoogleCloudError("Bucket check failed")
        mock_client_class.return_value = mock_client

        service = StorageService()

        # check_bucket_exists catches exceptions and returns False
        result = service.check_bucket_exists()
        assert result is False


class TestStorageServiceEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_empty_file(self, mock_client_class):
        """Test uploading empty file."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.side_effect = [False, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Empty file should still work
        result = service.upload_original_photo("user123", b"", "empty.jpg")
        assert result["file_size"] == 0

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_large_filename(self, mock_client_class):
        """Test uploading file with very long filename."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.side_effect = [False, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Very long filename
        long_filename = "a" * 200 + ".jpg"
        result = service.upload_original_photo("user123", b"test data", long_filename)
        assert long_filename in result["gcs_path"]

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_upload_special_characters_filename(self, mock_client_class):
        """Test uploading file with special characters in filename."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.side_effect = [False, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Filename with special characters
        special_filename = "test-file_with@special#chars$.jpg"
        result = service.upload_original_photo("user123", b"test data", special_filename)
        assert special_filename in result["gcs_path"]

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_get_content_type_edge_cases(self, mock_client_class):
        """Test content type detection for edge cases."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Test various file extensions
        assert service._get_content_type("photo.jpg") == "image/jpeg"
        assert service._get_content_type("photo.jpeg") == "image/jpeg"
        assert service._get_content_type("photo.JPEG") == "image/jpeg"
        assert service._get_content_type("photo.heic") == "image/heic"
        assert service._get_content_type("photo.HEIC") == "image/heic"
        assert service._get_content_type("photo.png") == "image/png"
        assert service._get_content_type("photo.gif") == "image/gif"
        assert service._get_content_type("photo.webp") == "image/webp"
        assert service._get_content_type("photo.unknown") == "application/octet-stream"
        assert service._get_content_type("photo") == "application/octet-stream"

    def test_upload_progress_edge_cases(self):
        """Test UploadProgress with edge cases."""
        from src.imgstream.services.storage import UploadProgress

        # Zero total bytes
        progress = UploadProgress(0, "empty.jpg")
        assert progress.progress_percentage == 0.0
        progress.update(0, "completed")
        assert progress.progress_percentage == 0.0

        # Negative values (should be handled gracefully)
        progress = UploadProgress(1000, "test.jpg")
        progress.update(-100, "error")  # Negative uploaded bytes
        assert progress.uploaded_bytes == -100
        # Progress percentage should handle this gracefully
        assert progress.progress_percentage >= 0.0

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_batch_operations_empty_list(self, mock_client_class):
        """Test batch operations with empty lists."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Empty photo list for batch upload
        results = service.upload_multiple_photos("user123", [])
        assert results == []

        # Empty thumbnail list for batch upload
        results = service.upload_multiple_thumbnails("user123", [])
        assert results == []

        # Empty photo requests for batch URLs
        results = service.get_batch_photo_urls("user123", [])
        assert results == []


class TestStorageServiceIntegration:
    """Integration tests for storage service functionality."""

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_complete_photo_workflow(self, mock_client_class):
        """Test complete photo upload and access workflow."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        # Multiple exists calls for upload verification and URL generation
        # Original upload: False, True; Thumbnail upload: False, True; URL generation: True, True
        mock_blob.exists.side_effect = [False, True, False, True, True, True]
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_blob.size = 1024
        mock_blob.content_type = "image/jpeg"
        mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"
        mock_client_class.return_value = mock_client

        service = StorageService()

        # 1. Upload original photo
        original_result = service.upload_original_photo("user123", b"original data", "photo.jpg")
        assert original_result["gcs_path"] == "photos/user123/original/photo.jpg"

        # 2. Upload thumbnail
        thumbnail_result = service.upload_thumbnail("user123", b"thumb data", "photo.jpg")
        assert thumbnail_result["gcs_path"] == "photos/user123/thumbs/photo_thumb.jpg"

        # 3. Generate display URLs
        original_url = service.get_photo_display_url("user123", "photo.jpg", "original")
        thumbnail_url = service.get_photo_display_url("user123", "photo.jpg", "thumbnail")

        assert original_url["signed_url"] == "https://signed-url.example.com"
        assert thumbnail_url["signed_url"] == "https://signed-url.example.com"

        # Verify all operations used correct paths
        actual_calls = [call[0][0] for call in mock_bucket.blob.call_args_list]

        # Should contain calls for original and thumbnail paths
        assert "photos/user123/original/photo.jpg" in actual_calls
        assert "photos/user123/thumbs/photo_thumb.jpg" in actual_calls

        # Should have multiple calls (upload + URL generation)
        assert len(actual_calls) >= 4

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_user_isolation_verification(self, mock_client_class):
        """Test that user data isolation is properly enforced."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Test path generation for different users
        user1_original = service._get_user_original_path("user1", "photo.jpg")
        user2_original = service._get_user_original_path("user2", "photo.jpg")
        user1_thumbnail = service._get_user_thumbnail_path("user1", "photo.jpg")
        user2_thumbnail = service._get_user_thumbnail_path("user2", "photo.jpg")

        # Verify paths are user-specific
        assert "user1" in user1_original and "user2" not in user1_original
        assert "user2" in user2_original and "user1" not in user2_original
        assert "user1" in user1_thumbnail and "user2" not in user1_thumbnail
        assert "user2" in user2_thumbnail and "user1" not in user2_thumbnail

        # Test access validation
        assert service.validate_user_access("user1", user1_original) is True
        assert service.validate_user_access("user1", user2_original) is False
        assert service.validate_user_access("user2", user2_original) is True
        assert service.validate_user_access("user2", user1_original) is False

    @patch.dict("os.environ", {"GCS_PHOTOS_BUCKET": "test-photos-bucket", "GCS_DATABASE_BUCKET": "test-database-bucket", "GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("src.imgstream.services.storage.storage.Client")
    def test_concurrent_operations_simulation(self, mock_client_class):
        """Test handling of concurrent-like operations."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.side_effect = [False, True] * 10  # Multiple operations
        mock_blob.storage_class = "STANDARD"
        mock_blob.etag = "test-etag"
        mock_blob.generation = 12345
        mock_client_class.return_value = mock_client

        service = StorageService()

        # Simulate multiple uploads for same user
        results = []
        for i in range(5):
            result = service.upload_original_photo("user123", f"data{i}".encode(), f"photo{i}.jpg")
            results.append(result)

        # All uploads should succeed
        assert len(results) == 5
        assert all("gcs_path" in result for result in results)
        assert all("user123" in result["gcs_path"] for result in results)
