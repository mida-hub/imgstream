"""Storage service for Google Cloud Storage operations."""

import os
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from google.cloud import storage  # type: ignore[attr-defined]
from google.cloud.exceptions import GoogleCloudError, NotFound
import google.auth
import google.auth.transport.requests

from imgstream.ui.handlers.error import StorageError
from ..logging_config import get_logger

logger = get_logger(__name__)


class UploadProgress:
    """Helper class for tracking upload progress."""

    def __init__(self, total_bytes: int, filename: str = ""):
        self.total_bytes = total_bytes
        self.uploaded_bytes = 0
        self.filename = filename
        self.start_time = datetime.now()
        self.status = "pending"

    def update(self, uploaded_bytes: int, status: str = "uploading") -> None:
        """Update progress information."""
        self.uploaded_bytes = uploaded_bytes
        self.status = status

    @property
    def progress_percentage(self) -> float:
        """Get progress as percentage."""
        if self.total_bytes == 0:
            return 0.0
        percentage = (self.uploaded_bytes / self.total_bytes) * 100
        # Clamp to 0-100 range
        return max(0.0, min(100.0, percentage))

    @property
    def elapsed_time(self) -> timedelta:
        """Get elapsed time since start."""
        return datetime.now() - self.start_time

    @property
    def upload_speed(self) -> float:
        """Get upload speed in bytes per second."""
        elapsed_seconds = self.elapsed_time.total_seconds()
        if elapsed_seconds == 0:
            return 0.0
        return self.uploaded_bytes / elapsed_seconds

    def to_dict(self) -> dict:
        """Convert progress to dictionary."""
        return {
            "filename": self.filename,
            "total_bytes": self.total_bytes,
            "uploaded_bytes": self.uploaded_bytes,
            "progress_percentage": self.progress_percentage,
            "status": self.status,
            "elapsed_time": self.elapsed_time.total_seconds(),
            "upload_speed": self.upload_speed,
        }


