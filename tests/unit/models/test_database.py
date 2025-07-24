"""
Unit tests for database module.
"""

import os
import tempfile
from unittest.mock import patch

import duckdb
import pytest

from src.imgstream.models.database import (
    DatabaseManager,
    create_database,
    get_database_manager,
)


class TestDatabaseManager:
    """Test cases for DatabaseManager class."""

    def test_init(self):
        """Test DatabaseManager initialization."""
        db_path = "/tmp/test.db"
        manager = DatabaseManager(db_path)

        assert manager.db_path == db_path
        assert manager._connection is None

    def test_connect_creates_connection(self):
        """Test that connect creates a DuckDB connection."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = DatabaseManager(db_path)
            conn = manager.connect()

            assert conn is not None
            assert isinstance(conn, duckdb.DuckDBPyConnection)
            assert manager._connection is conn

            # Second call should return same connection
            conn2 = manager.connect()
            assert conn2 is conn

            manager.close()

    def test_close_connection(self):
        """Test closing database connection."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = DatabaseManager(db_path)
            manager.connect()

            assert manager._connection is not None

            manager.close()
            assert manager._connection is None

    def test_context_manager(self):
        """Test DatabaseManager as context manager."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            with DatabaseManager(db_path) as manager:
                conn = manager.connect()
                assert conn is not None

            # Connection should be closed after context exit
            assert manager._connection is None

    def test_initialize_schema(self):
        """Test schema initialization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = DatabaseManager(db_path)
            manager.initialize_schema()

            # Verify table was created
            conn = manager.connect()
            result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='photos'").fetchone()
            assert result is not None

            manager.close()

    @patch("src.imgstream.models.database.validate_schema_compatibility")
    def test_initialize_schema_validation_failure(self, mock_validate):
        """Test schema initialization with validation failure."""
        mock_validate.return_value = False

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = DatabaseManager(db_path)

            with pytest.raises(RuntimeError, match="Schema is not compatible"):
                manager.initialize_schema()

    def test_verify_schema_success(self):
        """Test successful schema verification."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = DatabaseManager(db_path)
            manager.initialize_schema()

            result = manager.verify_schema()
            assert result is True

            manager.close()

    def test_verify_schema_missing_table(self):
        """Test schema verification with missing table."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = DatabaseManager(db_path)
            # Don't initialize schema

            result = manager.verify_schema()
            assert result is False

            manager.close()

    def test_get_table_info(self):
        """Test getting table information."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = DatabaseManager(db_path)
            manager.initialize_schema()

            table_info = manager.get_table_info()

            assert isinstance(table_info, list)
            assert len(table_info) > 0

            # Check that required columns are present
            column_names = {col["name"] for col in table_info}
            required_columns = {
                "id",
                "user_id",
                "filename",
                "original_path",
                "thumbnail_path",
                "created_at",
                "uploaded_at",
                "file_size",
                "mime_type",
            }

            assert required_columns.issubset(column_names)

            manager.close()

    def test_execute_query(self):
        """Test executing SQL queries."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = DatabaseManager(db_path)
            manager.initialize_schema()

            # Test simple query
            result = manager.execute_query("SELECT COUNT(*) FROM photos")
            assert result == [(0,)]  # Empty table

            # Test query with parameters
            manager.execute_query(
                """INSERT INTO photos (id, user_id, filename, original_path,
                   thumbnail_path, file_size, mime_type) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "test-id",
                    "user123",
                    "test.jpg",
                    "original/test.jpg",
                    "thumbs/test.jpg",
                    1024,
                    "image/jpeg",
                ),
            )

            result = manager.execute_query("SELECT COUNT(*) FROM photos")
            assert result == [(1,)]

            manager.close()

    def test_execute_query_error(self):
        """Test query execution error handling."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = DatabaseManager(db_path)

            with pytest.raises(duckdb.Error):
                manager.execute_query("SELECT * FROM nonexistent_table")

            manager.close()


class TestDatabaseFunctions:
    """Test cases for database utility functions."""

    def test_create_database(self):
        """Test database creation function."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = create_database(db_path)

            assert isinstance(manager, DatabaseManager)
            assert os.path.exists(db_path)

            # Verify schema was initialized
            assert manager.verify_schema() is True

            manager.close()

    def test_create_database_creates_parent_directory(self):
        """Test that create_database creates parent directories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "subdir", "test.db")

            manager = create_database(db_path)

            assert os.path.exists(db_path)
            assert os.path.exists(os.path.dirname(db_path))

            manager.close()

    def test_get_database_manager_existing_db(self):
        """Test getting manager for existing database."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            # Create database first
            original_manager = create_database(db_path)
            original_manager.close()

            # Get manager for existing database
            manager = get_database_manager(db_path, create_if_missing=False)

            assert isinstance(manager, DatabaseManager)
            assert manager.verify_schema() is True

            manager.close()

    def test_get_database_manager_missing_db_create_true(self):
        """Test getting manager for missing database with create_if_missing=True."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            manager = get_database_manager(db_path, create_if_missing=True)

            assert isinstance(manager, DatabaseManager)
            assert os.path.exists(db_path)
            assert manager.verify_schema() is True

            manager.close()

    def test_get_database_manager_missing_db_create_false(self):
        """Test getting manager for missing database with create_if_missing=False."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "nonexistent.db")

            with pytest.raises(FileNotFoundError):
                get_database_manager(db_path, create_if_missing=False)

    @patch("src.imgstream.models.database.DatabaseManager.verify_schema")
    def test_get_database_manager_reinitialize_schema(self, mock_verify):
        """Test that schema is reinitialized if verification fails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")

            # Create database first
            original_manager = create_database(db_path)
            original_manager.close()

            # Mock verification to fail first, then succeed
            mock_verify.side_effect = [False, True]

            with patch("src.imgstream.models.database.DatabaseManager.initialize_schema") as mock_init:
                manager = get_database_manager(db_path, create_if_missing=False)

                # Should have called initialize_schema due to failed verification
                mock_init.assert_called_once()

                manager.close()
