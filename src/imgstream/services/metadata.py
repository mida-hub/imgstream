"""Metadata service for managing photo metadata with DuckDB."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from google.cloud.exceptions import NotFound

from ..error_handling import DatabaseError, StorageError
from ..logging_config import get_logger, log_error, log_performance, log_user_action
from ..models.database import DatabaseManager, create_database, get_database_manager
from ..models.photo import PhotoMetadata
from .storage import get_storage_service

logger = get_logger(__name__)

# Global thread pool for async operations
_sync_executor: ThreadPoolExecutor | None = None
_sync_executor_lock = threading.Lock()


def get_sync_executor() -> ThreadPoolExecutor:
    """Get or create the global sync executor."""
    global _sync_executor
    if _sync_executor is None:
        with _sync_executor_lock:
            if _sync_executor is None:
                _sync_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gcs-sync")
    return _sync_executor


def shutdown_sync_executor() -> None:
    """Shutdown the global sync executor."""
    global _sync_executor
    if _sync_executor is not None:
        with _sync_executor_lock:
            if _sync_executor is not None:
                _sync_executor.shutdown(wait=True)
                _sync_executor = None


# Keep backward compatibility alias
MetadataError = DatabaseError


class MetadataService:
    """Service for managing photo metadata with DuckDB and GCS synchronization."""

    def __init__(self, user_id: str, temp_dir: str = "/tmp"):  # nosec B108
        """
        Initialize metadata service for a specific user.

        Args:
            user_id: User identifier
            temp_dir: Temporary directory for local database files

        Raises:
            MetadataError: If initialization fails
        """
        self.user_id = user_id
        self.temp_dir = Path(temp_dir)
        self.local_db_path = self.temp_dir / f"metadata_{user_id}.db"
        self.gcs_db_path = f"databases/{user_id}/metadata.db"

        # Initialize storage service
        try:
            self.storage_service = get_storage_service()
        except Exception as e:
            raise MetadataError(f"Failed to initialize storage service: {e}") from e

        # Database manager will be initialized when needed
        self._db_manager: DatabaseManager | None = None

        # Async sync management
        self._sync_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"metadata-sync-{user_id}")
        self._sync_lock = threading.Lock()
        self._last_sync_time: datetime | None = None
        self._sync_pending = False
        self._sync_enabled = True

        logger.info(
            "metadata_service_initialized",
            user_id=user_id,
            local_db_path=str(self.local_db_path),
            gcs_db_path=self.gcs_db_path,
        )

    @property
    def db_manager(self) -> DatabaseManager:
        """Get database manager, initializing if needed."""
        if self._db_manager is None:
            self._db_manager = get_database_manager(str(self.local_db_path), create_if_missing=True)
        return self._db_manager

    def ensure_local_database(self) -> bool:
        """
        Ensure local database exists, downloading from GCS if needed.

        Returns:
            bool: True if database was downloaded from GCS, False if created new

        Raises:
            MetadataError: If database setup fails
        """
        try:
            # Check if local database already exists
            if self.local_db_path.exists():
                logger.debug("local_database_exists", user_id=self.user_id, path=str(self.local_db_path))
                return False

            # Try to download from GCS
            if self._download_from_gcs():
                log_user_action(self.user_id, "database_downloaded_from_gcs", gcs_path=self.gcs_db_path)
                return True
            else:
                # Create new database
                self._create_new_database()
                log_user_action(self.user_id, "new_database_created", local_path=str(self.local_db_path))
                return False

        except Exception as e:
            raise MetadataError(f"Failed to ensure local database: {e}") from e

    def _download_from_gcs(self) -> bool:
        """
        Download database file from GCS.

        Returns:
            bool: True if successfully downloaded, False if not found

        Raises:
            MetadataError: If download fails
        """
        try:
            # Check if database exists in GCS
            if not self._gcs_database_exists():
                return False

            # Download database file from database bucket
            db_data = self.storage_service.download_database_file(self.user_id, "metadata.db")

            # Ensure temp directory exists
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # Write to local file
            with open(self.local_db_path, "wb") as f:
                f.write(db_data)

            # Verify the downloaded database
            self._verify_database_integrity()

            return True

        except NotFound:
            logger.debug("gcs_database_not_found", user_id=self.user_id, gcs_path=self.gcs_db_path)
            return False
        except Exception as e:
            # Clean up partial download
            if self.local_db_path.exists():
                self.local_db_path.unlink()
            log_error(e, {"operation": "download_from_gcs", "user_id": self.user_id, "gcs_path": self.gcs_db_path})
            raise MetadataError(f"Failed to download database from GCS: {e}") from e

    def _gcs_database_exists(self) -> bool:
        """Check if database exists in GCS."""
        try:
            # Try to get file metadata from database bucket
            self.storage_service.download_database_file(self.user_id, "metadata.db")
            return True
        except (StorageError, NotFound):
            return False
        except Exception:
            return False

    def _create_new_database(self) -> None:
        """Create a new local database with schema."""
        try:
            # Ensure temp directory exists
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # Create database with schema
            create_database(str(self.local_db_path))

            logger.info("new_database_created", user_id=self.user_id, local_path=str(self.local_db_path))

        except Exception as e:
            # Clean up on failure
            if self.local_db_path.exists():
                self.local_db_path.unlink()
            log_error(
                e, {"operation": "create_new_database", "user_id": self.user_id, "local_path": str(self.local_db_path)}
            )
            raise MetadataError(f"Failed to create new database: {e}") from e

    def _verify_database_integrity(self) -> None:
        """Verify database integrity and schema."""
        try:
            with self.db_manager as db:
                # Verify schema exists
                if not db.verify_schema():
                    raise MetadataError("Database schema verification failed")

        except Exception as e:
            raise MetadataError(f"Database integrity check failed: {e}") from e

    def upload_to_gcs(self, force: bool = False) -> bool:
        """
        Upload local database to GCS.

        Args:
            force: Force upload even if file hasn't changed

        Returns:
            bool: True if uploaded, False if skipped

        Raises:
            MetadataError: If upload fails
        """
        try:
            if not self.local_db_path.exists():
                raise MetadataError("Local database does not exist")

            # Read database file
            with open(self.local_db_path, "rb") as f:
                db_data = f.read()

            # Upload to GCS database bucket
            result = self.storage_service.upload_database_file(self.user_id, db_data, "metadata.db")

            log_user_action(
                self.user_id, "database_uploaded_to_gcs", gcs_path=result["gcs_path"], file_size=len(db_data)
            )
            return True

        except Exception as e:
            log_error(e, {"operation": "upload_to_gcs", "user_id": self.user_id, "local_path": str(self.local_db_path)})
            raise MetadataError(f"Failed to upload database to GCS: {e}") from e

    def disable_async_sync(self) -> None:
        """Disable async sync operations."""
        self._sync_enabled = False
        log_user_action(self.user_id, "async_sync_disabled")

    def enable_async_sync(self) -> None:
        """Enable async sync operations."""
        self._sync_enabled = True
        log_user_action(self.user_id, "async_sync_enabled")

    def get_database_info(self) -> dict:
        """
        Get information about the database.

        Returns:
            dict: Database information

        Raises:
            MetadataError: If getting info fails
        """
        try:
            info = {
                "user_id": self.user_id,
                "local_path": str(self.local_db_path),
                "gcs_path": self.gcs_db_path,
                "local_exists": self.local_db_path.exists(),
                "gcs_exists": self._gcs_database_exists(),
            }

            if info["local_exists"]:
                stat = self.local_db_path.stat()
                info.update({"local_size": stat.st_size, "local_modified": stat.st_mtime})

                # Get table info
                try:
                    with self.db_manager as db:
                        table_info = db.get_table_info()
                        info["table_info"] = table_info
                except Exception as e:
                    logger.warning("table_info_failed", user_id=self.user_id, error=str(e))
                    info["table_info"] = None

            return info

        except Exception as e:
            raise MetadataError(f"Failed to get database info: {e}") from e

    def cleanup_local_database(self) -> None:
        """Clean up local database file."""
        try:
            # Shutdown sync executor
            if hasattr(self, "_sync_executor"):
                self._sync_executor.shutdown(wait=True)

            if self._db_manager:
                self._db_manager.close()
                self._db_manager = None

            if self.local_db_path.exists():
                self.local_db_path.unlink()
                log_user_action(self.user_id, "local_database_cleaned_up", local_path=str(self.local_db_path))

        except Exception as e:
            log_error(
                e,
                {"operation": "cleanup_local_database", "user_id": self.user_id, "local_path": str(self.local_db_path)},
            )

    def force_reload_from_gcs(self) -> bool:
        """
        Force reload database from GCS by deleting local file and re-downloading.

        This is useful for development/testing when the local database becomes corrupted
        or when you want to reset to the GCS version.

        Returns:
            bool: True if successfully reloaded from GCS, False if no GCS database exists

        Raises:
            MetadataError: If reload fails
        """
        try:
            logger.info("force_reload_from_gcs_started", user_id=self.user_id, local_path=str(self.local_db_path))

            # Close existing database connection
            if self._db_manager:
                self._db_manager.close()
                self._db_manager = None

            # Remove local database file if it exists
            if self.local_db_path.exists():
                self.local_db_path.unlink()
                logger.info(
                    "local_database_removed_for_reload", user_id=self.user_id, local_path=str(self.local_db_path)
                )

            # Check if GCS database exists
            if not self._gcs_database_exists():
                logger.warning("force_reload_no_gcs_database", user_id=self.user_id, gcs_path=self.gcs_db_path)
                # Create new database since no GCS version exists
                self._create_new_database()
                log_user_action(self.user_id, "force_reload_created_new_database", local_path=str(self.local_db_path))
                return False

            # Download from GCS
            if self._download_from_gcs():
                log_user_action(
                    self.user_id,
                    "force_reload_from_gcs_completed",
                    gcs_path=self.gcs_db_path,
                    local_path=str(self.local_db_path),
                )
                return True
            else:
                # Fallback to creating new database
                self._create_new_database()
                log_user_action(self.user_id, "force_reload_fallback_new_database", local_path=str(self.local_db_path))
                return False

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "force_reload_from_gcs",
                    "user_id": self.user_id,
                    "local_path": str(self.local_db_path),
                    "gcs_path": self.gcs_db_path,
                },
            )
            raise MetadataError(f"Failed to force reload database from GCS: {e}") from e

    # Async Sync Methods

    def enable_sync(self) -> None:
        """Enable automatic GCS synchronization."""
        with self._sync_lock:
            self._sync_enabled = True
            log_user_action(self.user_id, "gcs_sync_enabled")

    def disable_sync(self) -> None:
        """Disable automatic GCS synchronization."""
        with self._sync_lock:
            self._sync_enabled = False
            log_user_action(self.user_id, "gcs_sync_disabled")

    def is_sync_enabled(self) -> bool:
        """Check if GCS synchronization is enabled."""
        with self._sync_lock:
            return self._sync_enabled

    def get_sync_status(self) -> dict:
        """
        Get current synchronization status.

        Returns:
            dict: Sync status information
        """
        with self._sync_lock:
            return {
                "enabled": self._sync_enabled,
                "pending": self._sync_pending,
                "last_sync_time": self._last_sync_time.isoformat() if self._last_sync_time else None,
                "user_id": self.user_id,
            }

    def _sync_to_gcs_async(self) -> None:
        """
        Internal method to sync database to GCS asynchronously.
        This runs in a background thread.
        """
        try:
            with self._sync_lock:
                if not self._sync_enabled:
                    logger.debug("async_sync_skipped_disabled", user_id=self.user_id)
                    return

                self._sync_pending = True

            # Perform the actual sync
            start_time = datetime.now()
            success = self.upload_to_gcs(force=False)
            duration = (datetime.now() - start_time).total_seconds()

            with self._sync_lock:
                self._sync_pending = False
                if success:
                    self._last_sync_time = datetime.now(UTC)
                    log_performance("async_sync_to_gcs", duration, user_id=self.user_id, success=True)
                    log_user_action(self.user_id, "async_sync_completed")
                else:
                    logger.warning("async_sync_failed", user_id=self.user_id)

        except Exception as e:
            with self._sync_lock:
                self._sync_pending = False
            log_error(e, {"operation": "async_sync_to_gcs", "user_id": self.user_id})

    def trigger_async_sync(self) -> None:
        """
        Trigger asynchronous synchronization to GCS.
        This method returns immediately and sync happens in background.
        """
        try:
            with self._sync_lock:
                if not self._sync_enabled:
                    logger.debug("async_sync_trigger_disabled", user_id=self.user_id)
                    return

                if self._sync_pending:
                    logger.debug("async_sync_already_pending", user_id=self.user_id)
                    return

            # Submit sync task to executor
            self._sync_executor.submit(self._sync_to_gcs_async)
            logger.debug("async_sync_task_submitted", user_id=self.user_id)

        except Exception as e:
            log_error(e, {"operation": "trigger_async_sync", "user_id": self.user_id})

    def wait_for_sync_completion(self, timeout: float = 30.0) -> bool:
        """
        Wait for any pending sync operations to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            bool: True if sync completed, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            with self._sync_lock:
                if not self._sync_pending:
                    return True

            time.sleep(0.1)

        logger.warning("sync_completion_timeout", user_id=self.user_id, timeout_seconds=timeout)
        return False

    def __enter__(self) -> "MetadataService":
        """Context manager entry."""
        self.ensure_local_database()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Context manager exit."""
        if self._db_manager:
            self._db_manager.close()

    # CRUD Operations

    def save_photo_metadata(self, photo_metadata: PhotoMetadata) -> None:
        """
        Save photo metadata to the database.

        Args:
            photo_metadata: PhotoMetadata instance to save

        Raises:
            MetadataError: If save operation fails
        """
        try:
            # Validate metadata
            if not photo_metadata.validate():
                raise MetadataError("Invalid photo metadata")

            # Ensure user_id matches
            if photo_metadata.user_id != self.user_id:
                raise MetadataError(f"User ID mismatch: expected {self.user_id}, got {photo_metadata.user_id}")

            # Ensure local database exists
            self.ensure_local_database()

            # Insert or update metadata
            with self.db_manager as db:
                # Check if photo already exists
                existing = db.execute_query("SELECT id FROM photos WHERE id = ?", (photo_metadata.id,))

                if existing:
                    # Update existing record
                    db.execute_query(
                        """UPDATE photos SET
                           user_id = ?, filename = ?, original_path = ?, thumbnail_path = ?,
                           created_at = ?, uploaded_at = ?, file_size = ?, mime_type = ?
                           WHERE id = ?""",
                        (
                            photo_metadata.user_id,
                            photo_metadata.filename,
                            photo_metadata.original_path,
                            photo_metadata.thumbnail_path,
                            photo_metadata.created_at.isoformat() if photo_metadata.created_at else None,
                            photo_metadata.uploaded_at.isoformat(),
                            photo_metadata.file_size,
                            photo_metadata.mime_type,
                            photo_metadata.id,
                        ),
                    )
                    log_user_action(
                        self.user_id,
                        "photo_metadata_updated",
                        photo_id=photo_metadata.id,
                        filename=photo_metadata.filename,
                    )
                else:
                    # Insert new record
                    db.execute_query(
                        """INSERT INTO photos
                           (id, user_id, filename, original_path, thumbnail_path,
                            created_at, uploaded_at, file_size, mime_type)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            photo_metadata.id,
                            photo_metadata.user_id,
                            photo_metadata.filename,
                            photo_metadata.original_path,
                            photo_metadata.thumbnail_path,
                            photo_metadata.created_at.isoformat() if photo_metadata.created_at else None,
                            photo_metadata.uploaded_at.isoformat(),
                            photo_metadata.file_size,
                            photo_metadata.mime_type,
                        ),
                    )
                    log_user_action(
                        self.user_id,
                        "photo_metadata_saved",
                        photo_id=photo_metadata.id,
                        filename=photo_metadata.filename,
                        file_size=photo_metadata.file_size,
                    )

            # Trigger async sync after successful save
            self.trigger_async_sync()

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "save_photo_metadata",
                    "user_id": self.user_id,
                    "photo_id": photo_metadata.id,
                    "filename": photo_metadata.filename,
                },
            )
            raise MetadataError(f"Failed to save photo metadata: {e}") from e

    def update_photo_metadata(self, photo_metadata: PhotoMetadata, preserve_creation_info: bool = True) -> None:
        """
        Update existing photo metadata in the database.

        This method is specifically designed for overwrite operations where we want to
        preserve the original creation date and photo ID while updating other fields.

        Args:
            photo_metadata: PhotoMetadata instance with updated information
            preserve_creation_info: Whether to preserve original created_at and id from existing record

        Raises:
            MetadataError: If update operation fails or photo doesn't exist
        """
        try:
            # Validate metadata
            if not photo_metadata.validate():
                raise MetadataError("Invalid photo metadata")

            # Ensure user_id matches
            if photo_metadata.user_id != self.user_id:
                raise MetadataError(f"User ID mismatch: expected {self.user_id}, got {photo_metadata.user_id}")

            # Ensure local database exists
            self.ensure_local_database()

            with self.db_manager as db:
                if preserve_creation_info:
                    # Get existing record to preserve creation info
                    existing = db.execute_query(
                        "SELECT id, created_at FROM photos WHERE filename = ? AND user_id = ?",
                        (photo_metadata.filename, self.user_id),
                    )

                    if not existing:
                        raise MetadataError(f"Photo with filename '{photo_metadata.filename}' not found for update")

                    existing_id, existing_created_at = existing[0]

                    # Update with preserved creation info
                    db.execute_query(
                        """UPDATE photos SET
                           original_path = ?, thumbnail_path = ?, uploaded_at = ?, 
                           file_size = ?, mime_type = ?
                           WHERE id = ? AND user_id = ?""",
                        (
                            photo_metadata.original_path,
                            photo_metadata.thumbnail_path,
                            photo_metadata.uploaded_at.isoformat(),
                            photo_metadata.file_size,
                            photo_metadata.mime_type,
                            existing_id,
                            self.user_id,
                        ),
                    )

                    log_user_action(
                        self.user_id,
                        "photo_metadata_overwrite_updated",
                        photo_id=existing_id,
                        filename=photo_metadata.filename,
                        preserved_creation_date=existing_created_at,
                        new_upload_date=photo_metadata.uploaded_at.isoformat(),
                    )
                else:
                    # Standard update without preservation
                    db.execute_query(
                        """UPDATE photos SET
                           original_path = ?, thumbnail_path = ?, created_at = ?, uploaded_at = ?, 
                           file_size = ?, mime_type = ?
                           WHERE id = ? AND user_id = ?""",
                        (
                            photo_metadata.original_path,
                            photo_metadata.thumbnail_path,
                            photo_metadata.created_at.isoformat() if photo_metadata.created_at else None,
                            photo_metadata.uploaded_at.isoformat(),
                            photo_metadata.file_size,
                            photo_metadata.mime_type,
                            photo_metadata.id,
                            self.user_id,
                        ),
                    )

                    # Check if any rows were affected
                    changes_result = db.execute_query("SELECT changes()")
                    rows_affected = changes_result[0][0] if changes_result else 0

                    if rows_affected == 0:
                        raise MetadataError(f"Photo with ID '{photo_metadata.id}' not found for update")

                    log_user_action(
                        self.user_id,
                        "photo_metadata_standard_updated",
                        photo_id=photo_metadata.id,
                        filename=photo_metadata.filename,
                    )

            # Trigger async sync after successful update
            self.trigger_async_sync()

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "update_photo_metadata",
                    "user_id": self.user_id,
                    "photo_id": photo_metadata.id,
                    "filename": photo_metadata.filename,
                    "preserve_creation_info": preserve_creation_info,
                },
            )
            raise MetadataError(f"Failed to update photo metadata: {e}") from e

    def save_or_update_photo_metadata(self, photo_metadata: PhotoMetadata, is_overwrite: bool = False) -> None:
        """
        Save or update photo metadata based on whether it's an overwrite operation.

        This method provides a unified interface for both new uploads and overwrites,
        automatically choosing the appropriate operation based on the is_overwrite flag.

        Args:
            photo_metadata: PhotoMetadata instance to save or update
            is_overwrite: True if this is an overwrite operation, False for new upload

        Raises:
            MetadataError: If save or update operation fails
        """
        try:
            if is_overwrite:
                # For overwrites, use update method with creation info preservation
                self.update_photo_metadata(photo_metadata, preserve_creation_info=True)
                logger.info(
                    "photo_metadata_overwrite_completed",
                    user_id=self.user_id,
                    filename=photo_metadata.filename,
                    photo_id=photo_metadata.id,
                )
            else:
                # For new uploads, use standard save method
                self.save_photo_metadata(photo_metadata)
                logger.info(
                    "photo_metadata_new_save_completed",
                    user_id=self.user_id,
                    filename=photo_metadata.filename,
                    photo_id=photo_metadata.id,
                )

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "save_or_update_photo_metadata",
                    "user_id": self.user_id,
                    "photo_id": photo_metadata.id,
                    "filename": photo_metadata.filename,
                    "is_overwrite": is_overwrite,
                },
            )
            raise MetadataError(f"Failed to save or update photo metadata: {e}") from e

    def get_photo_by_id(self, photo_id: str) -> PhotoMetadata | None:
        """
        Get photo metadata by ID.

        Args:
            photo_id: Photo ID to retrieve

        Returns:
            PhotoMetadata instance or None if not found

        Raises:
            MetadataError: If retrieval fails
        """
        try:
            self.ensure_local_database()

            with self.db_manager as db:
                result = db.execute_query(
                    """SELECT id, user_id, filename, original_path, thumbnail_path,
                              created_at, uploaded_at, file_size, mime_type
                       FROM photos WHERE id = ? AND user_id = ?""",
                    (photo_id, self.user_id),
                )

                if not result:
                    return None

                row = result[0]
                return PhotoMetadata(
                    id=row[0],
                    user_id=row[1],
                    filename=row[2],
                    original_path=row[3],
                    thumbnail_path=row[4],
                    created_at=row[5],
                    uploaded_at=row[6],
                    file_size=row[7],
                    mime_type=row[8],
                )

        except Exception as e:
            log_error(e, {"operation": "get_photo_by_id", "user_id": self.user_id, "photo_id": photo_id})
            raise MetadataError(f"Failed to get photo by ID: {e}") from e

    def get_photos_by_date(self, limit: int = 50, offset: int = 0) -> list[PhotoMetadata]:
        """
        Get photos ordered by creation date (newest first) with pagination.

        Args:
            limit: Maximum number of photos to return
            offset: Number of photos to skip

        Returns:
            List of PhotoMetadata instances

        Raises:
            MetadataError: If retrieval fails
        """
        try:
            self.ensure_local_database()

            with self.db_manager as db:
                result = db.execute_query(
                    """SELECT id, user_id, filename, original_path, thumbnail_path,
                              created_at, uploaded_at, file_size, mime_type
                       FROM photos
                       WHERE user_id = ?
                       ORDER BY COALESCE(created_at, uploaded_at) DESC
                       LIMIT ? OFFSET ?""",
                    (self.user_id, limit, offset),
                )

                photos = []
                for row in result:
                    photos.append(
                        PhotoMetadata(
                            id=row[0],
                            user_id=row[1],
                            filename=row[2],
                            original_path=row[3],
                            thumbnail_path=row[4],
                            created_at=row[5],
                            uploaded_at=row[6],
                            file_size=row[7],
                            mime_type=row[8],
                        )
                    )

                log_performance(
                    "get_photos_by_date", 0, user_id=self.user_id, photos_count=len(photos), limit=limit, offset=offset
                )

                logger.info(
                    "photos_retrieved_by_date",
                    user_id=self.user_id,
                    photos_count=len(photos),
                    limit=limit,
                    offset=offset,
                )
                return photos

        except Exception as e:
            log_error(e, {"operation": "get_photos_by_date", "user_id": self.user_id, "limit": limit, "offset": offset})
            raise MetadataError(f"Failed to get photos by date: {e}") from e

    def get_photos_count(self) -> int:
        """
        Get total count of photos for the user.

        Returns:
            Total number of photos

        Raises:
            MetadataError: If count fails
        """
        try:
            self.ensure_local_database()

            with self.db_manager as db:
                result = db.execute_query("SELECT COUNT(*) FROM photos WHERE user_id = ?", (self.user_id,))

                return result[0][0] if result else 0

        except Exception as e:
            log_error(e, {"operation": "get_photos_count", "user_id": self.user_id})
            raise MetadataError(f"Failed to get photos count: {e}") from e

    def delete_photo_metadata(self, photo_id: str) -> bool:
        """
        Delete photo metadata by ID.

        Args:
            photo_id: Photo ID to delete

        Returns:
            True if deleted, False if not found

        Raises:
            MetadataError: If deletion fails
        """
        try:
            self.ensure_local_database()

            with self.db_manager as db:
                db.execute_query("DELETE FROM photos WHERE id = ? AND user_id = ?", (photo_id, self.user_id))

                # Check if any rows were affected
                count_result = db.execute_query("SELECT changes()")

                deleted = count_result[0][0] > 0 if count_result else False

                if deleted:
                    logger.info(f"Deleted photo metadata: {photo_id}")
                    # Trigger async sync after successful deletion
                    self.trigger_async_sync()
                else:
                    logger.warning(f"Photo not found for deletion: {photo_id}")

                return deleted

        except Exception as e:
            raise MetadataError(f"Failed to delete photo metadata: {e}") from e

    def check_filename_exists(self, filename: str) -> dict | None:
        """
        Check if a photo with the given filename already exists for the user.

        Args:
            filename: Filename to check for collision

        Returns:
            dict: Existing photo information if found, None if not found
                  Contains: existing_photo (PhotoMetadata), existing_file_info (dict)

        Raises:
            MetadataError: If collision check fails
        """
        try:
            self.ensure_local_database()

            with self.db_manager as db:
                result = db.execute_query(
                    """SELECT id, user_id, filename, original_path, thumbnail_path,
                              created_at, uploaded_at, file_size, mime_type
                       FROM photos WHERE user_id = ? AND filename = ?""",
                    (self.user_id, filename),
                )

                if not result:
                    logger.debug("filename_collision_check_no_match", user_id=self.user_id, filename=filename)
                    return None

                # Found existing photo
                row = result[0]
                existing_photo = PhotoMetadata(
                    id=row[0],
                    user_id=row[1],
                    filename=row[2],
                    original_path=row[3],
                    thumbnail_path=row[4],
                    created_at=row[5],
                    uploaded_at=row[6],
                    file_size=row[7],
                    mime_type=row[8],
                )

                # Create file info for UI display
                existing_file_info = {
                    "upload_date": existing_photo.uploaded_at,
                    "file_size": existing_photo.file_size,
                    "creation_date": existing_photo.created_at,
                    "photo_id": existing_photo.id,
                }

                collision_info = {
                    "existing_photo": existing_photo,
                    "existing_file_info": existing_file_info,
                    "user_decision": "pending",
                    "warning_shown": False,
                }

                logger.info(
                    "filename_collision_detected",
                    user_id=self.user_id,
                    filename=filename,
                    existing_photo_id=existing_photo.id,
                    existing_upload_date=existing_photo.uploaded_at.isoformat() if existing_photo.uploaded_at else None,
                    existing_file_size=existing_photo.file_size,
                )

                return collision_info

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "check_filename_exists",
                    "user_id": self.user_id,
                    "filename": filename,
                },
            )
            raise MetadataError(f"Failed to check filename collision: {e}") from e

    def search_photos_by_filename(self, filename_pattern: str, limit: int = 50, offset: int = 0) -> list[PhotoMetadata]:
        """
        Search photos by filename pattern.

        Args:
            filename_pattern: Pattern to search for (supports SQL LIKE patterns)
            limit: Maximum number of photos to return
            offset: Number of photos to skip

        Returns:
            List of PhotoMetadata instances

        Raises:
            MetadataError: If search fails
        """
        try:
            self.ensure_local_database()

            with self.db_manager as db:
                result = db.execute_query(
                    """SELECT id, user_id, filename, original_path, thumbnail_path,
                              created_at, uploaded_at, file_size, mime_type
                       FROM photos
                       WHERE user_id = ? AND filename LIKE ?
                       ORDER BY COALESCE(created_at, uploaded_at) DESC
                       LIMIT ? OFFSET ?""",
                    (self.user_id, filename_pattern, limit, offset),
                )

                photos = []
                for row in result:
                    photos.append(
                        PhotoMetadata(
                            id=row[0],
                            user_id=row[1],
                            filename=row[2],
                            original_path=row[3],
                            thumbnail_path=row[4],
                            created_at=row[5],
                            uploaded_at=row[6],
                            file_size=row[7],
                            mime_type=row[8],
                        )
                    )

                logger.info(f"Found {len(photos)} photos matching pattern '{filename_pattern}'")
                return photos

        except Exception as e:
            raise MetadataError(f"Failed to search photos by filename: {e}") from e


# Global metadata service instances
_metadata_services: dict[str, MetadataService] = {}


def get_metadata_service(user_id: str, temp_dir: str = "/tmp") -> MetadataService:  # nosec B108
    """
    Get metadata service instance for a user.

    Args:
        user_id: User identifier
        temp_dir: Temporary directory for local database files

    Returns:
        MetadataService: Metadata service instance
    """
    if user_id not in _metadata_services:
        _metadata_services[user_id] = MetadataService(user_id, temp_dir)
    return _metadata_services[user_id]


def cleanup_metadata_services() -> None:
    """Clean up all metadata service instances."""
    for service in _metadata_services.values():
        service.cleanup_local_database()
    _metadata_services.clear()
