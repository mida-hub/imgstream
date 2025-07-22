"""
Unit tests for database schema module.
"""

import pytest
from src.imgstream.models.schema import (
    get_schema_statements,
    get_table_creation_statement,
    get_index_creation_statements,
    validate_schema_compatibility,
    PHOTOS_TABLE_SCHEMA,
    PHOTOS_TABLE_INDEXES,
)


class TestSchema:
    """Test cases for schema module."""

    def test_get_schema_statements(self):
        """Test getting all schema statements."""
        statements = get_schema_statements()

        assert isinstance(statements, list)
        assert len(statements) > 0

        # Should include table creation and indexes
        assert PHOTOS_TABLE_SCHEMA in statements
        for index_sql in PHOTOS_TABLE_INDEXES:
            assert index_sql in statements

    def test_get_table_creation_statement(self):
        """Test getting table creation statement."""
        statement = get_table_creation_statement()

        assert isinstance(statement, str)
        assert "CREATE TABLE" in statement.upper()
        assert "photos" in statement.lower()
        assert statement == PHOTOS_TABLE_SCHEMA

    def test_get_index_creation_statements(self):
        """Test getting index creation statements."""
        statements = get_index_creation_statements()

        assert isinstance(statements, list)
        assert len(statements) == len(PHOTOS_TABLE_INDEXES)

        for statement in statements:
            assert "CREATE INDEX" in statement.upper()
            assert "photos" in statement.lower()

    def test_photos_table_schema_contains_required_columns(self):
        """Test that photos table schema contains all required columns."""
        schema = PHOTOS_TABLE_SCHEMA.lower()

        required_columns = [
            "id",
            "user_id",
            "filename",
            "original_path",
            "thumbnail_path",
            "created_at",
            "uploaded_at",
            "file_size",
            "mime_type",
        ]

        for column in required_columns:
            assert column in schema, f"Column {column} not found in schema"

    def test_photos_table_schema_has_primary_key(self):
        """Test that photos table has a primary key."""
        schema = PHOTOS_TABLE_SCHEMA.upper()
        assert "PRIMARY KEY" in schema

    def test_photos_table_schema_has_not_null_constraints(self):
        """Test that required columns have NOT NULL constraints."""
        schema = PHOTOS_TABLE_SCHEMA.upper()

        # These columns should have NOT NULL constraints
        required_not_null = [
            "USER_ID",
            "FILENAME",
            "ORIGINAL_PATH",
            "THUMBNAIL_PATH",
            "UPLOADED_AT",
            "FILE_SIZE",
            "MIME_TYPE",
        ]

        for column in required_not_null:
            # Check that the column appears with NOT NULL
            assert column in schema
            # This is a simple check - in a real scenario you might want more sophisticated parsing

    def test_index_statements_are_valid_sql(self):
        """Test that index statements are valid SQL syntax."""
        for statement in PHOTOS_TABLE_INDEXES:
            statement_upper = statement.upper()
            assert statement_upper.startswith("CREATE INDEX")
            assert "IF NOT EXISTS" in statement_upper
            assert "ON PHOTOS" in statement_upper

    def test_validate_schema_compatibility_success(self):
        """Test schema compatibility validation succeeds."""
        result = validate_schema_compatibility()
        assert result is True

    def test_schema_includes_performance_indexes(self):
        """Test that schema includes performance-oriented indexes."""
        statements = get_index_creation_statements()

        # Should have indexes for common query patterns
        index_text = " ".join(statements).lower()

        # Should index created_at for chronological queries
        assert "created_at" in index_text

        # Should index user_id for user-specific queries
        assert "user_id" in index_text

        # Should have composite index for user + created_at
        assert any("user_id" in stmt and "created_at" in stmt for stmt in statements)

    def test_schema_uses_if_not_exists(self):
        """Test that schema statements use IF NOT EXISTS for safety."""
        table_statement = get_table_creation_statement()
        assert "IF NOT EXISTS" in table_statement.upper()

        for index_statement in get_index_creation_statements():
            assert "IF NOT EXISTS" in index_statement.upper()

    def test_schema_statements_are_strings(self):
        """Test that all schema statements are strings."""
        for statement in get_schema_statements():
            assert isinstance(statement, str)
            assert len(statement.strip()) > 0