class StorageService:
    """Service for Google Cloud Storage operations."""

    def __init__(self, bucket_name: str | None = None, project_id: str | None = None) -> None:
        """
        Initialize the storage service.

        Args:
            bucket_name: GCS photos bucket name (defaults to GCS_PHOTOS_BUCKET environment variable)
            project_id: GCP project ID (defaults to GOOGLE_CLOUD_PROJECT environment variable)

        Environment Variables:
            GCS_PHOTOS_BUCKET: Bucket for storing photos and thumbnails
            GCS_DATABASE_BUCKET: Bucket for storing database files
            GOOGLE_CLOUD_PROJECT: GCP project ID
        """
        # Photos bucket configuration
        self.photos_bucket_name = bucket_name or os.getenv("GCS_PHOTOS_BUCKET")
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")

        # Database bucket configuration
        self.database_bucket_name = os.getenv("GCS_DATABASE_BUCKET")

        # Additional configuration from environment variables
        self.region = os.getenv("GCS_REGION", "asia-northeast1")
        self.storage_class = os.getenv("GCS_STORAGE_CLASS", "STANDARD")
        self.default_signed_url_expiration = int(os.getenv("GCS_SIGNED_URL_EXPIRATION", "3600"))
        self.lifecycle_enabled = os.getenv("GCS_LIFECYCLE_ENABLED", "true").lower() == "true"
        self.coldline_days = int(os.getenv("GCS_COLDLINE_DAYS", "30"))

        if not self.photos_bucket_name:
            raise StorageError("GCS_PHOTOS_BUCKET environment variable is required")
        if not self.project_id:
            raise StorageError("GOOGLE_CLOUD_PROJECT environment variable is required")

        if not self.database_bucket_name:
            raise StorageError("GCS_DATABASE_BUCKET environment variable is required")

        try:
            self.client = storage.Client(project=self.project_id)
            self.photos_bucket = self.client.bucket(self.photos_bucket_name)

            # Initialize database bucket
            self.database_bucket = self.client.bucket(self.database_bucket_name)
            logger.info(
                "storage_service_initialized",
                photos_bucket=self.photos_bucket_name,
                database_bucket=self.database_bucket_name,
                region=self.region,
                project_id=self.project_id,
                storage_class=self.storage_class,
            )
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

    def upload_original_photo(
        self,
        user_id: str,
        file_data: bytes,
        filename: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        """
        Upload original photo to GCS with progress tracking.

        Args:
            user_id: User identifier
            file_data: Raw image data
            filename: Original filename
            progress_callback: Optional callback function for progress updates

        Returns:
            dict: Upload result with metadata

        Raises:
            StorageError: If upload fails
        """
        try:
            gcs_path = self._get_user_original_path(user_id, filename)
            blob = self.photos_bucket.blob(gcs_path)

            # Check if file already exists
            file_exists = blob.exists()
            if file_exists:
                logger.warning(f"File already exists, will overwrite: {gcs_path}")

            # Set comprehensive metadata
            upload_timestamp = datetime.now().isoformat()
            blob.metadata = {
                "user_id": user_id,
                "original_filename": filename,
                "uploaded_at": upload_timestamp,
                "content_type": self._get_content_type(filename),
                "file_size": str(len(file_data)),
                "storage_class": self.storage_class,
                "region": self.region,
                "upload_type": "original_photo",
            }

            # Set storage class explicitly
            blob.storage_class = self.storage_class

            # Progress tracking
            if progress_callback:
                progress_callback(0, len(file_data), "Starting upload...")

            # Upload with Standard storage class
            blob.upload_from_string(file_data, content_type=self._get_content_type(filename))

            if progress_callback:
                progress_callback(len(file_data), len(file_data), "Upload completed")

            # Verify upload
            if not blob.exists():
                raise StorageError(f"Upload verification failed for '{filename}'")

            # Get final blob info
            blob.reload()

            upload_result = {
                "gcs_path": gcs_path,
                "file_size": len(file_data),
                "content_type": self._get_content_type(filename),
                "storage_class": blob.storage_class,
                "uploaded_at": upload_timestamp,
                "etag": blob.etag,
                "generation": blob.generation,
                "was_overwrite": file_exists,
            }

            logger.info(f"Uploaded original photo: {gcs_path} " f"({len(file_data)} bytes, {blob.storage_class} class)")

            return upload_result

        except GoogleCloudError as e:
            if progress_callback:
                progress_callback(0, len(file_data), f"Upload failed: {e}")
            raise StorageError(f"Failed to upload original photo '{filename}': {e}") from e
        except Exception as e:
            if progress_callback:
                progress_callback(0, len(file_data), f"Unexpected error: {e}")
            raise StorageError(f"Unexpected error uploading '{filename}': {e}") from e

    def upload_thumbnail(
        self,
        user_id: str,
        thumbnail_data: bytes,
        original_filename: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        """
        Upload thumbnail image to GCS with enhanced features.

        Args:
            user_id: User identifier
            thumbnail_data: Thumbnail image data
            original_filename: Original filename for reference
            progress_callback: Optional callback function for progress updates

        Returns:
            dict: Upload result with metadata

        Raises:
            StorageError: If upload fails
        """
        try:
            gcs_path = self._get_user_thumbnail_path(user_id, original_filename)
            blob = self.photos_bucket.blob(gcs_path)

            # Check if thumbnail already exists
            file_exists = blob.exists()
            if file_exists:
                logger.warning(f"Thumbnail already exists, will overwrite: {gcs_path}")

            # Set comprehensive metadata
            upload_timestamp = datetime.now().isoformat()
            blob.metadata = {
                "user_id": user_id,
                "original_filename": original_filename,
                "uploaded_at": upload_timestamp,
                "content_type": "image/jpeg",
                "file_size": str(len(thumbnail_data)),
                "storage_class": "STANDARD",
                "region": self.region,
                "upload_type": "thumbnail",
            }

            # Progress tracking
            if progress_callback:
                progress_callback(0, len(thumbnail_data), "Starting thumbnail upload...")

            # Upload thumbnail (always JPEG) with efficient binary processing
            blob.upload_from_string(thumbnail_data, content_type="image/jpeg")

            if progress_callback:
                progress_callback(len(thumbnail_data), len(thumbnail_data), "Thumbnail upload completed")

            # Verify upload
            if not blob.exists():
                raise StorageError(f"Thumbnail upload verification failed for '{original_filename}'")

            # Get final blob info
            blob.reload()

            upload_result = {
                "gcs_path": gcs_path,
                "file_size": len(thumbnail_data),
                "content_type": "image/jpeg",
                "storage_class": blob.storage_class,
                "uploaded_at": upload_timestamp,
                "etag": blob.etag,
                "generation": blob.generation,
                "was_overwrite": file_exists,
            }

            logger.info(f"Uploaded thumbnail: {gcs_path} " f"({len(thumbnail_data)} bytes, {blob.storage_class} class)")

            return upload_result

        except GoogleCloudError as e:
            if progress_callback:
                progress_callback(0, len(thumbnail_data), f"Upload failed: {e}")
            raise StorageError(f"Failed to upload thumbnail for '{original_filename}': {e}") from e
        except Exception as e:
            if progress_callback:
                progress_callback(0, len(thumbnail_data), f"Unexpected error: {e}")
            raise StorageError(f"Unexpected error uploading thumbnail: {e}") from e

    def upload_multiple_thumbnails(
        self,
        user_id: str,
        thumbnails: list[tuple[bytes, str]],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[dict]:
        """
        Upload multiple thumbnails in batch with efficient processing.

        Args:
            user_id: User identifier
            thumbnails: List of (thumbnail_data, original_filename) tuples
            progress_callback: Optional callback function for progress updates

        Returns:
            list[dict]: List of upload results

        Raises:
            StorageError: If batch upload fails
        """
        results = []
        total_files = len(thumbnails)

        try:
            for i, (thumbnail_data, original_filename) in enumerate(thumbnails):
                if progress_callback:
                    progress_callback(i, total_files, f"Uploading thumbnail for {original_filename}...")

                try:
                    result = self.upload_thumbnail(user_id, thumbnail_data, original_filename)
                    results.append({"success": True, "filename": original_filename, "result": result})
                except StorageError as e:
                    logger.error(f"Failed to upload thumbnail for {original_filename}: {e}")
                    results.append({"success": False, "filename": original_filename, "error": str(e)})

            if progress_callback:
                successful = sum(1 for r in results if r["success"])
                progress_callback(
                    total_files, total_files, f"Batch thumbnail upload completed: {successful}/{total_files} successful"
                )

            logger.info(f"Batch thumbnail upload completed for user {user_id}: {len(results)} files processed")
            return results

        except Exception as e:
            raise StorageError(f"Batch thumbnail upload failed: {e}") from e

    def check_thumbnail_exists(self, user_id: str, original_filename: str) -> dict:
        """
        Check if thumbnail exists and get its metadata.

        Args:
            user_id: User identifier
            original_filename: Original filename

        Returns:
            dict: Thumbnail existence info and metadata

        Raises:
            StorageError: If check fails
        """
        try:
            gcs_path = self._get_user_thumbnail_path(user_id, original_filename)
            blob = self.photos_bucket.blob(gcs_path)

            if not blob.exists():
                return {"exists": False, "gcs_path": gcs_path}

            # Get metadata
            blob.reload()
            return {
                "exists": True,
                "gcs_path": gcs_path,
                "file_size": blob.size,
                "content_type": blob.content_type,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "etag": blob.etag,
                "generation": blob.generation,
                "metadata": blob.metadata or {},
            }

        except GoogleCloudError as e:
            raise StorageError(f"Failed to check thumbnail existence for '{original_filename}': {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error checking thumbnail: {e}") from e

    def upload_thumbnail_with_deduplication(
        self,
        user_id: str,
        thumbnail_data: bytes,
        original_filename: str,
        force_overwrite: bool = False,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        """
        Upload thumbnail with smart deduplication.

        Args:
            user_id: User identifier
            thumbnail_data: Thumbnail image data
            original_filename: Original filename for reference
            force_overwrite: Force overwrite even if thumbnail exists
            progress_callback: Optional callback function for progress updates

        Returns:
            dict: Upload result with deduplication info

        Raises:
            StorageError: If upload fails
        """
        try:
            # Check if thumbnail already exists
            existing_info = self.check_thumbnail_exists(user_id, original_filename)

            if existing_info["exists"] and not force_overwrite:
                # Compare file sizes for basic deduplication
                existing_size = existing_info.get("file_size", 0)
                new_size = len(thumbnail_data)

                if existing_size == new_size:
                    logger.info(f"Thumbnail already exists with same size, skipping upload: {original_filename}")
                    if progress_callback:
                        progress_callback(new_size, new_size, "Thumbnail already exists, skipped")

                    return {
                        "skipped": True,
                        "reason": "duplicate_size",
                        "existing_info": existing_info,
                        "gcs_path": existing_info["gcs_path"],
                    }

            # Upload thumbnail
            result = self.upload_thumbnail(user_id, thumbnail_data, original_filename, progress_callback)
            result["skipped"] = False
            result["was_duplicate"] = existing_info["exists"]

            return result

        except Exception as e:
            raise StorageError(f"Failed to upload thumbnail with deduplication: {e}") from e

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
            blob = self.photos_bucket.blob(gcs_path)

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
            credentials, _ = google.auth.default()
            try:
                credentials.refresh(google.auth.transport.requests.Request())
            except:
                # occurred by local env only for Invalid OAuth scope or ID token audience provided
                pass

            blob = self.photos_bucket.blob(gcs_path)

            # Use configured default if expiration not specified
            if expiration is None:
                expiration = self.default_signed_url_expiration

            # Generate signed URL
            expiration_time = datetime.now() + timedelta(seconds=expiration)
            signed_url: str = blob.generate_signed_url(expiration=expiration_time,
                                                       method="GET",
                                                       version="v4",
                                                       service_account_email=credentials.service_account_email,
                                                       access_token=credentials.token
                                                       )

            logger.debug(f"Generated signed URL for: {gcs_path} (expires in {expiration}s)")
            return signed_url

        except GoogleCloudError as e:
            raise StorageError(f"Failed to generate signed URL for '{gcs_path}': {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error generating signed URL: {e}") from e

    def get_photo_display_url(
        self, user_id: str, filename: str, photo_type: str = "original", expiration: int | None = None
    ) -> dict:
        """
        Generate signed URL for photo display with user permission validation.

        Args:
            user_id: User identifier
            filename: Original filename
            photo_type: Type of photo ('original' or 'thumbnail')
            expiration: URL expiration time in seconds

        Returns:
            dict: URL info with metadata

        Raises:
            StorageError: If URL generation fails
        """
        try:
            # Validate photo type
            if photo_type not in ["original", "thumbnail"]:
                raise ValueError(f"Invalid photo_type: {photo_type}. Must be 'original' or 'thumbnail'")

            # Get appropriate GCS path
            if photo_type == "original":
                gcs_path = self._get_user_original_path(user_id, filename)
            else:
                gcs_path = self._get_user_thumbnail_path(user_id, filename)

            # Check if file exists
            blob = self.photos_bucket.blob(gcs_path)
            if not blob.exists():
                raise StorageError(f"Photo not found: {filename} ({photo_type})")

            # Get file metadata
            blob.reload()

            # Generate signed URL
            signed_url = self.get_signed_url(gcs_path, expiration)

            # Calculate actual expiration time
            exp_seconds = expiration or self.default_signed_url_expiration
            expires_at = datetime.now() + timedelta(seconds=exp_seconds)

            result = {
                "signed_url": signed_url,
                "gcs_path": gcs_path,
                "photo_type": photo_type,
                "filename": filename,
                "user_id": user_id,
                "file_size": blob.size,
                "content_type": blob.content_type,
                "expires_at": expires_at.isoformat(),
                "expiration_seconds": exp_seconds,
            }

            logger.info(f"Generated {photo_type} display URL for user {user_id}: {filename}")
            return result

        except ValueError as e:
            raise StorageError(f"Invalid parameters: {e}") from e
        except Exception as e:
            raise StorageError(f"Failed to generate photo display URL: {e}") from e

    def get_batch_photo_urls(
        self, user_id: str, photo_requests: list[dict], default_expiration: int | None = None
    ) -> list[dict]:
        """
        Generate multiple signed URLs for batch photo access.

        Args:
            user_id: User identifier
            photo_requests: List of photo request dicts with 'filename' and optional 'photo_type', 'expiration'
            default_expiration: Default expiration for URLs without specific expiration

        Returns:
            list[dict]: List of URL results

        Raises:
            StorageError: If batch URL generation fails
        """
        results = []

        try:
            for request in photo_requests:
                filename = request.get("filename")
                if not filename:
                    results.append({"success": False, "error": "Missing filename", "filename": None})
                    continue

                photo_type = request.get("photo_type", "thumbnail")
                expiration = request.get("expiration", default_expiration)

                try:
                    url_info = self.get_photo_display_url(user_id, filename, photo_type, expiration)
                    results.append({"success": True, "filename": filename, "url_info": url_info})
                except StorageError as e:
                    logger.warning(f"Failed to generate URL for {filename}: {e}")
                    results.append({"success": False, "filename": filename, "error": str(e)})

            successful = sum(1 for r in results if r["success"])
            logger.info(f"Generated batch URLs for user {user_id}: {successful}/{len(results)} successful")

            return results

        except Exception as e:
            raise StorageError(f"Batch URL generation failed: {e}") from e

    def validate_user_access(self, user_id: str, gcs_path: str) -> bool:
        """
        Validate that a user has access to a specific GCS path.

        Args:
            user_id: User identifier
            gcs_path: GCS object path to validate

        Returns:
            bool: True if user has access, False otherwise
        """
        try:
            # Check if the path belongs to the user
            expected_prefix = f"photos/{user_id}/"
            if not gcs_path.startswith(expected_prefix):
                logger.warning(f"Access denied: {gcs_path} does not belong to user {user_id}")
                return False

            # Additional validation could be added here
            # (e.g., checking user permissions, file ownership, etc.)

            return True

        except Exception as e:
            logger.error(f"Error validating user access: {e}")
            return False

    def get_secure_photo_url(self, user_id: str, gcs_path: str, expiration: int | None = None) -> str:
        """
        Generate signed URL with user access validation.

        Args:
            user_id: User identifier
            gcs_path: GCS object path
            expiration: URL expiration time in seconds

        Returns:
            str: Signed URL

        Raises:
            StorageError: If access is denied or URL generation fails
        """
        try:
            # Validate user access
            if not self.validate_user_access(user_id, gcs_path):
                raise StorageError(f"Access denied to {gcs_path} for user {user_id}")

            # Generate signed URL
            return self.get_signed_url(gcs_path, expiration)

        except Exception as e:
            raise StorageError(f"Failed to generate secure URL: {e}") from e

    def delete_file(self, gcs_path: str) -> None:
        """
        Delete file from GCS.

        Args:
            gcs_path: GCS object path

        Raises:
            StorageError: If deletion fails
        """
        try:
            blob = self.photos_bucket.blob(gcs_path)

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

            blobs = self.client.list_blobs(self.photos_bucket, prefix=user_prefix)
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
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".heic": "image/heic",
            ".heif": "image/heif",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }
        return content_types.get(extension, "application/octet-stream")

    def upload_multiple_photos(
        self,
        user_id: str,
        photos: list[tuple[bytes, str]],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[dict]:
        """
        Upload multiple photos in batch.

        Args:
            user_id: User identifier
            photos: List of (file_data, filename) tuples
            progress_callback: Optional callback for overall progress

        Returns:
            list[dict]: List of upload results

        Raises:
            StorageError: If batch upload fails
        """
        results = []
        total_files = len(photos)

        try:
            for i, (file_data, filename) in enumerate(photos):
                if progress_callback:
                    progress_callback(i, total_files, f"Uploading {filename}...")

                try:
                    result = self.upload_original_photo(user_id, file_data, filename)
                    results.append({"success": True, "filename": filename, "result": result})
                except StorageError as e:
                    logger.error(f"Failed to upload {filename}: {e}")
                    results.append({"success": False, "filename": filename, "error": str(e)})

            if progress_callback:
                successful = sum(1 for r in results if r["success"])
                progress_callback(
                    total_files, total_files, f"Batch upload completed: {successful}/{total_files} successful"
                )

            logger.info(f"Batch upload completed for user {user_id}: {len(results)} files processed")
            return results

        except Exception as e:
            raise StorageError(f"Batch upload failed: {e}") from e

    def get_upload_url(self, user_id: str, filename: str, expiration: int = 3600) -> str:
        """
        Generate a signed URL for direct upload to GCS.

        Args:
            user_id: User identifier
            filename: Target filename
            expiration: URL expiration time in seconds

        Returns:
            str: Signed upload URL

        Raises:
            StorageError: If URL generation fails
        """
        try:
            gcs_path = self._get_user_original_path(user_id, filename)
            blob = self.photos_bucket.blob(gcs_path)

            # Generate signed URL for PUT operation
            expiration_time = datetime.now() + timedelta(seconds=expiration)
            upload_url: str = blob.generate_signed_url(
                expiration=expiration_time, method="PUT", content_type=self._get_content_type(filename)
            )

            logger.debug(f"Generated upload URL for: {gcs_path} (expires in {expiration}s)")
            return upload_url

        except GoogleCloudError as e:
            raise StorageError(f"Failed to generate upload URL for '{filename}': {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error generating upload URL: {e}") from e

    def check_bucket_exists(self) -> bool:
        """
        Check if the configured bucket exists and is accessible.

        Returns:
            bool: True if bucket exists and is accessible
        """
        try:
            self.photos_bucket.reload()
            return True
        except NotFound:
            logger.error(f"Bucket not found: {self.photos_bucket_name}")
            return False
        except Exception as e:
            logger.error(f"Error checking bucket: {e}")
            return False

    def file_exists(self, gcs_path: str) -> bool:
        """
        Check if a file exists in GCS.

        Args:
            gcs_path: Path to the file in GCS

        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            # For database files, use the database bucket
            if gcs_path.startswith("databases/"):
                if not self.database_bucket_name:
                    raise StorageError("Database bucket not configured")
                database_client = storage.Client(project=self.project_id)
                database_bucket = database_client.bucket(self.database_bucket_name)
                blob = database_bucket.blob(gcs_path)
            else:
                # For regular files, use the photos bucket
                blob = self.photos_bucket.blob(gcs_path)

            exists: bool = blob.exists()
            return exists
        except Exception as e:
            logger.error(f"Error checking file existence for '{gcs_path}': {e}")
            raise StorageError(f"Failed to check file existence: {e}") from e

    def upload_database_file(self, user_id: str, file_data: bytes, filename: str) -> dict[str, str]:
        """
        Upload database file to the database bucket.

        Args:
            user_id: User identifier
            file_data: Database file data as bytes
            filename: Database filename (e.g., 'metadata.db')

        Returns:
            dict: Upload result with GCS path and metadata

        Raises:
            StorageError: If upload fails
        """
        try:
            # Create database path: databases/{user_id}/{filename}
            gcs_path = f"databases/{user_id}/{filename}"

            # Use database bucket
            blob = self.database_bucket.blob(gcs_path)

            # Set metadata
            blob.metadata = {
                "user_id": user_id,
                "filename": filename,
                "upload_timestamp": datetime.now().isoformat(),
                "file_type": "database",
                "content_type": "application/octet-stream",
            }

            # Upload the file
            blob.upload_from_string(file_data, content_type="application/octet-stream")

            logger.info(
                "database_file_uploaded",
                user_id=user_id,
                filename=filename,
                gcs_path=gcs_path,
                bucket=self.database_bucket.name,
                file_size=len(file_data),
            )

            return {
                "gcs_path": gcs_path,
                "bucket": self.database_bucket.name,
                "filename": filename,
                "file_size": str(len(file_data)),
                "upload_timestamp": datetime.now().isoformat(),
            }

        except GoogleCloudError as e:
            logger.error("database_upload_failed", user_id=user_id, filename=filename, error=str(e))
            raise StorageError(f"Failed to upload database file '{filename}': {e}") from e
        except Exception as e:
            logger.error("database_upload_error", user_id=user_id, filename=filename, error=str(e))
            raise StorageError(f"Unexpected error uploading database file '{filename}': {e}") from e

    def download_database_file(self, user_id: str, filename: str) -> bytes:
        """
        Download database file from the database bucket.

        Args:
            user_id: User identifier
            filename: Database filename (e.g., 'metadata.db')

        Returns:
            bytes: Database file data

        Raises:
            StorageError: If download fails
        """
        try:
            gcs_path = f"databases/{user_id}/{filename}"
            blob = self.database_bucket.blob(gcs_path)

            if not blob.exists():
                raise StorageError(f"Database file not found: {gcs_path}")

            file_data: bytes = blob.download_as_bytes()

            logger.info(
                "database_file_downloaded",
                user_id=user_id,
                filename=filename,
                gcs_path=gcs_path,
                file_size=len(file_data),
            )

            return file_data

        except GoogleCloudError as e:
            logger.error("database_download_failed", user_id=user_id, filename=filename, error=str(e))
            raise StorageError(f"Failed to download database file '{filename}': {e}") from e
        except Exception as e:
            logger.error("database_download_error", user_id=user_id, filename=filename, error=str(e))
            raise StorageError(f"Unexpected error downloading database file '{filename}': {e}") from e


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
