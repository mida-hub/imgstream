"""
Pytest configuration and fixtures for imgstream tests.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Generator, Any


@pytest.fixture
def mock_gcs_client() -> Generator[Mock, None, None]:
    """Mock Google Cloud Storage client."""
    with patch('google.cloud.storage.Client') as mock_client:
        yield mock_client


@pytest.fixture
def mock_duckdb_connection() -> Generator[Mock, None, None]:
    """Mock DuckDB connection."""
    with patch('duckdb.connect') as mock_connect:
        yield mock_connect


@pytest.fixture
def mock_streamlit() -> Generator[Mock, None, None]:
    """Mock Streamlit for testing."""
    with patch('streamlit.session_state', {}):
        yield


@pytest.fixture
def sample_image_data() -> bytes:
    """Sample image data for testing."""
    # Simple 1x1 pixel PNG image
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13'
        b'\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc```'
        b'\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
    )


@pytest.fixture
def sample_user_id() -> str:
    """Sample user ID for testing."""
    return "test-user@example.com"


@pytest.fixture
def sample_photo_metadata() -> dict[str, Any]:
    """Sample photo metadata for testing."""
    return {
        "id": "test-photo-123",
        "user_id": "test-user@example.com",
        "filename": "test-photo.jpg",
        "original_path": "photos/test-user@example.com/original/test-photo.jpg",
        "thumbnail_path": "photos/test-user@example.com/thumbs/test-photo_thumb.jpg",
        "created_at": "2024-01-01T12:00:00",
        "uploaded_at": "2024-01-01T12:05:00",
        "file_size": 1024000,
        "mime_type": "image/jpeg"
    }
