"Tests for gallery page functionality."

from unittest.mock import Mock, patch

import pytest

from src.imgstream.ui.handlers.gallery import (
    get_photo_original_url,
    get_photo_thumbnail_url,
    load_user_photos,
    get_user_photos_count,
    load_user_photos_paginated,
)


@pytest.fixture
def mock_paginated_load_user_photos():
    with patch("src.imgstream.ui.handlers.gallery.load_user_photos_paginated") as mock:
        yield mock

@pytest.fixture
def mock_storage_service():
    with patch("src.imgstream.ui.handlers.gallery.get_storage_service") as mock_get_service:
        mock_service_instance = Mock()
        mock_get_service.return_value = mock_service_instance
        yield mock_service_instance

@pytest.fixture
def mock_metadata_service():
    with patch("src.imgstream.ui.handlers.gallery.get_metadata_service") as mock_get_service:
        mock_service_instance = Mock()
        mock_get_service.return_value = mock_service_instance
        yield mock_service_instance


class TestGalleryPage:
    """Test gallery page functionality."""

    def test_load_user_photos_empty(self, mock_paginated_load_user_photos):
        """Test loading photos when no photos exist."""
        mock_paginated_load_user_photos.return_value = ([], 0, False)
        photos = load_user_photos("test_user", "Newest First")
        assert photos == []

    def test_load_user_photos_with_data(self, mock_paginated_load_user_photos):
        """Test loading photos with data."""
        mock_photo_dict = {"id": "photo1"}
        mock_paginated_load_user_photos.return_value = ([mock_photo_dict], 1, False)
        photos = load_user_photos("test_user", "新しい順")
        assert len(photos) == 1
        assert photos[0]["id"] == "photo1"

    def test_load_user_photos_oldest_first(self, mock_paginated_load_user_photos):
        """Test loading photos with oldest first sorting."""
        mock_photo1 = {"id": "photo1", "filename": "newer.jpg"}
        mock_photo2 = {"id": "photo2", "filename": "older.jpg"}
        mock_paginated_load_user_photos.return_value = ([mock_photo2, mock_photo1], 2, False)
        photos = load_user_photos("test_user", "古い順")
        assert len(photos) == 2
        assert photos[0]["id"] == "photo2"

    def test_get_photo_thumbnail_url_success(self, mock_storage_service):
        """Test getting thumbnail URL successfully."""
        mock_storage_service.get_signed_url.return_value = "https://example.com/thumbnail.jpg"
        url = get_photo_thumbnail_url("thumbs/test.jpg", "photo1")
        assert url == "https://example.com/thumbnail.jpg"

    def test_get_photo_thumbnail_url_error(self, mock_storage_service):
        """Test getting thumbnail URL when storage service fails."""
        mock_storage_service.get_signed_url.side_effect = Exception("Storage error")
        url = get_photo_thumbnail_url("thumbs/test.jpg", "photo1")
        assert url is None


class TestGalleryPagination:
    """Test gallery pagination functionality."""

    def test_load_user_photos_paginated_with_data(self, mock_metadata_service):
        """Test paginated loading with data."""
        with patch("src.imgstream.ui.handlers.gallery.get_user_photos_count", return_value=100):
            mock_photos = [Mock() for _ in range(21)]
            for i, photo_mock in enumerate(mock_photos):
                photo_mock.to_dict.return_value = {"id": f"photo{i}"}
            
            mock_metadata_service.get_photos_by_date.return_value = mock_photos
            photos, total_count, has_more = load_user_photos_paginated("test_user", page_size=20)
            assert len(photos) == 20
            assert total_count == 100
            assert has_more is True

    def test_get_user_photos_count_error(self, mock_metadata_service):
        """Test getting photo count when service fails."""
        mock_metadata_service.get_photos_count.side_effect = Exception("Database error")
        count = get_user_photos_count("test_user")
        assert count == 0