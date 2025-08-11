"""
Pytest configuration and fixtures for imgstream tests.
"""

import base64
import json
import tempfile
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from src.imgstream.services.auth import UserInfo

# Import E2E test fixtures


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_image_data() -> bytes:
    """Provide sample image data for testing."""
    # Simple 1x1 pixel PNG image data
    return bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,
            0x08,
            0x02,
            0x00,
            0x00,
            0x00,
            0x90,
            0x77,
            0x53,
            0xDE,
            0x00,
            0x00,
            0x00,
            0x0C,
            0x49,
            0x44,
            0x41,
            0x54,
            0x08,
            0xD7,
            0x63,
            0xF8,
            0x00,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )


@pytest.fixture
def mock_user_id() -> str:
    """Provide a mock user ID for testing."""
    return "test-user-123"


@pytest.fixture
def mock_gcs_bucket() -> str:
    """Provide a mock GCS bucket name for testing."""
    return "test-imgstream-bucket"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up test environment variables."""
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("GCS_PHOTOS_BUCKET", "test-photos-bucket")
    monkeypatch.setenv("GCS_DATABASE_BUCKET", "test-database-bucket")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")


class TestDataFactory:
    """Factory class for creating test data objects."""

    @staticmethod
    def create_user_info(
        user_id: str = "test-user-123",
        email: str = "test@example.com",
        name: str | None = "Test User",
        picture: str | None = None,
    ) -> UserInfo:
        """Create a UserInfo object for testing.

        Args:
            user_id: User ID for the test user
            email: Email address for the test user
            name: Display name for the test user
            picture: Profile picture URL for the test user

        Returns:
            UserInfo object with the specified attributes
        """
        return UserInfo(user_id=user_id, email=email, picture=picture)

    @staticmethod
    def create_jwt_payload(
        user_id: str = "test-user-123",
        email: str = "test@example.com",
        name: str | None = "Test User",
        picture: str | None = None,
        iss: str = "https://cloud.google.com/iap",
        aud: str = "/projects/123456789/global/backendServices/test-service",
        iat: int | None = None,
        exp: int | None = None,
    ) -> dict:
        """Create a JWT payload for testing.

        Args:
            user_id: User ID (sub claim)
            email: Email address
            name: Display name
            picture: Profile picture URL
            iss: Issuer claim
            aud: Audience claim
            iat: Issued at timestamp (defaults to current time)
            exp: Expiration timestamp (defaults to current time + 1 hour)

        Returns:
            Dictionary containing JWT payload
        """
        current_time = int(time.time())
        payload = {
            "sub": user_id,
            "email": email,
            "iss": iss,
            "aud": aud,
            "iat": iat or current_time,
            "exp": exp or (current_time + 3600),
        }

        if name is not None:
            payload["name"] = name
        if picture is not None:
            payload["picture"] = picture

        return payload

    @staticmethod
    def create_valid_jwt_token(payload: dict | None = None) -> str:
        """Create a valid JWT token for testing.

        Args:
            payload: JWT payload dictionary. If None, creates a default payload.

        Returns:
            JWT token string
        """
        if payload is None:
            payload = TestDataFactory.create_jwt_payload()

        # Create JWT header
        header = {"alg": "RS256", "typ": "JWT"}

        # Encode header and payload
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

        # Create dummy signature (for testing purposes)
        signature = "test_signature_for_testing_purposes_only"
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip("=")

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    @staticmethod
    def create_invalid_jwt_token(payload: dict | None = None) -> str:
        """Create an invalid JWT token for testing (malformed structure).

        Args:
            payload: JWT payload dictionary. If None, creates a default payload.

        Returns:
            Invalid JWT token string
        """
        if payload is None:
            payload = TestDataFactory.create_jwt_payload()

        # Create JWT with invalid structure (using standard base64 instead of urlsafe)
        header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
        payload_encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        signature = "invalid_signature"

        return f"{header}.{payload_encoded}.{signature}"

    @staticmethod
    def create_iap_headers(
        user_id: str = "test-user-123",
        email: str = "test@example.com",
        name: str | None = "Test User",
        picture: str | None = None,
    ) -> dict[str, str]:
        """Create IAP headers with a valid JWT token for testing.

        Args:
            user_id: User ID for the test user
            email: Email address for the test user
            name: Display name for the test user
            picture: Profile picture URL for the test user

        Returns:
            Dictionary containing IAP headers
        """
        payload = TestDataFactory.create_jwt_payload(user_id=user_id, email=email, name=name, picture=picture)
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)

        return {"X-Goog-IAP-JWT-Assertion": jwt_token}

    @staticmethod
    def create_mock_user(
        user_id: str = "test-user-123", email: str = "test@example.com", name: str = "Test User"
    ) -> "MockUser":
        """Create a MockUser object for testing.

        Args:
            user_id: User ID for the mock user
            email: Email address for the mock user
            name: Display name for the mock user

        Returns:
            MockUser object
        """
        return MockUser(user_id=user_id, email=email, name=name)


class MockUser:
    """Mock user class for testing."""

    def __init__(self, user_id: str, email: str, name: str):
        self.user_id = user_id
        self.email = email
        self.name = name

    def to_dict(self) -> dict[str, str]:
        """Convert mock user to dictionary."""
        return {"user_id": self.user_id, "email": self.email, "name": self.name}

    def get_storage_path_prefix(self) -> str:
        """Get storage path prefix for this user."""
        return f"photos/{self.user_id}/"

    def get_database_path(self) -> str:
        """Get database path for this user."""
        safe_email = self.email.replace("@", "_at_").replace(".", "_dot_")
        return f"dbs/{safe_email}/metadata.db"


@pytest.fixture
def test_data_factory() -> TestDataFactory:
    """Provide TestDataFactory instance for tests."""
    return TestDataFactory()
