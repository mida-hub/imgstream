"""
Base classes and utilities for end-to-end tests.
"""

import io
import os
import tempfile
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests
from PIL import Image

from src.imgstream.services.image_processor import ImageProcessor
from src.imgstream.services.metadata import MetadataService
from src.imgstream.services.storage import StorageService


class MockUser:
    """Mock user for testing."""

    def __init__(self, user_id: str, email: str, name: str):
        self.user_id = user_id
        self.email = email
        self.name = name

    def to_dict(self) -> dict[str, str]:
        return {"user_id": self.user_id, "email": self.email, "name": self.name}


class E2ETestBase:
    """Base class for end-to-end tests."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Set up test environment for each test."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()

        # Mock users for testing
        self.test_users = {
            "user1": MockUser("test-user-1", "user1@example.com", "Test User 1"),
            "user2": MockUser("test-user-2", "user2@example.com", "Test User 2"),
            "admin": MockUser("admin-user", "admin@example.com", "Admin User"),
        }

        # Test configuration
        self.test_config = {"project_id": "test-project", "bucket_name": "test-bucket", "region": "us-central1"}

        yield

        # Cleanup
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_image(self, width: int = 800, height: int = 600, image_format: str = "JPEG") -> bytes:
        """Create a test image for upload testing."""
        image = Image.new("RGB", (width, height), color="red")
        buffer = io.BytesIO()
        image.save(buffer, format=image_format, quality=95)
        return buffer.getvalue()

    def create_test_heic_image(self) -> bytes:
        """Create a mock HEIC image for testing."""
        # Since we can't easily create real HEIC files in tests,
        # we'll create a JPEG and mock the HEIC detection
        return self.create_test_image(image_format="JPEG")

    def mock_iap_headers(self, user: MockUser) -> dict[str, str]:
        """Create mock IAP headers for authentication testing."""

        import jwt

        # Create a mock JWT token
        payload = {
            "iss": "https://cloud.google.com/iap",
            "aud": "/projects/123456789/global/backendServices/test-service",
            "email": user.email,
            "sub": user.user_id,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }

        # Create unsigned token for testing (in real scenarios, this would be signed)
        token = jwt.encode(payload, "secret", algorithm="HS256")

        return {
            "X-Goog-IAP-JWT-Assertion": token,
            "X-Goog-Authenticated-User-Email": user.email,
            "X-Goog-Authenticated-User-ID": user.user_id,
        }

    def setup_mock_services(self, user: MockUser):
        """Set up mock services for testing."""
        # Mock storage service
        mock_storage = Mock(spec=StorageService)
        mock_storage.upload_original_photo.return_value = f"original/{user.user_id}/test-image.jpg"
        mock_storage.upload_thumbnail.return_value = f"thumbs/{user.user_id}/test-image.jpg"
        mock_storage.get_signed_url.return_value = "https://storage.googleapis.com/signed-url"

        # Mock metadata service
        mock_metadata = Mock(spec=MetadataService)
        mock_metadata.save_photo_metadata.return_value = True
        mock_metadata.get_photos_by_date.return_value = []
        mock_metadata.trigger_async_sync.return_value = None

        # Mock image processor
        mock_image_processor = Mock(spec=ImageProcessor)
        mock_image_processor.extract_metadata.return_value = Mock(
            filename="test-image.jpg", file_size=1024, width=800, height=600, format="JPEG", created_at=time.time()
        )
        mock_image_processor.generate_thumbnail.return_value = self.create_test_image(300, 300)
        mock_image_processor.is_supported_format.return_value = True

        return {"storage": mock_storage, "metadata": mock_metadata, "image_processor": mock_image_processor}


class StreamlitE2ETest(E2ETestBase):
    """Base class for Streamlit E2E tests."""

    def setup_streamlit_session(self, user: MockUser):
        """Set up Streamlit session state for testing."""
        import streamlit as st

        # Mock session state
        session_state = {
            "authenticated": True,
            "user_id": user.user_id,
            "user_email": user.email,
            "user_name": user.name,
            "current_page": "home",
            "photos_loaded": False,
            "upload_in_progress": False,
        }

        # Patch streamlit session state
        with patch.object(st, "session_state", session_state):
            yield session_state


class APITestClient:
    """Test client for API testing."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get(self, path: str, headers: dict[str, str] | None = None, **kwargs) -> requests.Response:
        """Make GET request."""
        url = f"{self.base_url}{path}"
        return self.session.get(url, headers=headers, **kwargs)

    def post(self, path: str, headers: dict[str, str] | None = None, **kwargs) -> requests.Response:
        """Make POST request."""
        url = f"{self.base_url}{path}"
        return self.session.post(url, headers=headers, **kwargs)

    def upload_file(
        self, path: str, file_data: bytes, filename: str, headers: dict[str, str] | None = None
    ) -> requests.Response:
        """Upload file via POST request."""
        url = f"{self.base_url}{path}"
        files = {"file": (filename, file_data, "image/jpeg")}
        return self.session.post(url, files=files, headers=headers)


