"""
Configuration and fixtures for E2E tests.
"""

import io
import os
import tempfile
import time
from typing import Any
from unittest.mock import Mock

import pytest
from PIL import Image

from tests.e2e.base import MockUser, DatabaseTestHelper, APITestClient


@pytest.fixture
def test_users():
    """Provide test users for E2E tests."""
    return {
        "user1": MockUser("test-user-1", "user1@example.com", "Test User 1"),
        "user2": MockUser("test-user-2", "user2@example.com", "Test User 2"),
        "admin": MockUser("admin-user", "admin@example.com", "Admin User"),
    }


@pytest.fixture
def test_image():
    """Provide test image data."""
    image = Image.new("RGB", (800, 600), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


@pytest.fixture
def test_large_image():
    """Provide large test image data."""
    image = Image.new("RGB", (4000, 3000), color="blue")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


@pytest.fixture
def test_heic_image():
    """Provide mock HEIC image data."""
    # Since we can't easily create real HEIC files in tests,
    # we'll create a JPEG and mock the HEIC detection
    image = Image.new("RGB", (2000, 1500), color="green")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


@pytest.fixture
def db_helper():
    """Provide database test helper."""
    temp_dir = tempfile.mkdtemp()
    helper = DatabaseTestHelper(temp_dir)
    yield helper
    helper.cleanup()
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def api_client():
    """Provide API test client."""
    base_url = os.getenv("TEST_APP_URL", "http://localhost:8501")
    return APITestClient(base_url)


@pytest.fixture
def temp_dir():
    """Provide temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_gcs_bucket():
    """Provide mock GCS bucket for testing."""
    mock_bucket = Mock()
    mock_bucket.name = "test-bucket"
    mock_bucket.blob.return_value = Mock()
    return mock_bucket


@pytest.fixture
def setup_test_env():
    """Set up test environment variables."""
    original_env = os.environ.copy()

    # Set test environment variables
    test_env = {
        "ENVIRONMENT": "production",  # Use production mode for E2E tests
        "PROJECT_ID": "test-project",
        "BUCKET_NAME": "test-bucket",
        "REGION": "us-central1",
        "DEV_USER_EMAIL": "dev@example.com",
        "DEV_USER_NAME": "Development User",
        "DEV_USER_ID": "dev-user-123",
    }

    os.environ.update(test_env)

    yield test_env

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_user_id():
    """Provide mock user ID for testing."""
    return "test-user-123"


@pytest.fixture
def sample_image_data():
    """Provide sample image data with metadata."""
    # Create test image data
    image = Image.new("RGB", (800, 600), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    image_data = buffer.getvalue()

    return {
        "filename": "sample.jpg",
        "data": image_data,
        "size": len(image_data),
        "width": 800,
        "height": 600,
        "format": "JPEG",
        "mime_type": "image/jpeg",
    }


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically set up test environment for all E2E tests."""
    # Set production environment for E2E tests
    original_env = os.environ.get("ENVIRONMENT")
    os.environ["ENVIRONMENT"] = "production"

    yield

    # Restore original environment
    if original_env is not None:
        os.environ["ENVIRONMENT"] = original_env
    elif "ENVIRONMENT" in os.environ:
        del os.environ["ENVIRONMENT"]
