"""
Unit tests for authentication service.
"""

import pytest
import json
import base64
from unittest.mock import patch, MagicMock

from src.imgstream.services.auth import (
    CloudIAPAuthService,
    UserInfo,
    get_auth_service
)


class TestUserInfo:
    """Test cases for UserInfo dataclass."""

    def test_user_info_creation(self):
        """Test UserInfo creation with all fields."""
        user_info = UserInfo(
            user_id="123456789",
            email="user@example.com",
            name="Test User",
            picture="https://example.com/photo.jpg"
        )
        
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.name == "Test User"
        assert user_info.picture == "https://example.com/photo.jpg"

    def test_user_info_creation_minimal(self):
        """Test UserInfo creation with required fields only."""
        user_info = UserInfo(
            user_id="123456789",
            email="user@example.com"
        )
        
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.name is None
        assert user_info.picture is None

    def test_get_storage_path_prefix(self):
        """Test storage path prefix generation."""
        user_info = UserInfo(
            user_id="123456789",
            email="user@example.com"
        )
        
        path = user_info.get_storage_path_prefix()
        assert path == "photos/user_at_example_dot_com/"

    def test_get_storage_path_prefix_special_chars(self):
        """Test storage path prefix with special characters in email."""
        user_info = UserInfo(
            user_id="123456789",
            email="test.user+tag@sub.example.com"
        )
        
        path = user_info.get_storage_path_prefix()
        assert path == "photos/test_dot_user+tag_at_sub_dot_example_dot_com/"

    def test_get_database_path(self):
        """Test database path generation."""
        user_info = UserInfo(
            user_id="123456789",
            email="user@example.com"
        )
        
        path = user_info.get_database_path()
        assert path == "dbs/user_at_example_dot_com/metadata.db"

    def test_get_database_path_special_chars(self):
        """Test database path with special characters in email."""
        user_info = UserInfo(
            user_id="123456789",
            email="test.user+tag@sub.example.com"
        )
        
        path = user_info.get_database_path()
        assert path == "dbs/test_dot_user+tag_at_sub_dot_example_dot_com/metadata.db"