class DatabaseTestHelper:
    """Helper for database operations in tests."""

    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir
        self.db_files = {}

    def create_user_database(self, user_id: str) -> str:
        """Create a test database for a user."""
        db_path = os.path.join(self.temp_dir, f"{user_id}.db")
        self.db_files[user_id] = db_path

        # Initialize database with schema
        import duckdb

        conn = duckdb.connect(db_path)
        conn.execute(
            """
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
            )
        """
        )
        conn.close()

        return db_path

    def insert_test_photo(self, user_id: str, photo_data: dict[str, Any]):
        """Insert test photo data."""
        if user_id not in self.db_files:
            self.create_user_database(user_id)

        import duckdb

        conn = duckdb.connect(self.db_files[user_id])
        conn.execute(
            """
            INSERT INTO photos (id, user_id, filename, original_path, thumbnail_path, 
                              file_size, mime_type, created_at, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                photo_data["id"],
                photo_data["user_id"],
                photo_data["filename"],
                photo_data["original_path"],
                photo_data["thumbnail_path"],
                photo_data["file_size"],
                photo_data["mime_type"],
                photo_data["created_at"],
                photo_data["uploaded_at"],
            ),
        )
        conn.close()

    def get_user_photos(self, user_id: str) -> list[dict[str, Any]]:
        """Get all photos for a user."""
        if user_id not in self.db_files:
            return []

        import duckdb

        conn = duckdb.connect(self.db_files[user_id])
        result = conn.execute("SELECT * FROM photos ORDER BY created_at DESC").fetchall()
        conn.close()

        columns = [
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

        return [dict(zip(columns, row, strict=False)) for row in result]

    def cleanup(self):
        """Clean up test databases."""
        for db_path in self.db_files.values():
            if os.path.exists(db_path):
                os.remove(db_path)


class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def create_photo_metadata(user_id: str, filename: str = "test-image.jpg") -> dict[str, Any]:
        """Create test photo metadata."""
        return {
            "filename": filename,
            "original_path": f"original/{user_id}/{filename}",
            "thumbnail_path": f"thumbs/{user_id}/{filename}",
            "file_size": 1024000,
            "width": 1920,
            "height": 1080,
            "format": "JPEG",
            "created_at": time.time(),
        }

    @staticmethod
    def create_test_scenarios() -> dict[str, dict[str, Any]]:
        """Create various test scenarios."""
        return {
            "normal_upload": {
                "description": "Normal photo upload scenario",
                "file_size": 1024000,
                "format": "JPEG",
                "width": 1920,
                "height": 1080,
                "expected_success": True,
            },
            "large_file": {
                "description": "Large file upload scenario",
                "file_size": 50 * 1024 * 1024,  # 50MB
                "format": "JPEG",
                "width": 4000,
                "height": 3000,
                "expected_success": True,
            },
            "heic_format": {
                "description": "HEIC format upload scenario",
                "file_size": 2048000,
                "format": "HEIC",
                "width": 2000,
                "height": 1500,
                "expected_success": True,
            },
            "unsupported_format": {
                "description": "Unsupported format scenario",
                "file_size": 512000,
                "format": "BMP",
                "width": 800,
                "height": 600,
                "expected_success": False,
            },
            "oversized_file": {
                "description": "File too large scenario",
                "file_size": 100 * 1024 * 1024,  # 100MB
                "format": "JPEG",
                "width": 8000,
                "height": 6000,
                "expected_success": False,
            },
        }


# Pytest fixtures for E2E tests
@pytest.fixture
def test_users():
    """Provide test users."""
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
