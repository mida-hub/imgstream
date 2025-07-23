"""Metadata service for managing photo metadata with DuckDB."""

import logging
from pathlib import Path
from typing import Optional

from google.cloud.exceptions import NotFound

from ..models.database import DatabaseManager, create_database, get_database_manager
from .storage import StorageError, get_storage_service

logger = logging.getLogger(__name__)


class MetadataError(Exception):
    """Raised when metadata operations fail."""
    pass


class MetadataService:
    """Service for managing photo metadata with DuckDB and GCS synchronization."""

    def __init__(self, user_id: str, temp_dir: str = "/tmp"):
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

        logger.info(f"Initialized metadata service for user {user_id}")

    @property
    def db_manager(self) -> DatabaseManager:
        """Get database manager, initializing if needed."""
        if self._db_manager is None:
            self._db_manager = get_database_manager(
                str(self.local_db_path),
                create_if_missing=True
            )
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
                logger.debug(f"Local database already exists: {self.local_db_path}")
                return False

            # Try to download from GCS
            if self._download_from_gcs():
                logger.info(f"Downloaded database from GCS for user {self.user_id}")
                return True
            else:
                # Create new database
                self._create_new_database()
                logger.info(f"Created new database for user {self.user_id}")
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

            # Download database file
            db_data = self.storage_service.download_file(self.gcs_db_path)

            # Ensure temp directory exists
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # Write to local file
            with open(self.local_db_path, 'wb') as f:
                f.write(db_data)

            # Verify the downloaded database
            self._verify_database_integrity()

            return True

        except NotFound:
            logger.debug(f"Database not found in GCS: {self.gcs_db_path}")
            return False
        except Exception as e:
            # Clean up partial download
            if self.local_db_path.exists():
                self.local_db_path.unlink()
            raise MetadataError(f"Failed to download database from GCS: {e}") from e

    def _gcs_database_exists(self) -> bool:
        """Check if database exists in GCS."""
        try:
            # Try to get file metadata
            self.storage_service.download_file(self.gcs_db_path)
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

            logger.info(f"Created new database: {self.local_db_path}")

        except Exception as e:
            # Clean up on failure
            if self.local_db_path.exists():
                self.local_db_path.unlink()
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
            with open(self.local_db_path, 'rb') as f:
                db_data = f.read()

            # Upload to GCS
            result = self.storage_service.upload_original_photo(
                self.user_id,
                db_data,
                "metadata.db"
            )

            logger.info(f"Uploaded database to GCS: {result['gcs_path']}")
            return True

        except Exception as e:
            raise MetadataError(f"Failed to upload database to GCS: {e}") from e

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
                'user_id': self.user_id,
                'local_path': str(self.local_db_path),
                'gcs_path': self.gcs_db_path,
                'local_exists': self.local_db_path.exists(),
                'gcs_exists': self._gcs_database_exists()
            }

            if info['local_exists']:
                stat = self.local_db_path.stat()
                info.update({
                    'local_size': stat.st_size,
                    'local_modified': stat.st_mtime
                })

                # Get table info
                try:
                    with self.db_manager as db:
                        table_info = db.get_table_info()
                        info['table_info'] = table_info
                except Exception as e:
                    logger.warning(f"Failed to get table info: {e}")
                    info['table_info'] = None

            return info

        except Exception as e:
            raise MetadataError(f"Failed to get database info: {e}") from e

    def cleanup_local_database(self) -> None:
        """Clean up local database file."""
        try:
            if self._db_manager:
                self._db_manager.close()
                self._db_manager = None

            if self.local_db_path.exists():
                self.local_db_path.unlink()
                logger.info(f"Cleaned up local database: {self.local_db_path}")

        except Exception as e:
            logger.error(f"Failed to cleanup local database: {e}")

    def __enter__(self) -> 'MetadataService':
        """Context manager entry."""
        self.ensure_local_database()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Context manager exit."""
        if self._db_manager:
            self._db_manager.close()


# Global metadata service instances
_metadata_services: dict[str, MetadataService] = {}


def get_metadata_service(user_id: str, temp_dir: str = "/tmp") -> MetadataService:
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