class TestCloudIAPAuthService:
    """Test cases for CloudIAPAuthService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = CloudIAPAuthService()

    def create_test_jwt(self, payload: dict) -> str:
        """Create a test JWT token with the given payload."""
        # Create a simple JWT with dummy header and signature
        header = {"alg": "RS256", "typ": "JWT"}
        signature = "dummy_signature"
        
        # Encode header and payload
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip('=')
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def test_parse_iap_header_success(self):
        """Test successful IAP header parsing."""
        payload = {
            "sub": "123456789",
            "email": "user@example.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg"
        }
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}
        
        user_info = self.auth_service.parse_iap_header(headers)
        
        assert user_info is not None
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.name == "Test User"
        assert user_info.picture == "https://example.com/photo.jpg"

    def test_parse_iap_header_minimal_payload(self):
        """Test IAP header parsing with minimal payload."""
        payload = {
            "sub": "123456789",
            "email": "user@example.com"
        }
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}
        
        user_info = self.auth_service.parse_iap_header(headers)
        
        assert user_info is not None
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.name is None
        assert user_info.picture is None

    def test_parse_iap_header_missing_header(self):
        """Test IAP header parsing with missing header."""
        headers = {}
        
        user_info = self.auth_service.parse_iap_header(headers)
        
        assert user_info is None

    def test_parse_iap_header_invalid_jwt(self):
        """Test IAP header parsing with invalid JWT."""
        headers = {"X-Goog-IAP-JWT-Assertion": "invalid.jwt.token"}
        
        user_info = self.auth_service.parse_iap_header(headers)
        
        assert user_info is None

    def test_parse_iap_header_missing_email(self):
        """Test IAP header parsing with missing email in payload."""
        payload = {
            "sub": "123456789"
            # Missing email
        }
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}
        
        user_info = self.auth_service.parse_iap_header(headers)
        
        assert user_info is None

    def test_parse_iap_header_missing_sub(self):
        """Test IAP header parsing with missing sub in payload."""
        payload = {
            "email": "user@example.com"
            # Missing sub
        }
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}
        
        user_info = self.auth_service.parse_iap_header(headers)
        
        assert user_info is None

    def test_decode_jwt_payload_invalid_format(self):
        """Test JWT decoding with invalid format."""
        with pytest.raises(ValueError, match="Invalid JWT token format"):
            self.auth_service._decode_jwt_payload("invalid_format")

    def test_decode_jwt_payload_invalid_base64(self):
        """Test JWT decoding with invalid base64."""
        with pytest.raises(ValueError, match="Failed to decode JWT payload"):
            self.auth_service._decode_jwt_payload("header.invalid_base64.signature")

    def test_extract_user_info_missing_email(self):
        """Test user info extraction with missing email."""
        payload = {"sub": "123456789"}
        
        with pytest.raises(ValueError, match="Email not found in JWT payload"):
            self.auth_service._extract_user_info(payload)

    def test_extract_user_info_missing_sub(self):
        """Test user info extraction with missing sub."""
        payload = {"email": "user@example.com"}
        
        with pytest.raises(ValueError, match="Subject \\(user ID\\) not found in JWT payload"):
            self.auth_service._extract_user_info(payload)

    def test_authenticate_request_success(self):
        """Test successful request authentication."""
        payload = {
            "sub": "123456789",
            "email": "user@example.com",
            "name": "Test User"
        }
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}
        
        result = self.auth_service.authenticate_request(headers)
        
        assert result is True
        assert self.auth_service.is_authenticated() is True
        assert self.auth_service.get_current_user() is not None
        assert self.auth_service.get_user_id() == "123456789"
        assert self.auth_service.get_user_email() == "user@example.com"

    def test_authenticate_request_failure(self):
        """Test failed request authentication."""
        headers = {}
        
        result = self.auth_service.authenticate_request(headers)
        
        assert result is False
        assert self.auth_service.is_authenticated() is False
        assert self.auth_service.get_current_user() is None
        assert self.auth_service.get_user_id() is None
        assert self.auth_service.get_user_email() is None

    def test_get_user_storage_path(self):
        """Test getting user storage path."""
        payload = {
            "sub": "123456789",
            "email": "user@example.com"
        }
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}
        
        self.auth_service.authenticate_request(headers)
        
        path = self.auth_service.get_user_storage_path()
        assert path == "photos/user_at_example_dot_com/"

    def test_get_user_storage_path_not_authenticated(self):
        """Test getting user storage path when not authenticated."""
        path = self.auth_service.get_user_storage_path()
        assert path is None

    def test_get_user_database_path(self):
        """Test getting user database path."""
        payload = {
            "sub": "123456789",
            "email": "user@example.com"
        }
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}
        
        self.auth_service.authenticate_request(headers)
        
        path = self.auth_service.get_user_database_path()
        assert path == "dbs/user_at_example_dot_com/metadata.db"

    def test_get_user_database_path_not_authenticated(self):
        """Test getting user database path when not authenticated."""
        path = self.auth_service.get_user_database_path()
        assert path is None

    def test_clear_authentication(self):
        """Test clearing authentication state."""
        payload = {
            "sub": "123456789",
            "email": "user@example.com"
        }
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}
        
        # Authenticate first
        self.auth_service.authenticate_request(headers)
        assert self.auth_service.is_authenticated() is True
        
        # Clear authentication
        self.auth_service.clear_authentication()
        assert self.auth_service.is_authenticated() is False
        assert self.auth_service.get_current_user() is None

    def test_iap_header_name_constant(self):
        """Test that IAP header name constant is correct."""
        assert CloudIAPAuthService.IAP_HEADER_NAME == "X-Goog-IAP-JWT-Assertion"


class TestAuthServiceGlobal:
    """Test cases for global auth service functions."""

    def test_get_auth_service(self):
        """Test getting global auth service instance."""
        service = get_auth_service()
        
        assert isinstance(service, CloudIAPAuthService)
        
        # Should return the same instance
        service2 = get_auth_service()
        assert service is service2
