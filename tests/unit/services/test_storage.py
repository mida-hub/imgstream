"""
Unit tests for storage service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, Mock
from google.cloud.exceptions import GoogleCloudError, NotFound

from src.imgstream.services.storage import (
    StorageService,
    StorageError,
    get_storage_service
)


class TestStorageService:
    """Test cases for StorageService class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.mock_env = {
            'GCS_BUCKET': 'test-bucket',
            'GOOGLE_CLOUD_PROJECT': 'test-project'
        }

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_init_success(self, mock_client_class):
        """Test successful initialization."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_client_class.return_value = mock_client
        
        service = StorageService()
        
        assert service.bucket_name == 'test-bucket'
        assert service.project_id == 'test-project'
        assert service.client == mock_client
        assert service.bucket == mock_bucket
        mock_client_class.assert_called_once_with(project='test-project')

    def test_init_missing_bucket_name(self):
        """Test initialization with missing bucket name."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(StorageError, match="GCS_BUCKET environment variable is required"):
                StorageService()

    def test_init_missing_project_id(self):
        """Test initialization with missing project ID."""
        with patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket'}, clear=True):
            with pytest.raises(StorageError, match="GOOGLE_CLOUD_PROJECT environment variable is required"):
                StorageService()

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_init_client_error(self, mock_client_class):
        """Test initialization with client error."""
        mock_client_class.side_effect = Exception("Client initialization failed")
        
        with pytest.raises(StorageError, match="Failed to initialize GCS client"):
            StorageService()

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_get_user_original_path(self, mock_client_class):
        """Test user original path generation."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        service = StorageService()
        
        # Test normal filename
        path = service._get_user_original_path('user123', 'photo.jpg')
        assert path == 'photos/user123/original/photo.jpg'
        
        # Test filename with path (should be sanitized)
        path = service._get_user_original_path('user123', '../../../etc/passwd')
        assert path == 'photos/user123/original/passwd'

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_get_user_thumbnail_path(self, mock_client_class):
        """Test user thumbnail path generation."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        service = StorageService()
        
        # Test normal filename
        path = service._get_user_thumbnail_path('user123', 'photo.jpg')
        assert path == 'photos/user123/thumbs/photo_thumb.jpg'
        
        # Test HEIC filename
        path = service._get_user_thumbnail_path('user123', 'photo.heic')
        assert path == 'photos/user123/thumbs/photo_thumb.jpg'

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_upload_original_photo_success(self, mock_client_class):
        """Test successful original photo upload."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_client_class.return_value = mock_client
        
        service = StorageService()
        
        file_data = b'fake image data'
        result = service.upload_original_photo('user123', file_data, 'photo.jpg')
        
        assert result == 'photos/user123/original/photo.jpg'
        mock_bucket.blob.assert_called_once_with('photos/user123/original/photo.jpg')
        mock_blob.upload_from_string.assert_called_once_with(
            file_data,
            content_type='image/jpeg'
        )
        
        # Check metadata was set
        assert mock_blob.metadata['user_id'] == 'user123'
        assert mock_blob.metadata['original_filename'] == 'photo.jpg'
        assert 'uploaded_at' in mock_blob.metadata

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
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
            service.upload_original_photo('user123', b'data', 'photo.jpg')

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_upload_thumbnail_success(self, mock_client_class):
        """Test successful thumbnail upload."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_client_class.return_value = mock_client
        
        service = StorageService()
        
        thumbnail_data = b'fake thumbnail data'
        result = service.upload_thumbnail('user123', thumbnail_data, 'photo.jpg')
        
        assert result == 'photos/user123/thumbs/photo_thumb.jpg'
        mock_bucket.blob.assert_called_once_with('photos/user123/thumbs/photo_thumb.jpg')
        mock_blob.upload_from_string.assert_called_once_with(
            thumbnail_data,
            content_type='image/jpeg'
        )

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_download_file_success(self, mock_client_class):
        """Test successful file download."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b'file data'
        mock_client_class.return_value = mock_client
        
        service = StorageService()
        
        result = service.download_file('photos/user123/original/photo.jpg')
        
        assert result == b'file data'
        mock_blob.exists.assert_called_once()
        mock_blob.download_as_bytes.assert_called_once()

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
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
            service.download_file('photos/user123/original/nonexistent.jpg')

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_get_signed_url_success(self, mock_client_class):
        """Test successful signed URL generation."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.generate_signed_url.return_value = 'https://signed-url.example.com'
        mock_client_class.return_value = mock_client
        
        service = StorageService()
        
        result = service.get_signed_url('photos/user123/original/photo.jpg', expiration=1800)
        
        assert result == 'https://signed-url.example.com'
        mock_blob.generate_signed_url.assert_called_once()

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
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
        
        service.delete_file('photos/user123/original/photo.jpg')
        
        mock_blob.exists.assert_called_once()
        mock_blob.delete.assert_called_once()

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
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
        service.delete_file('photos/user123/original/nonexistent.jpg')
        
        mock_blob.exists.assert_called_once()
        mock_blob.delete.assert_not_called()

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_list_user_files_success(self, mock_client_class):
        """Test successful user files listing."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        
        # Mock blob objects
        mock_blob1 = MagicMock()
        mock_blob1.name = 'photos/user123/original/photo1.jpg'
        mock_blob2 = MagicMock()
        mock_blob2.name = 'photos/user123/original/photo2.jpg'
        
        mock_client.list_blobs.return_value = [mock_blob1, mock_blob2]
        mock_client.bucket.return_value = mock_bucket
        mock_client_class.return_value = mock_client
        
        service = StorageService()
        
        result = service.list_user_files('user123', 'original/')
        
        assert result == ['photos/user123/original/photo1.jpg', 'photos/user123/original/photo2.jpg']
        mock_client.list_blobs.assert_called_once_with(mock_bucket, prefix='photos/user123/original/')

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_get_content_type(self, mock_client_class):
        """Test content type detection."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        service = StorageService()
        
        assert service._get_content_type('photo.jpg') == 'image/jpeg'
        assert service._get_content_type('photo.jpeg') == 'image/jpeg'
        assert service._get_content_type('photo.heic') == 'image/heic'
        assert service._get_content_type('photo.heif') == 'image/heif'
        assert service._get_content_type('document.pdf') == 'application/octet-stream'

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
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

    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
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

    @patch('src.imgstream.services.storage._storage_service', None)
    @patch.dict('os.environ', {'GCS_BUCKET': 'test-bucket', 'GOOGLE_CLOUD_PROJECT': 'test-project'})
    @patch('src.imgstream.services.storage.storage.Client')
    def test_get_storage_service(self, mock_client_class):
        """Test getting global storage service instance."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        service = get_storage_service()
        
        assert isinstance(service, StorageService)
        
        # Should return the same instance
        service2 = get_storage_service()
        assert service is service2
