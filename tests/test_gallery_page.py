"""Tests for gallery page functionality."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.imgstream.ui.pages.gallery import (
    load_user_photos,
    get_photo_thumbnail_url,
    get_photo_original_url,
    render_photo_thumbnail,
    render_photo_details
)


class TestGalleryPage:
    """Test gallery page functionality."""

    def test_load_user_photos_empty(self):
        """Test loading photos when no photos exist."""
        with patch('src.imgstream.ui.pages.gallery.get_metadata_service') as mock_service:
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_by_date.return_value = []
            mock_service.return_value = mock_metadata_service
            
            photos = load_user_photos("test_user", "Newest First")
            
            assert photos == []
            mock_metadata_service.get_photos_by_date.assert_called_once_with(limit=50, offset=0)

    def test_load_user_photos_with_data(self):
        """Test loading photos with data."""
        with patch('src.imgstream.ui.pages.gallery.get_metadata_service') as mock_service:
            # Create mock photo metadata
            mock_photo = Mock()
            mock_photo.to_dict.return_value = {
                "id": "photo1",
                "filename": "test.jpg",
                "created_at": "2024-01-01T12:00:00Z",
                "thumbnail_path": "thumbs/test.jpg"
            }
            
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_by_date.return_value = [mock_photo]
            mock_service.return_value = mock_metadata_service
            
            photos = load_user_photos("test_user", "Newest First")
            
            assert len(photos) == 1
            assert photos[0]["id"] == "photo1"
            assert photos[0]["filename"] == "test.jpg"

    def test_load_user_photos_oldest_first(self):
        """Test loading photos with oldest first sorting."""
        with patch('src.imgstream.ui.pages.gallery.get_metadata_service') as mock_service:
            # Create mock photo metadata
            mock_photo1 = Mock()
            mock_photo1.to_dict.return_value = {"id": "photo1", "filename": "newer.jpg"}
            mock_photo2 = Mock()
            mock_photo2.to_dict.return_value = {"id": "photo2", "filename": "older.jpg"}
            
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_by_date.return_value = [mock_photo1, mock_photo2]
            mock_service.return_value = mock_metadata_service
            
            photos = load_user_photos("test_user", "Oldest First")
            
            # Should be reversed
            assert len(photos) == 2
            assert photos[0]["id"] == "photo2"  # older photo first
            assert photos[1]["id"] == "photo1"  # newer photo second

    def test_get_photo_thumbnail_url_success(self):
        """Test getting thumbnail URL successfully."""
        with patch('src.imgstream.ui.pages.gallery.get_storage_service') as mock_service:
            mock_storage_service = Mock()
            mock_storage_service.get_signed_url.return_value = "https://example.com/thumbnail.jpg"
            mock_service.return_value = mock_storage_service
            
            photo = {"id": "photo1", "thumbnail_path": "thumbs/test.jpg"}
            url = get_photo_thumbnail_url(photo)
            
            assert url == "https://example.com/thumbnail.jpg"
            mock_storage_service.get_signed_url.assert_called_once_with("thumbs/test.jpg", expiration=3600)

    def test_get_photo_thumbnail_url_no_path(self):
        """Test getting thumbnail URL when no path exists."""
        photo = {"id": "photo1"}  # No thumbnail_path
        url = get_photo_thumbnail_url(photo)
        
        assert url is None

    def test_get_photo_thumbnail_url_error(self):
        """Test getting thumbnail URL when storage service fails."""
        with patch('src.imgstream.ui.pages.gallery.get_storage_service') as mock_service:
            mock_storage_service = Mock()
            mock_storage_service.get_signed_url.side_effect = Exception("Storage error")
            mock_service.return_value = mock_storage_service
            
            photo = {"id": "photo1", "thumbnail_path": "thumbs/test.jpg"}
            url = get_photo_thumbnail_url(photo)
            
            assert url is None

    def test_get_photo_original_url_success(self):
        """Test getting original photo URL successfully."""
        with patch('src.imgstream.ui.pages.gallery.get_storage_service') as mock_service:
            mock_storage_service = Mock()
            mock_storage_service.get_signed_url.return_value = "https://example.com/original.jpg"
            mock_service.return_value = mock_storage_service
            
            photo = {"id": "photo1", "original_path": "original/test.jpg"}
            url = get_photo_original_url(photo)
            
            assert url == "https://example.com/original.jpg"
            mock_storage_service.get_signed_url.assert_called_once_with("original/test.jpg", expiration=3600)

    def test_get_photo_original_url_no_path(self):
        """Test getting original URL when no path exists."""
        photo = {"id": "photo1"}  # No original_path
        url = get_photo_original_url(photo)
        
        assert url is None


class TestGalleryPageIntegration:
    """Test gallery page integration functionality."""

    def test_gallery_page_functions_exist(self):
        """Test that all required gallery page functions exist."""
        from src.imgstream.ui.pages.gallery import (
            render_gallery_page,
            load_user_photos,
            render_photo_grid,
            render_photo_list,
            render_photo_thumbnail,
            render_photo_details,
            get_photo_thumbnail_url,
            get_photo_original_url,
            render_photo_detail_modal
        )
        
        # Check that functions are callable
        assert callable(render_gallery_page)
        assert callable(load_user_photos)
        assert callable(render_photo_grid)
        assert callable(render_photo_list)
        assert callable(render_photo_thumbnail)
        assert callable(render_photo_details)
        assert callable(get_photo_thumbnail_url)
        assert callable(get_photo_original_url)
        assert callable(render_photo_detail_modal)

    def test_photo_data_structure(self):
        """Test that photo data structure is handled correctly."""
        # Test photo dictionary structure
        photo = {
            "id": "photo123",
            "filename": "test.jpg",
            "created_at": "2024-01-01T12:00:00Z",
            "uploaded_at": "2024-01-01T12:30:00Z",
            "file_size": 1024000,
            "mime_type": "image/jpeg",
            "thumbnail_path": "thumbs/test.jpg",
            "original_path": "original/test.jpg"
        }
        
        # Test that all required fields are present
        required_fields = ["id", "filename", "thumbnail_path", "original_path"]
        for field in required_fields:
            assert field in photo
        
        # Test optional fields
        optional_fields = ["created_at", "uploaded_at", "file_size", "mime_type"]
        for field in optional_fields:
            assert field in photo
