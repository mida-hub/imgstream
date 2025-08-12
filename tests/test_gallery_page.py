"""Tests for gallery page functionality."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.imgstream.ui.pages.gallery import (
    get_photo_original_url,
    get_photo_thumbnail_url,
    load_user_photos,
    render_photo_details,
    render_photo_thumbnail,
)


class TestGalleryPage:
    """Test gallery page functionality."""

    def test_load_user_photos_empty(self):
        """Test loading photos when no photos exist."""
        with patch("src.imgstream.ui.pages.gallery.get_metadata_service") as mock_service:
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
        with patch("src.imgstream.ui.pages.gallery.get_metadata_service") as mock_service:
            # Create mock photo metadata
            mock_photo = Mock()
            mock_photo.to_dict.return_value = {
                "id": "photo1",
                "filename": "test.jpg",
                "created_at": "2024-01-01T12:00:00Z",
                "thumbnail_path": "thumbs/test.jpg",
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
        with patch("src.imgstream.ui.pages.gallery.get_metadata_service") as mock_service:
            # Create mock photo metadata
            mock_photo1 = Mock()
            mock_photo1.to_dict.return_value = {"id": "photo1", "filename": "newer.jpg"}
            mock_photo2 = Mock()
            mock_photo2.to_dict.return_value = {"id": "photo2", "filename": "older.jpg"}

            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_by_date.return_value = [mock_photo1, mock_photo2]
            mock_metadata_service.get_photos_count.return_value = 2
            mock_service.return_value = mock_metadata_service

            photos = load_user_photos("test_user", "古い順")

            # Should be reversed
            assert len(photos) == 2
            assert photos[0]["id"] == "photo2"  # older photo first
            assert photos[1]["id"] == "photo1"  # newer photo second

    def test_get_photo_thumbnail_url_success(self):
        """Test getting thumbnail URL successfully."""
        with patch("src.imgstream.ui.pages.gallery.get_storage_service") as mock_service:
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
        with patch("src.imgstream.ui.pages.gallery.get_storage_service") as mock_service:
            mock_storage_service = Mock()
            mock_storage_service.get_signed_url.side_effect = Exception("Storage error")
            mock_service.return_value = mock_storage_service

            photo = {"id": "photo1", "thumbnail_path": "thumbs/test.jpg"}
            url = get_photo_thumbnail_url(photo)

            assert url is None

    def test_get_photo_original_url_success(self):
        """Test getting original photo URL successfully."""
        with patch("src.imgstream.ui.pages.gallery.get_storage_service") as mock_service:
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
            get_photo_original_url,
            get_photo_thumbnail_url,
            load_user_photos,
            render_gallery_page,
            render_photo_detail_modal,
            render_photo_grid,
            render_photo_list,
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
            "original_path": "original/test.jpg",
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
        import streamlit as st

        from src.imgstream.ui.pages.gallery import initialize_gallery_pagination

        # Clear any existing state
        for key in ["gallery_page", "gallery_page_size", "gallery_sort_order", "gallery_total_loaded"]:
            if key in st.session_state:
                del st.session_state[key]

        initialize_gallery_pagination()

        assert st.session_state.gallery_page == 0
        assert st.session_state.gallery_page_size == 20
        assert st.session_state.gallery_sort_order == "新しい順"
        assert st.session_state.gallery_total_loaded == 0

    def test_reset_gallery_pagination(self):
        """Test pagination reset functionality."""
        import streamlit as st

        from src.imgstream.ui.pages.gallery import reset_gallery_pagination

        # Set some state
        st.session_state.gallery_page = 5
        st.session_state.gallery_total_loaded = 100

        reset_gallery_pagination()

        assert st.session_state.gallery_page == 0
        assert st.session_state.gallery_total_loaded == 0

    def test_load_user_photos_paginated_empty(self):
        """Test paginated loading when no photos exist."""
        with patch("src.imgstream.ui.pages.gallery.get_metadata_service") as mock_service:
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
        with patch("src.imgstream.ui.pages.gallery.get_metadata_service") as mock_service:
            # Create mock photo metadata (21 photos to test has_more)
            mock_photos = []
            for i in range(21):
                mock_photo = Mock()
                mock_photo.to_dict.return_value = {
                    "id": f"photo{i}",
                    "filename": f"test{i}.jpg",
                    "created_at": f"2024-01-{i+1:02d}T12:00:00Z",
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
        with patch("src.imgstream.ui.pages.gallery.get_metadata_service") as mock_service:
            # Create mock photo metadata (only 15 photos, less than page_size)
            mock_photos = []
            for i in range(15):
                mock_photo = Mock()
                mock_photo.to_dict.return_value = {"id": f"photo{i}", "filename": f"test{i}.jpg"}
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
        with patch("src.imgstream.ui.pages.gallery.get_metadata_service") as mock_service:
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_count.return_value = 42
            mock_service.return_value = mock_metadata_service

            from src.imgstream.ui.pages.gallery import get_user_photos_count

            count = get_user_photos_count("test_user")

            assert count == 42

    def test_get_user_photos_count_error(self):
        """Test getting photo count when service fails."""
        with patch("src.imgstream.ui.pages.gallery.get_metadata_service") as mock_service:
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
            get_user_photos_count,
            initialize_gallery_pagination,
            load_user_photos_paginated,
            render_gallery_header,
            render_pagination_controls,
            render_pagination_summary,
            reset_gallery_pagination,
        )

        # Check that functions are callable
        assert callable(initialize_gallery_pagination)
        assert callable(reset_gallery_pagination)
        assert callable(load_user_photos_paginated)
        assert callable(get_user_photos_count)
        assert callable(render_gallery_header)
        assert callable(render_pagination_controls)
        assert callable(render_pagination_summary)


class TestPhotoDetailDisplay:
    """Test photo detail display functionality."""

    def test_render_photo_detail_modal_functions_exist(self):
        """Test that photo detail modal functions exist."""
        from src.imgstream.ui.pages.gallery import (
            confirm_delete_photo,
            copy_image_url,
            download_original_photo,
            download_thumbnail_photo,
            render_photo_detail_footer,
            render_photo_detail_header,
            render_photo_detail_image,
            render_photo_detail_modal,
            render_photo_detail_sidebar,
        )

        # Check that functions are callable
        assert callable(render_photo_detail_modal)
        assert callable(render_photo_detail_header)
        assert callable(render_photo_detail_image)
        assert callable(render_photo_detail_sidebar)
        assert callable(render_photo_detail_footer)
        assert callable(download_original_photo)
        assert callable(download_thumbnail_photo)
        assert callable(copy_image_url)
        assert callable(confirm_delete_photo)

    def test_photo_detail_modal_session_state(self):
        """Test photo detail modal session state handling."""
        import streamlit as st

        # Test when no photo is selected
        st.session_state.show_photo_details = False
        st.session_state.selected_photo = None

        from src.imgstream.ui.pages.gallery import render_photo_detail_modal

        # Should not raise any errors when no photo is selected
        try:
            render_photo_detail_modal()
        except Exception:
            pytest.fail("render_photo_detail_modal should handle empty state gracefully")

    def test_download_original_photo_success(self):
        """Test successful original photo download."""
        with patch("src.imgstream.ui.pages.gallery.get_photo_original_url") as mock_url:
            mock_url.return_value = "https://example.com/original.jpg"

            from src.imgstream.ui.pages.gallery import download_original_photo

            photo = {"id": "photo1", "filename": "test.jpg"}

            # Should not raise any errors
            try:
                download_original_photo(photo)
            except Exception:
                pytest.fail("download_original_photo should handle success case")

    def test_download_original_photo_failure(self):
        """Test original photo download failure."""
        with patch("src.imgstream.ui.pages.gallery.get_photo_original_url") as mock_url:
            mock_url.return_value = None

            from src.imgstream.ui.pages.gallery import download_original_photo

            photo = {"id": "photo1", "filename": "test.jpg"}

            # Should not raise any errors even on failure
            try:
                download_original_photo(photo)
            except Exception:
                pytest.fail("download_original_photo should handle failure gracefully")

    def test_download_thumbnail_photo_success(self):
        """Test successful thumbnail photo download."""
        with patch("src.imgstream.ui.pages.gallery.get_photo_thumbnail_url") as mock_url:
            mock_url.return_value = "https://example.com/thumbnail.jpg"

            from src.imgstream.ui.pages.gallery import download_thumbnail_photo

            photo = {"id": "photo1", "filename": "test.jpg"}

            # Should not raise any errors
            try:
                download_thumbnail_photo(photo)
            except Exception:
                pytest.fail("download_thumbnail_photo should handle success case")

    def test_copy_image_url_success(self):
        """Test successful image URL copying."""
        with patch("src.imgstream.ui.pages.gallery.get_photo_original_url") as mock_url:
            mock_url.return_value = "https://example.com/original.jpg"

            from src.imgstream.ui.pages.gallery import copy_image_url

            photo = {"id": "photo1", "filename": "test.jpg"}

            # Should not raise any errors
            try:
                copy_image_url(photo)
            except Exception:
                pytest.fail("copy_image_url should handle success case")

    def test_copy_image_url_failure(self):
        """Test image URL copying failure."""
        with patch("src.imgstream.ui.pages.gallery.get_photo_original_url") as mock_url:
            mock_url.return_value = None

            from src.imgstream.ui.pages.gallery import copy_image_url

            photo = {"id": "photo1", "filename": "test.jpg"}

            # Should not raise any errors even on failure
            try:
                copy_image_url(photo)
            except Exception:
                pytest.fail("copy_image_url should handle failure gracefully")

    def test_confirm_delete_photo(self):
        """Test photo deletion confirmation."""
        from src.imgstream.ui.pages.gallery import confirm_delete_photo

        photo = {"id": "photo1", "filename": "test.jpg"}

        # Should not raise any errors
        try:
            confirm_delete_photo(photo)
        except Exception:
            pytest.fail("confirm_delete_photo should handle confirmation display")


class TestPhotoDetailIntegration:
    """Test photo detail integration functionality."""

    def test_photo_detail_data_handling(self):
        """Test photo detail data structure handling."""
        # Test comprehensive photo data structure
        photo = {
            "id": "photo123",
            "filename": "detailed_test.jpg",
            "created_at": "2024-01-01T12:00:00Z",
            "uploaded_at": "2024-01-01T12:30:00Z",
            "file_size": 2048000,
            "mime_type": "image/jpeg",
            "thumbnail_path": "thumbs/detailed_test.jpg",
            "original_path": "original/detailed_test.jpg",
        }

        # Test that all fields are accessible
        assert photo["id"] == "photo123"
        assert photo["filename"] == "detailed_test.jpg"
        assert photo["file_size"] == 2048000
        assert photo["mime_type"] == "image/jpeg"

        # Test date handling

        created_at = datetime.fromisoformat(photo["created_at"].replace("Z", "+00:00"))
        uploaded_at = datetime.fromisoformat(photo["uploaded_at"].replace("Z", "+00:00"))

        assert created_at.year == 2024
        assert uploaded_at.year == 2024
        assert uploaded_at > created_at

    def test_photo_navigation_context(self):
        """Test photo navigation context handling."""
        import streamlit as st

        # Set up photo navigation context
        photos = [
            {"id": "photo1", "filename": "first.jpg"},
            {"id": "photo2", "filename": "second.jpg"},
            {"id": "photo3", "filename": "third.jpg"},
        ]

        st.session_state.gallery_photos = photos
        st.session_state.photo_index = 1
        st.session_state.total_photos = 3

        # Test context is properly set
        assert st.session_state.photo_index == 1
        assert st.session_state.total_photos == 3
        assert len(st.session_state.gallery_photos) == 3
