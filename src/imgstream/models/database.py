"""
Database initialization and management for imgstream application.

This module provides functions to initialize DuckDB databases and manage
database connections.
"""

import logging
from pathlib import Path
from typing import Any

import duckdb

from .schema import get_schema_statements, validate_schema_compatibility

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages DuckDB database connections and initialization.
    """

    def __init__(self, db_path: str):
        """
        Initialize DatabaseManager.

        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = db_path
        self._connection: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        """
        Get or create a database connection.

        Returns:
            DuckDB connection object
        """
        if self._connection is None:
            self._connection = duckdb.connect(self.db_path)
            logger.info(f"Connected to DuckDB database at {self.db_path}")

        return self._connection

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("Closed DuckDB database connection")

    def initialize_schema(self) -> None:
        """
        Initialize the database schema.

        Creates all necessary tables and indexes if they don't exist.

        Raises:
            RuntimeError: If schema validation fails
            duckdb.Error: If database operations fail
        """
        if not validate_schema_compatibility():
            raise RuntimeError("Schema is not compatible with PhotoMetadata model")

        conn = self.connect()

        try:
            # Execute all schema creation statements
            for statement in get_schema_statements():
                logger.debug(f"Executing SQL: {statement}")
                conn.execute(statement)

            conn.commit()
            logger.info("Database schema initialized successfully")

        except duckdb.Error as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise

    def verify_schema(self) -> bool:
        """
        Verify that the database schema is correctly set up.

        Returns:
            True if schema is valid, False otherwise
        """
        conn = self.connect()

        try:
            # Check if photos table exists
            result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='photos'").fetchone()

            if not result:
                logger.warning("Photos table does not exist")
                return False

            # Check table structure
            columns = conn.execute("PRAGMA table_info(photos)").fetchall()
            column_names = {col[1] for col in columns}  # col[1] is column name

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

            missing_columns = required_columns - column_names
            if missing_columns:
                logger.warning(f"Missing columns: {missing_columns}")
                return False

            logger.info("Database schema verification successful")
            return True

        except duckdb.Error as e:
            logger.error(f"Schema verification failed: {e}")
            return False

    def get_table_info(self) -> list[dict]:
        """
        Get information about the photos table structure.

        Returns:
            List of dictionaries containing column information
        """
        conn = self.connect()

        try:
            columns = conn.execute("PRAGMA table_info(photos)").fetchall()
            return [
                {
                    "cid": col[0],
                    "name": col[1],
                    "type": col[2],
                    "notnull": bool(col[3]),
                    "default_value": col[4],
                    "pk": bool(col[5]),
                }
                for col in columns
            ]
        except duckdb.Error as e:
            logger.error(f"Failed to get table info: {e}")
            return []

    def execute_query(self, query: str, parameters: tuple | None = None) -> list[tuple]:
        """
        Execute a SQL query and return results.

        Args:
            query: SQL query string
            parameters: Optional query parameters

        Returns:
            List of result tuples

        Raises:
            duckdb.Error: If query execution fails
        """
        conn = self.connect()

        try:
            if parameters:
                result = conn.execute(query, parameters)
            else:
                result = conn.execute(query)

            return result.fetchall()

        except duckdb.Error as e:
            logger.error(f"Query execution failed: {query}, error: {e}")
            raise

    def __enter__(self) -> "DatabaseManager":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


def create_database(db_path: str) -> DatabaseManager:
    """
    Create and initialize a new DuckDB database.

    Args:
        db_path: Path where the database file should be created

    Returns:
        Initialized DatabaseManager instance

    Raises:
        RuntimeError: If database creation fails
    """
    try:
        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Create database manager and initialize schema
        db_manager = DatabaseManager(db_path)
        db_manager.initialize_schema()

        # Verify the schema was created correctly
        if not db_manager.verify_schema():
            raise RuntimeError("Schema verification failed after creation")

        logger.info(f"Successfully created database at {db_path}")
        return db_manager

    except Exception as e:
        logger.error(f"Failed to create database at {db_path}: {e}")
        raise RuntimeError(f"Database creation failed: {e}") from e


def get_database_manager(db_path: str, create_if_missing: bool = True) -> DatabaseManager:
    """
    Get a DatabaseManager instance, optionally creating the database if it doesn't exist.

    Args:
        db_path: Path to the database file
        create_if_missing: Whether to create the database if it doesn't exist

    Returns:
        DatabaseManager instance

    Raises:
        FileNotFoundError: If database doesn't exist and create_if_missing is False
        RuntimeError: If database operations fail
    """
    db_file = Path(db_path)

    if not db_file.exists():
        if create_if_missing:
            return create_database(db_path)
        else:
            raise FileNotFoundError(f"Database file not found: {db_path}")

    # Database exists, create manager and verify schema
    db_manager = DatabaseManager(db_path)

    if not db_manager.verify_schema():
        logger.warning("Schema verification failed, reinitializing...")
        db_manager.initialize_schema()

    return db_manager
