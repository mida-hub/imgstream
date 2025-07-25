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
            mock_metadata_service.get_photos_count.return_value = 0
            mock_service.return_value = mock_metadata_service
            
            photos = load_user_photos("test_user", "Newest First")
            
            assert photos == []
            # The new implementation requests limit+1 to check for more photos
            mock_metadata_service.get_photos_by_date.assert_called_once_with(limit=51, offset=0)

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
            mock_metadata_service.get_photos_count.return_value = 1
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
            mock_metadata_service.get_photos_count.return_value = 2
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


class TestGalleryPagination:
    """Test gallery pagination functionality."""

    def test_initialize_gallery_pagination(self):
        """Test pagination state initialization."""
        from src.imgstream.ui.pages.gallery import initialize_gallery_pagination
        import streamlit as st
        
        # Clear any existing state
        for key in ["gallery_page", "gallery_page_size", "gallery_sort_order", "gallery_total_loaded"]:
            if key in st.session_state:
                del st.session_state[key]
        
        initialize_gallery_pagination()
        
        assert st.session_state.gallery_page == 0
        assert st.session_state.gallery_page_size == 20
        assert st.session_state.gallery_sort_order == "Newest First"
        assert st.session_state.gallery_total_loaded == 0

    def test_reset_gallery_pagination(self):
        """Test pagination reset functionality."""
        from src.imgstream.ui.pages.gallery import reset_gallery_pagination
        import streamlit as st
        
        # Set some state
        st.session_state.gallery_page = 5
        st.session_state.gallery_total_loaded = 100
        
        reset_gallery_pagination()
        
        assert st.session_state.gallery_page == 0
        assert st.session_state.gallery_total_loaded == 0

    def test_load_user_photos_paginated_empty(self):
        """Test paginated loading when no photos exist."""
        with patch('src.imgstream.ui.pages.gallery.get_metadata_service') as mock_service:
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_by_date.return_value = []
            mock_metadata_service.get_photos_count.return_value = 0
            mock_service.return_value = mock_metadata_service
            
            from src.imgstream.ui.pages.gallery import load_user_photos_paginated
            
            photos, total_count, has_more = load_user_photos_paginated("test_user", "Newest First", 0, 20)
            
            assert photos == []
            assert total_count == 0
            assert has_more is False

    def test_load_user_photos_paginated_with_data(self):
        """Test paginated loading with data."""
        with patch('src.imgstream.ui.pages.gallery.get_metadata_service') as mock_service:
            # Create mock photo metadata (21 photos to test has_more)
            mock_photos = []
            for i in range(21):
                mock_photo = Mock()
                mock_photo.to_dict.return_value = {
                    "id": f"photo{i}",
                    "filename": f"test{i}.jpg",
                    "created_at": f"2024-01-{i+1:02d}T12:00:00Z"
                }
                mock_photos.append(mock_photo)
            
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_by_date.return_value = mock_photos
            mock_metadata_service.get_photos_count.return_value = 100
            mock_service.return_value = mock_metadata_service
            
            from src.imgstream.ui.pages.gallery import load_user_photos_paginated
            
            photos, total_count, has_more = load_user_photos_paginated("test_user", "Newest First", 0, 20)
            
            assert len(photos) == 20  # Should return only 20 photos (page_size)
            assert total_count == 100
            assert has_more is True  # Should have more photos

    def test_load_user_photos_paginated_last_page(self):
        """Test paginated loading on last page."""
        with patch('src.imgstream.ui.pages.gallery.get_metadata_service') as mock_service:
            # Create mock photo metadata (only 15 photos, less than page_size)
            mock_photos = []
            for i in range(15):
                mock_photo = Mock()
                mock_photo.to_dict.return_value = {
                    "id": f"photo{i}",
                    "filename": f"test{i}.jpg"
                }
                mock_photos.append(mock_photo)
            
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_by_date.return_value = mock_photos
            mock_metadata_service.get_photos_count.return_value = 35  # Total across all pages
            mock_service.return_value = mock_metadata_service
            
            from src.imgstream.ui.pages.gallery import load_user_photos_paginated
            
            photos, total_count, has_more = load_user_photos_paginated("test_user", "Newest First", 1, 20)
            
            assert len(photos) == 15  # Should return 15 photos (remaining)
            assert total_count == 35
            assert has_more is False  # Should not have more photos

    def test_get_user_photos_count(self):
        """Test getting total photo count."""
        with patch('src.imgstream.ui.pages.gallery.get_metadata_service') as mock_service:
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_count.return_value = 42
            mock_service.return_value = mock_metadata_service
            
            from src.imgstream.ui.pages.gallery import get_user_photos_count
            
            count = get_user_photos_count("test_user")
            
            assert count == 42

    def test_get_user_photos_count_error(self):
        """Test getting photo count when service fails."""
        with patch('src.imgstream.ui.pages.gallery.get_metadata_service') as mock_service:
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_count.side_effect = Exception("Database error")
            mock_service.return_value = mock_metadata_service
            
            from src.imgstream.ui.pages.gallery import get_user_photos_count
            
            count = get_user_photos_count("test_user")
            
            assert count == 0  # Should return 0 on error


class TestGalleryPaginationIntegration:
    """Test gallery pagination integration functionality."""

    def test_pagination_functions_exist(self):
        """Test that all pagination functions exist."""
        from src.imgstream.ui.pages.gallery import (
            initialize_gallery_pagination,
            reset_gallery_pagination,
            load_user_photos_paginated,
            get_user_photos_count,
            render_gallery_header,
            render_pagination_controls,
            render_pagination_summary
        )
        
        # Check that functions are callable
        assert callable(initialize_gallery_pagination)
        assert callable(reset_gallery_pagination)
        assert callable(load_user_photos_paginated)
        assert callable(get_user_photos_count)
        assert callable(render_gallery_header)
        assert callable(render_pagination_controls)
        assert callable(render_pagination_summary)
