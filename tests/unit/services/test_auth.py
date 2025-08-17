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
from tests.conftest import TestDataFactory


class TestUserInfo:
    """Test cases for UserInfo dataclass."""

    def test_user_info_creation(self):
        """Test UserInfo creation with all fields."""
        user_info = UserInfo(user_id="123456789", email="user@example.com", picture="https://example.com/photo.jpg")

        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.picture == "https://example.com/photo.jpg"

    def test_user_info_creation_minimal(self):
        """Test UserInfo creation with required fields only."""
        user_info = UserInfo(user_id="123456789", email="user@example.com")

        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.picture is None

class TestCloudIAPAuthService:
    """Test cases for CloudIAPAuthService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = CloudIAPAuthService()

    def test_init_development_mode(self):
        """Test initialization in development mode."""
        with patch.dict("os.environ", {"ENVIRONMENT": "development"}):
            service = CloudIAPAuthService()
            assert service._development_mode is True

    def test_init_production_mode(self):
        """Test initialization in production mode."""
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            service = CloudIAPAuthService()
            assert service._development_mode is False

    def test_get_development_user_default(self):
        """Test getting development user with default values."""
        with patch.dict("os.environ", {}, clear=True):
            user = self.auth_service._get_development_user()
            assert user.email == "dev@example.com"
            assert user.user_id == "dev-user-123"
            assert user.picture is None

    def test_get_development_user_custom(self):
        """Test getting development user with custom environment variables."""
        with patch.dict(
            "os.environ",
            {"DEV_USER_EMAIL": "custom@test.com", "DEV_USER_ID": "custom-123"},
        ):
            user = self.auth_service._get_development_user()
            assert user.email == "custom@test.com"
            assert user.user_id == "custom-123"

    def test_parse_iap_header_development_mode(self):
        """Test parsing IAP header in development mode."""
        with patch.dict("os.environ", {"ENVIRONMENT": "development"}):
            service = CloudIAPAuthService()
            headers = {"X-Goog-Iap-Jwt-Assertion": "some-token"}

            user_info = service.parse_iap_header(headers)

            assert user_info is not None
            assert user_info.email == "dev@example.com"
            assert user_info.user_id == "dev-user-123"

    def test_parse_iap_header_missing_token_production(self):
        """Test parsing IAP header with missing token in production mode."""
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            service = CloudIAPAuthService()
            headers = {}

            user_info = service.parse_iap_header(headers)

            assert user_info is None

    def test_parse_iap_header_success(self):
        """Test successful IAP header parsing."""
        payload = {
            "sub": "123456789",
            "email": "user@example.com",
            "picture": "https://example.com/photo.jpg",
        }
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is not None
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.picture == "https://example.com/photo.jpg"

    def test_parse_iap_header_minimal_payload(self):
        """Test IAP header parsing with minimal payload."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is not None
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.picture is None

    def test_parse_iap_header_missing_header(self):
        """Test IAP header parsing with missing header."""
        headers = {}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is None

    def test_parse_iap_header_invalid_jwt(self):
        """Test IAP header parsing with invalid JWT."""
        headers = {"X-Goog-Iap-Jwt-Assertion": "invalid.jwt.token"}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is None

    def test_parse_iap_header_missing_email(self):
        """Test IAP header parsing with missing email in payload."""
        payload = {
            "sub": "123456789"
            # Missing email
        }
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is None

    def test_parse_iap_header_missing_sub(self):
        """Test IAP header parsing with missing sub in payload."""
        payload = {
            "email": "user@example.com"
            # Missing sub
        }
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

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
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        result = self.auth_service.authenticate_request(headers)

        assert result is not None
        assert self.auth_service.is_authenticated() is True
        assert self.auth_service.get_current_user() is not None
        assert self.auth_service.get_user_id() == "123456789"
        assert self.auth_service.get_user_email() == "user@example.com"

    def test_authenticate_request_failure(self):
        """Test failed request authentication."""
        headers = {}

        result = self.auth_service.authenticate_request(headers)

        assert result is None
        assert self.auth_service.is_authenticated() is False
        assert self.auth_service.get_current_user() is None
        assert self.auth_service.get_user_id() is None
        assert self.auth_service.get_user_email() is None

    def test_clear_authentication(self):
        """Test clearing authentication state."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        # Authenticate first
        self.auth_service.authenticate_request(headers)
        assert self.auth_service.is_authenticated() is True

        # Clear authentication
        self.auth_service.clear_authentication()
        assert self.auth_service.is_authenticated() is False
        assert self.auth_service.get_current_user() is None

    def test_iap_header_name_constant(self):
        """Test that IAP header name constant is correct."""
        assert CloudIAPAuthService.IAP_HEADER_NAME == "X-Goog-Iap-Jwt-Assertion"


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

    def test_ensure_authenticated_success(self):
        """Test ensure_authenticated with authenticated user."""
        payload = {"sub": "123456789", "email": "user@example.com", "name": "Test User"}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        self.auth_service.authenticate_request(headers)

        user_info = self.auth_service.ensure_authenticated()
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"

    def test_ensure_authenticated_failure(self):
        """Test ensure_authenticated with unauthenticated user."""
        with pytest.raises(AuthenticationError, match="User is not authenticated"):
            self.auth_service.ensure_authenticated()

    def test_require_authentication_success(self):
        """Test require authentication with authenticated user."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

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

    def test_jwt_malformed_parts(self):
        """Test JWT with wrong number of parts."""
        # JWT with only 2 parts instead of 3
        malformed_jwt = "header.payload"
        headers = {"X-Goog-Iap-Jwt-Assertion": malformed_jwt}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_jwt_empty_payload(self):
        """Test JWT with empty payload."""
        payload = {}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_jwt_null_values(self):
        """Test JWT with null values in payload."""
        payload = {"sub": None, "email": None}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_jwt_empty_string_values(self):
        """Test JWT with empty string values."""
        payload = {"sub": "", "email": ""}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

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
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

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
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)
        assert user_info is None

    def test_logging_on_missing_header(self):
        """Test that security event is logged when IAP header is missing."""
        headers = {}

        with patch("src.imgstream.services.auth.log_security_event") as mock_security_log:
            self.auth_service.parse_iap_header(headers)

            mock_security_log.assert_called_once_with("missing_iap_header", context={"headers_present": []})

    def test_logging_on_jwt_parse_error(self):
        """Test that security event is logged when JWT parsing fails."""
        headers = {"X-Goog-Iap-Jwt-Assertion": "invalid.jwt.token"}

        with patch("src.imgstream.services.auth.log_security_event") as mock_security_log:
            self.auth_service.parse_iap_header(headers)

            # Verify security event was logged
            mock_security_log.assert_called_with(
                "authentication_failure",
                context={
                    "error": (
                        "Failed to decode JWT payload: 'utf-8' codec can't decode byte 0x8f in position 0: "
                        "invalid start byte"
                    )
                },
            )

    def test_logging_on_successful_auth(self):
        """Test that user action is logged on successful authentication."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        with patch("src.imgstream.services.auth.log_user_action") as mock_user_log:
            self.auth_service.parse_iap_header(headers)

            mock_user_log.assert_called_with("123456789", "authentication_success", email="user@example.com")

    def test_logging_on_clear_authentication(self):
        """Test that user action is logged when authentication is cleared."""
        with patch("src.imgstream.services.auth.log_user_action") as mock_user_log:
            self.auth_service.clear_authentication()

            mock_user_log.assert_called_with("unknown", "authentication_cleared")


class TestEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = CloudIAPAuthService()

    def test_very_long_email(self):
        """Test with very long email address."""
        long_email = "a" * 100 + "@" + "b" * 100 + ".com"
        payload = {"sub": "123456789", "email": long_email}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is not None
        assert user_info.email == long_email

    def test_email_with_multiple_special_chars(self):
        """Test email with multiple special characters."""
        special_email = "test.user+tag@sub.domain.example.com"
        payload = {"sub": "123456789", "email": special_email}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is not None
        assert user_info.email == special_email

    def test_concurrent_authentication_requests(self):
        """Test concurrent authentication requests don't interfere."""
        payload1 = {"sub": "user1", "email": "user1@example.com"}
        payload2 = {"sub": "user2", "email": "user2@example.com"}

        jwt_token1 = TestDataFactory.create_valid_jwt_token(payload1)
        jwt_token2 = TestDataFactory.create_valid_jwt_token(payload2)

        headers1 = {"X-Goog-Iap-Jwt-Assertion": jwt_token1}
        headers2 = {"X-Goog-Iap-Jwt-Assertion": jwt_token2}

        # Authenticate with first user
        result1 = self.auth_service.authenticate_request(headers1)
        assert result1 is not None
        assert self.auth_service.get_user_email() == "user1@example.com"

        # Authenticate with second user (should replace first)
        result2 = self.auth_service.authenticate_request(headers2)
        assert result2 is not None
        assert self.auth_service.get_user_email() == "user2@example.com"

    def test_multiple_authentication_cycles(self):
        """Test multiple authentication and clearing cycles."""
        payload = {"sub": "123456789", "email": "user@example.com"}
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        # Perform multiple auth cycles
        for _ in range(5):
            # Authenticate
            result = self.auth_service.authenticate_request(headers)
            assert result is not None
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
        jwt_token = TestDataFactory.create_valid_jwt_token(payload)
        headers = {"X-Goog-Iap-Jwt-Assertion": jwt_token}

        user_info = self.auth_service.parse_iap_header(headers)

        assert user_info is not None
        assert user_info.user_id == "123456789"
        assert user_info.email == "user@example.com"
        assert user_info.picture == "https://example.com/photo.jpg"


