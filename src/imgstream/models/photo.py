"""
Photo metadata model for imgstream application.

This module contains the PhotoMetadata dataclass that represents
photo metadata stored in DuckDB.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class PhotoMetadata:
    """
    Represents metadata for a photo in the imgstream system.

    This dataclass contains all the information needed to track
    a photo's location, timestamps, and properties.
    """

    id: str
    user_id: str
    filename: str
    original_path: str
    thumbnail_path: str
    created_at: datetime | None
    uploaded_at: datetime
    file_size: int
    mime_type: str

    @classmethod
    def create_new(
        cls,
        user_id: str,
        filename: str,
        original_path: str,
        thumbnail_path: str,
        file_size: int,
        mime_type: str,
        created_at: datetime | None = None,
        uploaded_at: datetime | None = None,
    ) -> "PhotoMetadata":
        """
        Create a new PhotoMetadata instance with generated ID and current timestamp.

        Args:
            user_id: ID of the user who uploaded the photo
            filename: Original filename of the photo
            original_path: GCS path to the original photo
            thumbnail_path: GCS path to the thumbnail
            file_size: Size of the original file in bytes
            mime_type: MIME type of the photo (e.g., 'image/jpeg')
            created_at: When the photo was originally taken (from EXIF)
            uploaded_at: When the photo was uploaded (defaults to now)

        Returns:
            New PhotoMetadata instance
        """
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            filename=filename,
            original_path=original_path,
            thumbnail_path=thumbnail_path,
            created_at=created_at,
            uploaded_at=uploaded_at or datetime.now(UTC),
            file_size=file_size,
            mime_type=mime_type,
        )

    def to_dict(self) -> dict:
        """
        Convert PhotoMetadata to dictionary for database storage.

        Returns:
            Dictionary representation of the photo metadata
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "original_path": self.original_path,
            "thumbnail_path": self.thumbnail_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "uploaded_at": self.uploaded_at.isoformat(),
            "file_size": self.file_size,
            "mime_type": self.mime_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PhotoMetadata":
        """
        Create PhotoMetadata from dictionary (e.g., from database).

        Args:
            data: Dictionary containing photo metadata

        Returns:
            PhotoMetadata instance
        """
        # Handle created_at which can be None, string, or datetime
        created_at = data["created_at"]
        if created_at is not None and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        # Handle uploaded_at which can be string or datetime
        uploaded_at = data["uploaded_at"]
        if isinstance(uploaded_at, str):
            uploaded_at = datetime.fromisoformat(uploaded_at)

        return cls(
            id=data["id"],
            user_id=data["user_id"],
            filename=data["filename"],
            original_path=data["original_path"],
            thumbnail_path=data["thumbnail_path"],
            created_at=created_at,
            uploaded_at=uploaded_at,
            file_size=data["file_size"],
            mime_type=data["mime_type"],
        )

    def validate(self) -> bool:
        """
        Validate the PhotoMetadata instance.

        Returns:
            True if valid, False otherwise
        """
        if not self.id or not self.user_id or not self.filename:
            return False

        if not self.original_path or not self.thumbnail_path:
            return False

        if self.file_size <= 0:
            return False

        if not self.mime_type or not self.mime_type.startswith("image/"):
            return False

        return True

    def get_display_name(self) -> str:
        """
        Get a user-friendly display name for the photo.

        Returns:
            Display name based on created_at or filename
        """
        if self.created_at:
            return f"{self.created_at.strftime('%Y-%m-%d %H:%M')} - {self.filename}"
        return self.filename

    def is_recent(self, days: int = 7) -> bool:
        """
        Check if the photo was uploaded recently.

        Args:
            days: Number of days to consider as recent

        Returns:
            True if uploaded within the specified days
        """
        time_diff = datetime.now(UTC) - self.uploaded_at
        return time_diff.days <= days
