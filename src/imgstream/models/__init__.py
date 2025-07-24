"""
Models module for imgstream application.

This module contains data models and schemas:
- PhotoMetadata: Data class for photo metadata
- Database schemas and table definitions
- DatabaseManager: Database connection and schema management
"""

from .database import DatabaseManager, create_database, get_database_manager
from .photo import PhotoMetadata
from .schema import get_schema_statements, validate_schema_compatibility

__all__ = [
    "PhotoMetadata",
    "DatabaseManager",
    "create_database",
    "get_database_manager",
    "get_schema_statements",
    "validate_schema_compatibility",
]
