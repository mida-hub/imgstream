"Tests for gallery page functionality."

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import streamlit as st

from src.imgstream.ui.handlers.gallery import (
    get_photo_original_url,
    get_photo_thumbnail_url,
    load_user_photos,
    get_user_photos_count,
    load_user_photos_paginated,
)





class TestGalleryPage:
    """Test gallery page functionality."""

    @patch("src.imgstream.ui.handlers.gallery.load_user_photos_paginated")
    def test_load_user_photos_empty(self, mock_paginated):
        """Test loading photos when no photos exist."""
        mock_paginated.return_value = ([], 0, False)
        photos = load_user_photos("test_user", "Newest First")
        assert photos == []

    @patch("src.imgstream.ui.handlers.gallery.load_user_photos_paginated")
    def test_load_user_photos_with_data(self, mock_paginated):
        """Test loading photos with data."""
        mock_photo_dict = {"id": "photo1"}
        mock_paginated.return_value = ([mock_photo_dict], 1, False)
        photos = load_user_photos("test_user", "新しい順")
        assert len(photos) == 1
        assert photos[0]["id"] == "photo1"

    @patch("src.imgstream.ui.handlers.gallery.load_user_photos_paginated")
    def test_load_user_photos_oldest_first(self, mock_paginated):
        """Test loading photos with oldest first sorting."""
        mock_photo1 = {"id": "photo1", "filename": "newer.jpg"}
        mock_photo2 = {"id": "photo2", "filename": "older.jpg"}
        mock_paginated.return_value = ([mock_photo2, mock_photo1], 2, False)
        photos = load_user_photos("test_user", "古い順")
        assert len(photos) == 2
        assert photos[0]["id"] == "photo2"

    def test_get_photo_thumbnail_url_success(self):
        """Test getting thumbnail URL successfully."""
        with patch("src.imgstream.ui.handlers.gallery.get_storage_service") as mock_service:
            mock_storage_service = Mock()
            mock_storage_service.get_signed_url.return_value = "https://example.com/thumbnail.jpg"
            mock_service.return_value = mock_storage_service
            url = get_photo_thumbnail_url("thumbs/test.jpg", "photo1")
            assert url == "https://example.com/thumbnail.jpg"

    def test_get_photo_thumbnail_url_error(self):
        """Test getting thumbnail URL when storage service fails."""
        with patch("src.imgstream.ui.handlers.gallery.get_storage_service") as mock_service:
            mock_storage_service = Mock()
            mock_storage_service.get_signed_url.side_effect = Exception("Storage error")
            mock_service.return_value = mock_storage_service
            url = get_photo_thumbnail_url("thumbs/test.jpg", "photo1")
            assert url is None


class TestGalleryPagination:
    """Test gallery pagination functionality."""

    def test_load_user_photos_paginated_with_data(self):
        """Test paginated loading with data."""
        with patch("src.imgstream.ui.handlers.gallery.get_metadata_service") as mock_service, \
             patch("src.imgstream.ui.handlers.gallery.get_user_photos_count", return_value=100):
            mock_photos = []
            for i in range(21):
                mock_photo = Mock()
                mock_photo.to_dict.return_value = {"id": f"photo{i}"}
                mock_photos.append(mock_photo)
            
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_by_date.return_value = mock_photos
            mock_service.return_value = mock_metadata_service
            photos, total_count, has_more = load_user_photos_paginated("test_user", page_size=20)
            assert len(photos) == 20
            assert total_count == 100
            assert has_more is True

    def test_get_user_photos_count_error(self):
        """Test getting photo count when service fails."""
        with patch("src.imgstream.ui.handlers.gallery.get_metadata_service") as mock_service:
            mock_metadata_service = Mock()
            mock_metadata_service.get_photos_count.side_effect = Exception("Database error")
            mock_service.return_value = mock_metadata_service
            count = get_user_photos_count("test_user")
            assert count == 0
