"""
Unit tests for TestDataFactory.
"""

import json
import base64
import time

import pytest

from src.imgstream.services.auth import UserInfo
from tests.conftest import TestDataFactory, MockUser


class TestTestDataFactory:
    """Test cases for TestDataFactory class."""

    def test_create_user_info_default(self):
        """Test creating UserInfo with default values."""
        user_info = TestDataFactory.create_user_info()

        assert user_info.user_id == "test-user-123"
        assert user_info.email == "test@example.com"
        assert user_info.picture is None

    def test_create_user_info_custom(self):
        """Test creating UserInfo with custom values."""
        user_info = TestDataFactory.create_user_info(
            user_id="custom-user-456",
            email="custom@example.com",
            name="Custom User",  # Kept for compatibility but not used
            picture="https://example.com/photo.jpg",
        )

        assert user_info.user_id == "custom-user-456"
        assert user_info.email == "custom@example.com"
        assert user_info.picture == "https://example.com/photo.jpg"

    def test_create_jwt_payload_default(self):
        """Test creating JWT payload with default values."""
        payload = TestDataFactory.create_jwt_payload()

        assert payload["sub"] == "test-user-123"
        assert payload["email"] == "test@example.com"
        assert payload["name"] == "Test User"
        assert payload["iss"] == "https://cloud.google.com/iap"
        assert payload["aud"] == "/projects/123456789/global/backendServices/test-service"
        assert "iat" in payload
        assert "exp" in payload
        assert payload["exp"] > payload["iat"]

    def test_create_jwt_payload_custom(self):
        """Test creating JWT payload with custom values."""
        current_time = int(time.time())
        payload = TestDataFactory.create_jwt_payload(
            user_id="custom-user",
            email="custom@example.com",
            name="Custom User",
            picture="https://example.com/photo.jpg",
            iat=current_time,
            exp=current_time + 7200,
        )

        assert payload["sub"] == "custom-user"
        assert payload["email"] == "custom@example.com"
        assert payload["name"] == "Custom User"
        assert payload["picture"] == "https://example.com/photo.jpg"
        assert payload["iat"] == current_time
        assert payload["exp"] == current_time + 7200

    def test_create_valid_jwt_token(self):
        """Test creating valid JWT token."""
        token = TestDataFactory.create_valid_jwt_token()

        # JWT should have 3 parts separated by dots
        parts = token.split(".")
        assert len(parts) == 3

        # Decode and verify payload
        payload_b64 = parts[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        assert payload["sub"] == "test-user-123"
        assert payload["email"] == "test@example.com"

    def test_create_valid_jwt_token_custom_payload(self):
        """Test creating valid JWT token with custom payload."""
        custom_payload = {"sub": "custom-user", "email": "custom@example.com", "name": "Custom User"}

        token = TestDataFactory.create_valid_jwt_token(custom_payload)

        # Decode and verify payload
        parts = token.split(".")
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        assert payload["sub"] == "custom-user"
        assert payload["email"] == "custom@example.com"
        assert payload["name"] == "Custom User"

    def test_create_invalid_jwt_token(self):
        """Test creating invalid JWT token."""
        token = TestDataFactory.create_invalid_jwt_token()

        # JWT should have 3 parts separated by dots
        parts = token.split(".")
        assert len(parts) == 3

        # The token should be invalid due to structure differences
        # (uses standard base64 instead of urlsafe)
        assert token != TestDataFactory.create_valid_jwt_token()

    def test_create_iap_headers(self):
        """Test creating IAP headers."""
        headers = TestDataFactory.create_iap_headers()

        assert "X-Goog-IAP-JWT-Assertion" in headers
        assert isinstance(headers["X-Goog-IAP-JWT-Assertion"], str)

        # Verify the JWT token in headers is valid
        token = headers["X-Goog-IAP-JWT-Assertion"]
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_iap_headers_custom(self):
        """Test creating IAP headers with custom values."""
        headers = TestDataFactory.create_iap_headers(
            user_id="custom-user",
            email="custom@example.com",
            name="Custom User",
            picture="https://example.com/photo.jpg",
        )

        assert "X-Goog-IAP-JWT-Assertion" in headers

        # Decode and verify the payload contains custom values
        token = headers["X-Goog-IAP-JWT-Assertion"]
        parts = token.split(".")
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        assert payload["sub"] == "custom-user"
        assert payload["email"] == "custom@example.com"
        assert payload["name"] == "Custom User"
        assert payload["picture"] == "https://example.com/photo.jpg"

    def test_create_mock_user(self):
        """Test creating MockUser object."""
        user = TestDataFactory.create_mock_user()

        assert user.user_id == "test-user-123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"

    def test_create_mock_user_custom(self):
        """Test creating MockUser object with custom values."""
        user = TestDataFactory.create_mock_user(user_id="custom-user", email="custom@example.com", name="Custom User")

        assert user.user_id == "custom-user"
        assert user.email == "custom@example.com"
        assert user.name == "Custom User"

    def test_mock_user_to_dict(self):
        """Test MockUser to_dict method."""
        user = TestDataFactory.create_mock_user(user_id="test-user", email="test@example.com", name="Test User")

        user_dict = user.to_dict()

        assert user_dict == {"user_id": "test-user", "email": "test@example.com", "name": "Test User"}


class TestTestDataFactoryFixture:
    """Test cases for TestDataFactory fixture."""

    def test_test_data_factory_fixture(self, test_data_factory):
        """Test that the test_data_factory fixture works."""
        assert isinstance(test_data_factory, TestDataFactory)

        # Test that we can use the fixture to create objects
        user_info = test_data_factory.create_user_info()
        assert isinstance(user_info, UserInfo)

        headers = test_data_factory.create_iap_headers()
        assert "X-Goog-IAP-JWT-Assertion" in headers
