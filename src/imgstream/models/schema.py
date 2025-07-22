"""
Database schema definitions for imgstream application.

This module contains SQL schema definitions and database initialization functions.
"""

from typing import List

# SQL schema for the photos table
PHOTOS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    thumbnail_path TEXT NOT NULL,
    created_at TIMESTAMP,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    file_size INTEGER NOT NULL,
    mime_type TEXT NOT NULL
);
"""

# Indexes for performance optimization
PHOTOS_TABLE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_photos_created_at ON photos(created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_photos_user_id ON photos(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_photos_uploaded_at ON photos(uploaded_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_photos_user_created ON photos(user_id, created_at DESC);",
]

# All schema creation statements
ALL_SCHEMA_STATEMENTS = [PHOTOS_TABLE_SCHEMA] + PHOTOS_TABLE_INDEXES


def get_schema_statements() -> List[str]:
    """
    Get all database schema creation statements.

    Returns:
        List of SQL statements to create tables and indexes
    """
    return ALL_SCHEMA_STATEMENTS


def get_table_creation_statement() -> str:
    """
    Get the photos table creation statement.

    Returns:
        SQL statement to create the photos table
    """
    return PHOTOS_TABLE_SCHEMA


def get_index_creation_statements() -> List[str]:
    """
    Get all index creation statements.

    Returns:
        List of SQL statements to create indexes
    """
    return PHOTOS_TABLE_INDEXES


def validate_schema_compatibility() -> bool:
    """
    Validate that the schema is compatible with PhotoMetadata model.

    This function checks that all required fields from PhotoMetadata
    are represented in the database schema.

    Returns:
        True if schema is compatible, False otherwise
    """
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

    # Extract column names from schema (simple parsing)
    schema_lower = PHOTOS_TABLE_SCHEMA.lower()

    for column in required_columns:
        if column not in schema_lower:
            return False

    return True