class TestInputSanitization:
    """Test cases for input sanitization functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = CloudIAPAuthService()

    def test_sanitize_user_input_sql_injection(self):
        """Test that SQL injection patterns are removed."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "admin'/**/OR/**/1=1--",
            "user123'; UNION SELECT * FROM secrets--",
            "test@example.com'; DELETE FROM photos; --",
        ]

        for malicious_input in malicious_inputs:
            sanitized = self.auth_service._sanitize_user_input(malicious_input)

            # Check that dangerous SQL patterns are removed
            assert "DROP TABLE" not in sanitized
            assert "DELETE FROM" not in sanitized
            assert "UNION SELECT" not in sanitized
            assert "--" not in sanitized
            assert "/*" not in sanitized
            assert "*/" not in sanitized

    def test_sanitize_user_input_xss_attacks(self):
        """Test that XSS attack patterns are removed."""
        malicious_inputs = [
            "<script>alert('xss')</script>@example.com",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')@example.com",
            "user123<svg onload=alert('xss')>",
        ]

        for malicious_input in malicious_inputs:
            sanitized = self.auth_service._sanitize_user_input(malicious_input)

            # Check that dangerous XSS patterns are removed
            assert "<script>" not in sanitized
            assert "<img" not in sanitized
            assert "javascript:" not in sanitized
            assert "<svg" not in sanitized
            assert "onerror" not in sanitized
            assert "onload" not in sanitized

    def test_sanitize_user_input_html_escaping(self):
        """Test that HTML characters are properly escaped."""
        test_input = 'user@example.com<>&"'
        sanitized = self.auth_service._sanitize_user_input(test_input)

        # Check that HTML characters are escaped
        assert "&lt;" in sanitized  # < becomes &lt;
        assert "&gt;" in sanitized  # > becomes &gt;
        assert "&amp;" in sanitized  # & becomes &amp;
        assert "&quot;" in sanitized  # " becomes &quot;

    def test_sanitize_user_input_none_and_empty(self):
        """Test that None and empty values are handled correctly."""
        assert self.auth_service._sanitize_user_input(None) is None
        assert self.auth_service._sanitize_user_input("") == ""
        assert self.auth_service._sanitize_user_input("   ") == "   "

    def test_sanitize_user_input_normal_values(self):
        """Test that normal values are preserved."""
        normal_inputs = [
            "user@example.com",
            "John Doe",
            "https://example.com/photo.jpg",
            "user123",
        ]

        for normal_input in normal_inputs:
            sanitized = self.auth_service._sanitize_user_input(normal_input)
            # Normal inputs should be preserved (though HTML-escaped)
            assert len(sanitized) > 0
            assert "user" in sanitized or "John" in sanitized or "example" in sanitized

    def test_extract_user_info_with_malicious_payload(self):
        """Test that _extract_user_info properly sanitizes malicious payloads."""
        malicious_payload = {
            "email": "<script>alert('xss')</script>@example.com",
            "sub": "'; DROP TABLE users; --",
            "name": "<img src=x onerror=alert('xss')>",
            "picture": "javascript:alert('xss')",
        }

        user_info = self.auth_service._extract_user_info(malicious_payload)

        # Check that all fields are sanitized
        assert "<script>" not in user_info.email
        assert "DROP TABLE" not in user_info.user_id
        assert "--" not in user_info.user_id
        assert "javascript:" not in user_info.picture
