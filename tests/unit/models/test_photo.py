"""
Unit tests for PhotoMetadata model.
"""

import pytest
from datetime import datetime, timezone, timedelta
from src.imgstream.models.photo import PhotoMetadata


class TestPhotoMetadata:
    """Test cases for PhotoMetadata class."""

    def test_create_new_with_all_params(self):
        """Test creating new PhotoMetadata with all parameters."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        uploaded_at = datetime(2023, 1, 1, 12, 5, 0)

        photo = PhotoMetadata.create_new(
            user_id="user123",
            filename="test.jpg",
            original_path="photos/user123/original/test.jpg",
            thumbnail_path="photos/user123/thumbs/test_thumb.jpg",
            file_size=1024000,
            mime_type="image/jpeg",
            created_at=created_at,
            uploaded_at=uploaded_at,
        )

        assert photo.user_id == "user123"
        assert photo.filename == "test.jpg"
        assert photo.original_path == "photos/user123/original/test.jpg"
        assert photo.thumbnail_path == "photos/user123/thumbs/test_thumb.jpg"
        assert photo.file_size == 1024000
        assert photo.mime_type == "image/jpeg"
        assert photo.created_at == created_at
        assert photo.uploaded_at == uploaded_at
        assert photo.id is not None
        assert len(photo.id) == 36  # UUID4 length

    def test_create_new_with_defaults(self):
        """Test creating new PhotoMetadata with default values."""
        before_creation = datetime.now(timezone.utc)

        photo = PhotoMetadata.create_new(
            user_id="user123",
            filename="test.jpg",
            original_path="photos/user123/original/test.jpg",
            thumbnail_path="photos/user123/thumbs/test_thumb.jpg",
            file_size=1024000,
            mime_type="image/jpeg",
        )

        after_creation = datetime.now(timezone.utc)

        assert photo.created_at is None
        assert before_creation <= photo.uploaded_at <= after_creation
        assert photo.id is not None

    def test_to_dict(self):
        """Test converting PhotoMetadata to dictionary."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        uploaded_at = datetime(2023, 1, 1, 12, 5, 0)

        photo = PhotoMetadata(
            id="test-id-123",
            user_id="user123",
            filename="test.jpg",
            original_path="photos/user123/original/test.jpg",
            thumbnail_path="photos/user123/thumbs/test_thumb.jpg",
            created_at=created_at,
            uploaded_at=uploaded_at,
            file_size=1024000,
            mime_type="image/jpeg",
        )

        result = photo.to_dict()

        expected = {
            "id": "test-id-123",
            "user_id": "user123",
            "filename": "test.jpg",
            "original_path": "photos/user123/original/test.jpg",
            "thumbnail_path": "photos/user123/thumbs/test_thumb.jpg",
            "created_at": "2023-01-01T12:00:00",
            "uploaded_at": "2023-01-01T12:05:00",
            "file_size": 1024000,
            "mime_type": "image/jpeg",
        }

        assert result == expected

    def test_to_dict_with_none_created_at(self):
        """Test converting PhotoMetadata to dictionary with None created_at."""
        uploaded_at = datetime(2023, 1, 1, 12, 5, 0)

        photo = PhotoMetadata(
            id="test-id-123",
            user_id="user123",
            filename="test.jpg",
            original_path="photos/user123/original/test.jpg",
            thumbnail_path="photos/user123/thumbs/test_thumb.jpg",
            created_at=None,
            uploaded_at=uploaded_at,
            file_size=1024000,
            mime_type="image/jpeg",
        )

        result = photo.to_dict()
        assert result["created_at"] is None

    def test_from_dict(self):
        """Test creating PhotoMetadata from dictionary."""
        data = {
            "id": "test-id-123",
            "user_id": "user123",
            "filename": "test.jpg",
            "original_path": "photos/user123/original/test.jpg",
            "thumbnail_path": "photos/user123/thumbs/test_thumb.jpg",
            "created_at": "2023-01-01T12:00:00",
            "uploaded_at": "2023-01-01T12:05:00",
            "file_size": 1024000,
            "mime_type": "image/jpeg",
        }

        photo = PhotoMetadata.from_dict(data)

        assert photo.id == "test-id-123"
        assert photo.user_id == "user123"
        assert photo.filename == "test.jpg"
        assert photo.created_at == datetime(2023, 1, 1, 12, 0, 0)
        assert photo.uploaded_at == datetime(2023, 1, 1, 12, 5, 0)
        assert photo.file_size == 1024000
        assert photo.mime_type == "image/jpeg"

    def test_from_dict_with_none_created_at(self):
        """Test creating PhotoMetadata from dictionary with None created_at."""
        data = {
            "id": "test-id-123",
            "user_id": "user123",
            "filename": "test.jpg",
            "original_path": "photos/user123/original/test.jpg",
            "thumbnail_path": "photos/user123/thumbs/test_thumb.jpg",
            "created_at": None,
            "uploaded_at": "2023-01-01T12:05:00",
            "file_size": 1024000,
            "mime_type": "image/jpeg",
        }

        photo = PhotoMetadata.from_dict(data)
        assert photo.created_at is None

    def test_validate_valid_photo(self):
        """Test validation of valid PhotoMetadata."""
        photo = PhotoMetadata(
            id="test-id-123",
            user_id="user123",
            filename="test.jpg",
            original_path="photos/user123/original/test.jpg",
            thumbnail_path="photos/user123/thumbs/test_thumb.jpg",
            created_at=datetime.now(timezone.utc),
            uploaded_at=datetime.now(timezone.utc),
            file_size=1024000,
            mime_type="image/jpeg",
        )

        assert photo.validate() is True

    def test_validate_invalid_photo_missing_id(self):
        """Test validation fails for missing ID."""
        photo = PhotoMetadata(
            id="",
            user_id="user123",
            filename="test.jpg",
            original_path="photos/user123/original/test.jpg",
            thumbnail_path="photos/user123/thumbs/test_thumb.jpg",
            created_at=datetime.now(timezone.utc),
            uploaded_at=datetime.now(timezone.utc),
            file_size=1024000,
            mime_type="image/jpeg",
        )

        assert photo.validate() is False

    def test_validate_invalid_photo_zero_file_size(self):
        """Test validation fails for zero file size."""
        photo = PhotoMetadata(
            id="test-id-123",
            user_id="user123",
            filename="test.jpg",
            original_path="photos/user123/original/test.jpg",
            thumbnail_path="photos/user123/thumbs/test_thumb.jpg",
            created_at=datetime.now(timezone.utc),
            uploaded_at=datetime.now(timezone.utc),
            file_size=0,
            mime_type="image/jpeg",
        )

        assert photo.validate() is False

    def test_validate_invalid_photo_wrong_mime_type(self):
        """Test validation fails for non-image MIME type."""
        photo = PhotoMetadata(
            id="test-id-123",
            user_id="user123",
            filename="test.txt",
            original_path="photos/user123/original/test.txt",
            thumbnail_path="photos/user123/thumbs/test_thumb.jpg",
            created_at=datetime.now(timezone.utc),
            uploaded_at=datetime.now(timezone.utc),
            file_size=1024000,
            mime_type="text/plain",
        )

        assert photo.validate() is False

    def test_get_display_name_with_created_at(self):
        """Test display name generation with created_at."""
        created_at = datetime(2023, 1, 1, 12, 30, 45)

        photo = PhotoMetadata(
            id="test-id-123",
            user_id="user123",
            filename="vacation.jpg",
            original_path="photos/user123/original/vacation.jpg",
            thumbnail_path="photos/user123/thumbs/vacation_thumb.jpg",
            created_at=created_at,
            uploaded_at=datetime.now(timezone.utc),
            file_size=1024000,
            mime_type="image/jpeg",
        )

        display_name = photo.get_display_name()
        assert display_name == "2023-01-01 12:30 - vacation.jpg"

    def test_get_display_name_without_created_at(self):
        """Test display name generation without created_at."""
        photo = PhotoMetadata(
            id="test-id-123",
            user_id="user123",
            filename="vacation.jpg",
            original_path="photos/user123/original/vacation.jpg",
            thumbnail_path="photos/user123/thumbs/vacation_thumb.jpg",
            created_at=None,
            uploaded_at=datetime.now(timezone.utc),
            file_size=1024000,
            mime_type="image/jpeg",
        )

        display_name = photo.get_display_name()
        assert display_name == "vacation.jpg"

    def test_is_recent_true(self):
        """Test is_recent returns True for recent photos."""
        recent_time = datetime.now(timezone.utc) - timedelta(days=3)

        photo = PhotoMetadata(
            id="test-id-123",
            user_id="user123",
            filename="recent.jpg",
            original_path="photos/user123/original/recent.jpg",
            thumbnail_path="photos/user123/thumbs/recent_thumb.jpg",
            created_at=None,
            uploaded_at=recent_time,
            file_size=1024000,
            mime_type="image/jpeg",
        )

        assert photo.is_recent(days=7) is True

    def test_is_recent_false(self):
        """Test is_recent returns False for old photos."""
        old_time = datetime.now(timezone.utc) - timedelta(days=10)

        photo = PhotoMetadata(
            id="test-id-123",
            user_id="user123",
            filename="old.jpg",
            original_path="photos/user123/original/old.jpg",
            thumbnail_path="photos/user123/thumbs/old_thumb.jpg",
            created_at=None,
            uploaded_at=old_time,
            file_size=1024000,
            mime_type="image/jpeg",
        )

        assert photo.is_recent(days=7) is False

    def test_roundtrip_dict_conversion(self):
        """Test that to_dict and from_dict are inverse operations."""
        original = PhotoMetadata.create_new(
            user_id="user123",
            filename="test.jpg",
            original_path="photos/user123/original/test.jpg",
            thumbnail_path="photos/user123/thumbs/test_thumb.jpg",
            file_size=1024000,
            mime_type="image/jpeg",
            created_at=datetime(2023, 1, 1, 12, 0, 0),
        )

        # Convert to dict and back
        data = original.to_dict()
        reconstructed = PhotoMetadata.from_dict(data)

        # Should be equal
        assert original == reconstructed
