"""Storage service for Google Cloud Storage operations."""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from google.cloud import storage  # type: ignore[attr-defined]
from google.cloud.exceptions import GoogleCloudError, NotFound

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when storage operations fail."""
    pass


class StorageService:
    """Service for Google Cloud Storage operations."""

    def __init__(self, bucket_name: str | None = None, project_id: str | None = None) -> None:
        """
        Initialize the storage service.

        Args:
            bucket_name: GCS bucket name (defaults to environment variable)
            project_id: GCP project ID (defaults to environment variable)
        """
        self.bucket_name = bucket_name or os.getenv('GCS_BUCKET')
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT')

        # Additional configuration from environment variables
        self.region = os.getenv('GCS_REGION', 'asia-northeast1')
        self.storage_class = os.getenv('GCS_STORAGE_CLASS', 'STANDARD')
        self.default_signed_url_expiration = int(os.getenv('GCS_SIGNED_URL_EXPIRATION', '3600'))
        self.lifecycle_enabled = os.getenv('GCS_LIFECYCLE_ENABLED', 'true').lower() == 'true'
        self.coldline_days = int(os.getenv('GCS_COLDLINE_DAYS', '30'))

        if not self.bucket_name:
            raise StorageError("GCS_BUCKET environment variable is required")
        if not self.project_id:
            raise StorageError("GOOGLE_CLOUD_PROJECT environment variable is required")

        try:
            self.client = storage.Client(project=self.project_id)
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"Initialized StorageService for bucket: {self.bucket_name} (region: {self.region})")
        except Exception as e:
            raise StorageError(f"Failed to initialize GCS client: {e}") from e

    def _get_user_original_path(self, user_id: str, filename: str) -> str:
        """
        Generate the GCS path for original photos.

        Args:
            user_id: User identifier
            filename: Original filename

        Returns:
            str: GCS object path
        """
        # Sanitize filename to prevent path traversal
        safe_filename = Path(filename).name
        return f"photos/{user_id}/original/{safe_filename}"

    def _get_user_thumbnail_path(self, user_id: str, original_filename: str) -> str:
        """
        Generate the GCS path for thumbnail images.

        Args:
            user_id: User identifier
            original_filename: Original filename

        Returns:
            str: GCS object path for thumbnail
        """
        # Generate thumbnail filename from original
        original_path = Path(original_filename)
        thumbnail_filename = f"{original_path.stem}_thumb.jpg"
        return f"photos/{user_id}/thumbs/{thumbnail_filename}"

    def upload_original_photo(self, user_id: str, file_data: bytes, filename: str) -> str:
        """
        Upload original photo to GCS.

        Args:
            user_id: User identifier
            file_data: Raw image data
            filename: Original filename

        Returns:
            str: GCS object path

        Raises:
            StorageError: If upload fails
        """
        try:
            gcs_path = self._get_user_original_path(user_id, filename)
            blob = self.bucket.blob(gcs_path)

            # Set metadata
            blob.metadata = {
                'user_id': user_id,
                'original_filename': filename,
                'uploaded_at': datetime.now().isoformat(),
                'content_type': self._get_content_type(filename)
            }

            # Upload with Standard storage class
            blob.upload_from_string(
                file_data,
                content_type=self._get_content_type(filename)
            )

            logger.info(f"Uploaded original photo: {gcs_path} ({len(file_data)} bytes)")
            return gcs_path

        except GoogleCloudError as e:
            raise StorageError(f"Failed to upload original photo '{filename}': {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error uploading '{filename}': {e}") from e

    def upload_thumbnail(self, user_id: str, thumbnail_data: bytes, original_filename: str) -> str:
        """
        Upload thumbnail image to GCS.

        Args:
            user_id: User identifier
            thumbnail_data: Thumbnail image data
            original_filename: Original filename for reference

        Returns:
            str: GCS object path for thumbnail

        Raises:
            StorageError: If upload fails
        """
        try:
            gcs_path = self._get_user_thumbnail_path(user_id, original_filename)
            blob = self.bucket.blob(gcs_path)

            # Set metadata
            blob.metadata = {
                'user_id': user_id,
                'original_filename': original_filename,
                'uploaded_at': datetime.now().isoformat(),
                'content_type': 'image/jpeg'
            }

            # Upload thumbnail (always JPEG)
            blob.upload_from_string(
                thumbnail_data,
                content_type='image/jpeg'
            )

            logger.info(f"Uploaded thumbnail: {gcs_path} ({len(thumbnail_data)} bytes)")
            return gcs_path

        except GoogleCloudError as e:
            raise StorageError(f"Failed to upload thumbnail for '{original_filename}': {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error uploading thumbnail: {e}") from e

    def download_file(self, gcs_path: str) -> bytes:
        """
        Download file from GCS.

        Args:
            gcs_path: GCS object path

        Returns:
            bytes: File data

        Raises:
            StorageError: If download fails
        """
        try:
            blob = self.bucket.blob(gcs_path)

            if not blob.exists():
                raise StorageError(f"File not found: {gcs_path}")

            file_data: bytes = blob.download_as_bytes()
            logger.debug(f"Downloaded file: {gcs_path} ({len(file_data)} bytes)")
            return file_data

        except NotFound as e:
            raise StorageError(f"File not found: {gcs_path}") from e
        except GoogleCloudError as e:
            raise StorageError(f"Failed to download file '{gcs_path}': {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error downloading '{gcs_path}': {e}") from e

    def get_signed_url(self, gcs_path: str, expiration: int | None = None) -> str:
        """
        Generate signed URL for secure file access.

        Args:
            gcs_path: GCS object path
            expiration: URL expiration time in seconds (defaults to configured value)

        Returns:
            str: Signed URL

        Raises:
            StorageError: If URL generation fails
        """
        try:
            blob = self.bucket.blob(gcs_path)

            # Use configured default if expiration not specified
            if expiration is None:
                expiration = self.default_signed_url_expiration

            # Generate signed URL
            expiration_time = datetime.now() + timedelta(seconds=expiration)
            signed_url: str = blob.generate_signed_url(
                expiration=expiration_time,
                method='GET'
            )

            logger.debug(f"Generated signed URL for: {gcs_path} (expires in {expiration}s)")
            return signed_url

        except GoogleCloudError as e:
            raise StorageError(f"Failed to generate signed URL for '{gcs_path}': {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error generating signed URL: {e}") from e

    def delete_file(self, gcs_path: str) -> None:
        """
        Delete file from GCS.

        Args:
            gcs_path: GCS object path

        Raises:
            StorageError: If deletion fails
        """
        try:
            blob = self.bucket.blob(gcs_path)

            if not blob.exists():
                logger.warning(f"File not found for deletion: {gcs_path}")
                return

            blob.delete()
            logger.info(f"Deleted file: {gcs_path}")

        except GoogleCloudError as e:
            raise StorageError(f"Failed to delete file '{gcs_path}': {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error deleting '{gcs_path}': {e}") from e

    def list_user_files(self, user_id: str, prefix: str = "") -> list[str]:
        """
        List files for a specific user.

        Args:
            user_id: User identifier
            prefix: Additional prefix filter (e.g., 'original/', 'thumbs/')

        Returns:
            list[str]: List of GCS object paths

        Raises:
            StorageError: If listing fails
        """
        try:
            user_prefix = f"photos/{user_id}/"
            if prefix:
                user_prefix += prefix

            blobs = self.client.list_blobs(self.bucket, prefix=user_prefix)
            file_paths = [blob.name for blob in blobs]

            logger.debug(f"Listed {len(file_paths)} files for user {user_id} with prefix '{prefix}'")
            return file_paths

        except GoogleCloudError as e:
            raise StorageError(f"Failed to list files for user '{user_id}': {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error listing files: {e}") from e

    def _get_content_type(self, filename: str) -> str:
        """
        Determine content type from filename.

        Args:
            filename: File name

        Returns:
            str: MIME content type
        """
        extension = Path(filename).suffix.lower()
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.heic': 'image/heic',
            '.heif': 'image/heif',
        }
        return content_types.get(extension, 'application/octet-stream')

    def check_bucket_exists(self) -> bool:
        """
        Check if the configured bucket exists and is accessible.

        Returns:
            bool: True if bucket exists and is accessible
        """
        try:
            self.bucket.reload()
            return True
        except NotFound:
            logger.error(f"Bucket not found: {self.bucket_name}")
            return False
        except Exception as e:
            logger.error(f"Error checking bucket: {e}")
            return False


# Global storage service instance
_storage_service: StorageService | None = None


def get_storage_service(bucket_name: str | None = None, project_id: str | None = None) -> StorageService:
    """
    Get the global storage service instance.

    Args:
        bucket_name: GCS bucket name (optional, uses environment variable if not provided)
        project_id: GCP project ID (optional, uses environment variable if not provided)

    Returns:
        StorageService: Global storage service instance
    """
    global _storage_service

    if _storage_service is None:
        _storage_service = StorageService(bucket_name=bucket_name, project_id=project_id)

    return _storage_service
