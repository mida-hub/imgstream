"""
Unit tests for authentication service.
"""

import base64
import json
from unittest.mock import patch

import pytest

from src.imgstream.services.auth import (
    AccessDeniedError,
    AuthenticationError,
    CloudIAPAuthService,
    UserInfo,
    get_auth_service,
)


class TestUserInfo:
    """Test cases for UserInfo dataclass."""

    def test_user_info_creation(self):
        """Test UserInfo creation with all fields."""
        user_info = UserInfo(
            user_id="123456789", email="user@example.com", name="Test User", picture="https://example.com/photo.jpg"
        )

        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.name == "Test User"
        assert user_info.picture == "https://example.com/photo.jpg"

    def test_user_info_creation_minimal(self):
        """Test UserInfo creation with required fields only."""
        user_info = UserInfo(user_id="123456789", email="user@example.com")

        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.name is None
        assert user_info.picture is None

    def test_get_storage_path_prefix(self):
        """Test storage path prefix generation."""
        user_info = UserInfo(user_id="123456789", email="user@example.com")

        path = user_info.get_storage_path_prefix()
        assert path == "photos/user_at_example_dot_com/"

    def test_get_storage_path_prefix_special_chars(self):
        """Test storage path prefix with special characters in email."""
        user_info = UserInfo(user_id="123456789", email="test.user+tag@sub.example.com")

        path = user_info.get_storage_path_prefix()
        assert path == "photos/test_dot_user+tag_at_sub_dot_example_dot_com/"

    def test_get_database_path(self):
        """Test database path generation."""
        user_info = UserInfo(user_id="123456789", email="user@example.com")

        path = user_info.get_database_path()
        assert path == "dbs/user_at_example_dot_com/metadata.db"

    def test_get_database_path_special_chars(self):
        """Test database path with special characters in email."""
        user_info = UserInfo(user_id="123456789", email="test.user+tag@sub.example.com")

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
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip("=")

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def test_parse_iap_header_success(self):
        """Test successful IAP header parsing."""
        payload = {
            "sub": "123456789",
            "email": "user@example.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
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
        payload = {"sub": "123456789", "email": "user@example.com"}
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
        payload = {"sub": "123456789", "email": "user@example.com", "name": "Test User"}
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
        payload = {"sub": "123456789", "email": "user@example.com"}
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
        payload = {"sub": "123456789", "email": "user@example.com"}
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
        payload = {"sub": "123456789", "email": "user@example.com"}
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


class TestAccessControl:
    """Test cases for access control functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = CloudIAPAuthService()

    def create_test_jwt(self, payload: dict) -> str:
        """Create a test JWT token with the given payload."""
        # Create a simple JWT with dummy header and signature
        header = {"alg": "RS256", "typ": "JWT"}
        signature = "dummy_signature"

        # Encode header and payload
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip("=")

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def test_ensure_authenticated_success(self):
        """Test ensure_authenticated with authenticated user."""
        payload = {"sub": "123456789", "email": "user@example.com", "name": "Test User"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        user_info = self.auth_service.ensure_authenticated()
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"

    def test_ensure_authenticated_failure(self):
        """Test ensure_authenticated with unauthenticated user."""
        with pytest.raises(AuthenticationError, match="User is not authenticated"):
            self.auth_service.ensure_authenticated()

    def test_check_resource_access_storage_success(self):
        """Test resource access check for user's storage path."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        # Test access to user's storage path
        user_path = "photos/user_at_example_dot_com/original/photo.jpg"
        assert self.auth_service.check_resource_access(user_path) is True

    def test_check_resource_access_database_success(self):
        """Test resource access check for user's database path."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        # Test access to user's database path
        db_path = "dbs/user_at_example_dot_com/metadata.db"
        assert self.auth_service.check_resource_access(db_path) is True

    def test_check_resource_access_denied(self):
        """Test resource access check for other user's resources."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        # Test access to another user's path
        other_user_path = "photos/other_at_example_dot_com/original/photo.jpg"
        assert self.auth_service.check_resource_access(other_user_path) is False

    def test_check_resource_access_unauthenticated(self):
        """Test resource access check with unauthenticated user."""
        user_path = "photos/user_at_example_dot_com/original/photo.jpg"
        assert self.auth_service.check_resource_access(user_path) is False

    def test_get_user_resource_paths_success(self):
        """Test getting user resource paths."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        paths = self.auth_service.get_user_resource_paths()

        expected_paths = {
            "storage_prefix": "photos/user_at_example_dot_com/",
            "database_path": "dbs/user_at_example_dot_com/metadata.db",
            "original_photos": "photos/user_at_example_dot_com/original/",
            "thumbnails": "photos/user_at_example_dot_com/thumbs/",
            "database_dir": "dbs/user_at_example_dot_com/",
        }

        assert paths == expected_paths

    def test_get_user_resource_paths_unauthenticated(self):
        """Test getting user resource paths with unauthenticated user."""
        with pytest.raises(AuthenticationError, match="User is not authenticated"):
            self.auth_service.get_user_resource_paths()

    def test_validate_user_ownership_success(self):
        """Test validating user ownership of resource."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        # Should not raise exception for user's resource
        user_path = "photos/user_at_example_dot_com/original/photo.jpg"
        self.auth_service.validate_user_ownership(user_path)

    def test_validate_user_ownership_access_denied(self):
        """Test validating user ownership with access denied."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        # Should raise exception for other user's resource
        other_user_path = "photos/other_at_example_dot_com/original/photo.jpg"
        with pytest.raises(AccessDeniedError, match="Access denied to resource"):
            self.auth_service.validate_user_ownership(other_user_path)

    def test_validate_user_ownership_unauthenticated(self):
        """Test validating user ownership with unauthenticated user."""
        user_path = "photos/user_at_example_dot_com/original/photo.jpg"
        with pytest.raises(AuthenticationError, match="User is not authenticated"):
            self.auth_service.validate_user_ownership(user_path)

    def test_require_authentication_success(self):
        """Test require authentication with authenticated user."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        # Should not raise exception
        self.auth_service.require_authentication()

    def test_require_authentication_failure(self):
        """Test require authentication with unauthenticated user."""
        with pytest.raises(AuthenticationError, match="User is not authenticated"):
            self.auth_service.require_authentication()


class TestErrorHandling:
    """Test cases for comprehensive error handling scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = CloudIAPAuthService()

    def create_test_jwt(self, payload: dict) -> str:
        """Create a test JWT token with the given payload."""
        header = {"alg": "RS256", "typ": "JWT"}
        signature = "dummy_signature"

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip("=")

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def test_jwt_malformed_parts(self):
        """Test JWT with wrong number of parts."""
        # JWT with only 2 parts instead of 3
        malformed_jwt = "header.payload"
        headers = {"X-Goog-IAP-JWT-Assertion": malformed_jwt}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_jwt_empty_payload(self):
        """Test JWT with empty payload."""
        payload = {}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_jwt_null_values(self):
        """Test JWT with null values in payload."""
        payload = {"sub": None, "email": None}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_jwt_empty_string_values(self):
        """Test JWT with empty string values."""
        payload = {"sub": "", "email": ""}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_jwt_invalid_json_payload(self):
        """Test JWT with invalid JSON in payload."""
        # Create a JWT with invalid JSON payload
        header = {"alg": "RS256", "typ": "JWT"}
        invalid_json = "invalid json content"
        signature = "dummy_signature"

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(invalid_json.encode()).decode().rstrip("=")
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip("=")

        jwt_token = f"{header_b64}.{payload_b64}.{signature_b64}"
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_jwt_unicode_decode_error(self):
        """Test JWT with invalid UTF-8 in payload."""
        # Create a JWT with invalid UTF-8 bytes
        header = {"alg": "RS256", "typ": "JWT"}
        signature = "dummy_signature"

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        # Invalid UTF-8 bytes
        invalid_bytes = b"\xff\xfe\xfd"
        payload_b64 = base64.urlsafe_b64encode(invalid_bytes).decode().rstrip("=")
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip("=")

        jwt_token = f"{header_b64}.{payload_b64}.{signature_b64}"
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_logging_on_missing_header(self):
        """Test that security event is logged when IAP header is missing."""
        headers = {}

        with patch("src.imgstream.services.auth.log_security_event") as mock_security_log:
            self.auth_service.parse_iap_header(headers)
            
            mock_security_log.assert_called_once_with(
                "missing_iap_header", 
                context={"headers_present": []}
            )

    def test_logging_on_jwt_parse_error(self):
        """Test that security event is logged when JWT parsing fails."""
        headers = {"X-Goog-IAP-JWT-Assertion": "invalid.jwt.token"}

        with patch("src.imgstream.services.auth.log_security_event") as mock_security_log:
            self.auth_service.parse_iap_header(headers)
            
            # Verify security event was logged
            mock_security_log.assert_called_with(
                "authentication_failure",
                context={"error": "Failed to decode JWT payload: 'utf-8' codec can't decode byte 0x8f in position 0: invalid start byte"}
            )

    def test_logging_on_successful_auth(self):
        """Test that user action is logged on successful authentication."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        with patch("src.imgstream.services.auth.log_user_action") as mock_user_log:
            self.auth_service.parse_iap_header(headers)
            
            mock_user_log.assert_called_with(
                "123456789",
                "authentication_success",
                email="user@example.com"
            )

    def test_logging_on_access_denied(self):
        """Test that security event is logged on access denied."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        # Try to access another user's resource
        other_user_path = "photos/other_at_example_dot_com/original/photo.jpg"
        
        with patch("src.imgstream.services.auth.log_security_event") as mock_security_log:
            self.auth_service.check_resource_access(other_user_path)
            
            mock_security_log.assert_called_with(
                "access_denied",
                user_id="123456789",
                context={
                    "user_email": "user@example.com",
                    "resource_path": other_user_path
                }
            )

    def test_logging_on_clear_authentication(self):
        """Test that user action is logged when authentication is cleared."""
        with patch("src.imgstream.services.auth.log_user_action") as mock_user_log:
            self.auth_service.clear_authentication()
            
            mock_user_log.assert_called_with(
                "unknown",
                "authentication_cleared"
            )


class TestEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = CloudIAPAuthService()

    def create_test_jwt(self, payload: dict) -> str:
        """Create a test JWT token with the given payload."""
        header = {"alg": "RS256", "typ": "JWT"}
        signature = "dummy_signature"

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip("=")

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def test_very_long_email(self):
        """Test with very long email address."""
        long_email = "a" * 100 + "@" + "b" * 100 + ".com"
        payload = {"sub": "123456789", "email": long_email}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is not None
        assert user_info.email == long_email
        # Test that path generation works with long email
        storage_path = user_info.get_storage_path_prefix()
        assert storage_path.startswith("photos/")
        assert storage_path.endswith("/")

    def test_email_with_multiple_special_chars(self):
        """Test email with multiple special characters."""
        special_email = "test.user+tag@sub.domain.example.com"
        payload = {"sub": "123456789", "email": special_email}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is not None
        assert user_info.email == special_email

        # Test path generation
        storage_path = user_info.get_storage_path_prefix()
        expected_path = "photos/test_dot_user+tag_at_sub_dot_domain_dot_example_dot_com/"
        assert storage_path == expected_path

    def test_concurrent_authentication_requests(self):
        """Test concurrent authentication requests don't interfere."""
        payload1 = {"sub": "user1", "email": "user1@example.com"}
        payload2 = {"sub": "user2", "email": "user2@example.com"}

        jwt_token1 = self.create_test_jwt(payload1)
        jwt_token2 = self.create_test_jwt(payload2)

        headers1 = {"X-Goog-IAP-JWT-Assertion": jwt_token1}
        headers2 = {"X-Goog-IAP-JWT-Assertion": jwt_token2}

        # Authenticate with first user
        result1 = self.auth_service.authenticate_request(headers1)
        assert result1 is True
        assert self.auth_service.get_user_email() == "user1@example.com"

        # Authenticate with second user (should replace first)
        result2 = self.auth_service.authenticate_request(headers2)
        assert result2 is True
        assert self.auth_service.get_user_email() == "user2@example.com"

    def test_resource_path_edge_cases(self):
        """Test resource access with edge case paths."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        # Test various path formats
        test_cases = [
            ("photos/user_at_example_dot_com/", True),  # Exact prefix match
            ("photos/user_at_example_dot_com/original/", True),  # Subdirectory
            ("photos/user_at_example_dot_com", True),  # Without trailing slash
            ("photos/user_at_example_dot_com_malicious/", False),  # Similar but different
            ("photos/other_user_at_example_dot_com/", False),  # Different user
            ("dbs/user_at_example_dot_com/", True),  # Database path
            ("dbs/user_at_example_dot_com/metadata.db", True),  # Exact DB file
            ("", False),  # Empty path
            ("/", False),  # Root path
            ("photos/", False),  # Just photos directory
        ]

        for path, expected in test_cases:
            result = self.auth_service.check_resource_access(path)
            assert result == expected, f"Path '{path}' should return {expected}, got {result}"

    def test_multiple_authentication_cycles(self):
        """Test multiple authentication and clearing cycles."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        # Perform multiple auth cycles
        for _ in range(5):
            # Authenticate
            result = self.auth_service.authenticate_request(headers)
            assert result is True
            assert self.auth_service.is_authenticated() is True

            # Clear
            self.auth_service.clear_authentication()
            assert self.auth_service.is_authenticated() is False

    def test_jwt_with_extra_fields(self):
        """Test JWT with extra fields in payload."""
        payload = {
            "sub": "123456789",
            "email": "user@example.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
            "iss": "https://cloud.google.com/iap",
            "aud": "test-audience",
            "exp": 1234567890,
            "iat": 1234567800,
            "custom_field": "custom_value",
            "roles": ["admin", "user"],
            "permissions": {"read": True, "write": False},
        }
        jwt_token = self.create_test_jwt(payload)
        headers = {"X-Goog-IAP-JWT-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is not None
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.name == "Test User"
        assert user_info.picture == "https://example.com/photo.jpg"
