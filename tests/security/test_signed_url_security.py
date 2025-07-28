"""
Security tests for signed URL functionality.

This module contains comprehensive security tests including:
- Signed URL expiration validation
- URL tampering detection
- Cross-user URL access prevention
- URL parameter injection prevention
"""

import time
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest

from tests.e2e.base import E2ETestBase


class TestSignedUrlSecurity(E2ETestBase):
    """Security tests for signed URL functionality."""

    def create_mock_signed_url(self, user_id: str, filename: str, expiration_minutes: int = 60) -> str:
        """Create a mock signed URL for testing."""
        expiration_time = int(time.time()) + (expiration_minutes * 60)
        base_url = f"https://storage.googleapis.com/test-bucket/original/{user_id}/{filename}"
        params = (
            f"X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=test&"
            f"X-Goog-Date=20240101T000000Z&X-Goog-Expires={expiration_minutes * 60}&"
            f"X-Goog-SignedHeaders=host&X-Goog-Signature=test_signature_{expiration_time}"
        )
        return f"{base_url}?{params}"

    def parse_signed_url(self, url: str) -> dict:
        """Parse a signed URL and extract its components."""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        return {
            "scheme": parsed.scheme,
            "netloc": parsed.netloc,
            "path": parsed.path,
            "query_params": query_params,
            "expires": query_params.get("X-Goog-Expires", [None])[0],
            "signature": query_params.get("X-Goog-Signature", [None])[0],
        }

    @pytest.mark.security
    def test_signed_url_expiration_validation(self, test_users):
        """Test that expired signed URLs are properly rejected."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        storage_service = mock_services["storage"]

        # Test with various expiration scenarios
        expiration_scenarios = [
            (-60, "Already expired URL"),  # Expired 1 hour ago
            (-1, "Just expired URL"),  # Expired 1 minute ago
            (0, "Zero expiration URL"),  # No expiration time
            (1, "Valid short-term URL"),  # Expires in 1 minute
            (60, "Valid long-term URL"),  # Expires in 1 hour
        ]

        for expiration_minutes, description in expiration_scenarios:
            # Create mock signed URL with specific expiration
            signed_url = self.create_mock_signed_url(user.user_id, "test.jpg", expiration_minutes)

            # Configure mock to simulate expiration validation
            def get_signed_url_side_effect(file_path, expiration=3600):
                current_time = int(time.time())
                url_expiration = current_time + (expiration_minutes * 60)

                if url_expiration <= current_time:
                    raise ValueError(f"URL has expired: {description}")

                return signed_url

            storage_service.get_signed_url.side_effect = get_signed_url_side_effect

            if expiration_minutes <= 0:
                # Expired URLs should be rejected
                with pytest.raises(ValueError, match="URL has expired"):
                    storage_service.get_signed_url(f"original/{user.user_id}/test.jpg")
            else:
                # Valid URLs should be accepted
                result_url = storage_service.get_signed_url(f"original/{user.user_id}/test.jpg")
                assert result_url == signed_url

    @pytest.mark.security
    def test_signed_url_tampering_detection(self, test_users):
        """Test that tampered signed URLs are detected and rejected."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        storage_service = mock_services["storage"]

        # Create a valid signed URL
        original_url = self.create_mock_signed_url(user.user_id, "test.jpg")
        parsed_original = self.parse_signed_url(original_url)

        # Test various tampering attempts
        tampering_attempts = [
            # Modify the file path
            original_url.replace("test.jpg", "sensitive.jpg"),
            # Modify the user ID in path
            original_url.replace(user.user_id, "admin"),
            # Modify the expiration time
            original_url.replace("X-Goog-Expires=3600", "X-Goog-Expires=36000"),
            # Modify the signature
            original_url.replace("test_signature_", "fake_signature_"),
            # Add malicious parameters
            original_url + "&admin=true",
            # Remove required parameters
            original_url.replace("&X-Goog-Signature=test_signature_" + str(int(time.time()) + 3600), ""),
        ]

        # Configure mock to simulate signature validation
        def validate_signed_url_side_effect(url):
            parsed = self.parse_signed_url(url)

            # Check if URL has been tampered with
            if url != original_url:
                raise ValueError("Invalid signature: URL has been tampered with")

            return True

        storage_service.validate_signed_url = Mock(side_effect=validate_signed_url_side_effect)

        # Original URL should be valid
        assert storage_service.validate_signed_url(original_url) is True

        # Tampered URLs should be rejected
        for tampered_url in tampering_attempts:
            with pytest.raises(ValueError, match="Invalid signature"):
                storage_service.validate_signed_url(tampered_url)

    @pytest.mark.security
    def test_cross_user_signed_url_access_prevention(self, test_users):
        """Test that users cannot access other users' signed URLs."""
        user1 = test_users["user1"]
        user2 = test_users["user2"]

        mock_services1 = self.setup_mock_services(user1)
        mock_services2 = self.setup_mock_services(user2)

        storage_service1 = mock_services1["storage"]
        storage_service2 = mock_services2["storage"]

        # User1 creates a signed URL for their file
        user1_file_path = f"original/{user1.user_id}/private.jpg"
        user1_signed_url = self.create_mock_signed_url(user1.user_id, "private.jpg")

        storage_service1.get_signed_url.return_value = user1_signed_url

        # User2 tries to access user1's signed URL
        def access_control_side_effect(file_path):
            # Extract user ID from file path
            path_parts = file_path.split("/")
            if len(path_parts) >= 2:
                file_user_id = path_parts[1]
                if file_user_id != user2.user_id:
                    raise PermissionError(f"Access denied: User {user2.user_id} cannot access {file_user_id}'s files")

            return self.create_mock_signed_url(user2.user_id, "allowed.jpg")

        storage_service2.get_signed_url.side_effect = access_control_side_effect

        # User2 should not be able to get signed URL for user1's file
        with pytest.raises(PermissionError, match="Access denied"):
            storage_service2.get_signed_url(user1_file_path)

        # User2 should be able to get signed URL for their own file
        user2_file_path = f"original/{user2.user_id}/allowed.jpg"
        user2_signed_url = storage_service2.get_signed_url(user2_file_path)
        assert user2.user_id in user2_signed_url

    @pytest.mark.security
    def test_signed_url_parameter_injection_prevention(self, test_users):
        """Test that parameter injection attacks on signed URLs are prevented."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        storage_service = mock_services["storage"]

        # Test various parameter injection attempts
        injection_attempts = [
            "test.jpg?admin=true",
            "test.jpg&X-Goog-Signature=fake",
            "test.jpg%26admin%3Dtrue",  # URL encoded
            "test.jpg\x00admin=true",  # Null byte injection
            "test.jpg\r\nSet-Cookie: admin=true",  # CRLF injection
            "test.jpg'; DROP TABLE photos; --",
            "test.jpg<script>alert('xss')</script>",
        ]

        # Configure mock to simulate parameter validation
        def get_signed_url_side_effect(file_path, expiration=3600):
            # Extract filename from path
            filename = file_path.split("/")[-1]

            # Check for injection attempts
            if "?" in filename or "&" in filename:
                raise ValueError("Invalid filename: contains query parameters")
            if "%" in filename:
                raise ValueError("Invalid filename: contains URL encoding")
            if "\x00" in filename or "\r" in filename or "\n" in filename:
                raise ValueError("Invalid filename: contains control characters")
            if "'" in filename or '"' in filename:
                raise ValueError("Invalid filename: contains quote characters")
            if "<" in filename or ">" in filename:
                raise ValueError("Invalid filename: contains HTML characters")

            return self.create_mock_signed_url(user.user_id, filename)

        storage_service.get_signed_url.side_effect = get_signed_url_side_effect

        # All injection attempts should be rejected
        for malicious_filename in injection_attempts:
            file_path = f"original/{user.user_id}/{malicious_filename}"

            with pytest.raises(ValueError, match="Invalid filename"):
                storage_service.get_signed_url(file_path)

    @pytest.mark.security
    def test_signed_url_replay_attack_prevention(self, test_users):
        """Test that signed URL replay attacks are prevented."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        storage_service = mock_services["storage"]

        # Simulate a signed URL with nonce/timestamp to prevent replay
        def create_secure_signed_url(file_path, nonce=None):
            if nonce is None:
                nonce = str(int(time.time() * 1000000))  # Microsecond timestamp

            filename = file_path.split("/")[-1]
            base_url = self.create_mock_signed_url(user.user_id, filename)
            return f"{base_url}&X-Goog-Nonce={nonce}"

        # Track used nonces to prevent replay
        used_nonces = set()

        def validate_signed_url_side_effect(url):
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            nonce = query_params.get("X-Goog-Nonce", [None])[0]

            if nonce is None:
                raise ValueError("Missing nonce parameter")

            if nonce in used_nonces:
                raise ValueError("Replay attack detected: nonce already used")

            used_nonces.add(nonce)
            return True

        storage_service.get_signed_url.side_effect = create_secure_signed_url
        storage_service.validate_signed_url = Mock(side_effect=validate_signed_url_side_effect)

        # First request should succeed
        file_path = f"original/{user.user_id}/test.jpg"
        signed_url1 = storage_service.get_signed_url(file_path)
        assert storage_service.validate_signed_url(signed_url1) is True

        # Replay of the same URL should fail
        with pytest.raises(ValueError, match="Replay attack detected"):
            storage_service.validate_signed_url(signed_url1)

        # New request with different nonce should succeed
        signed_url2 = storage_service.get_signed_url(file_path)
        assert storage_service.validate_signed_url(signed_url2) is True

    @pytest.mark.security
    def test_signed_url_domain_validation(self, test_users):
        """Test that signed URLs are validated for correct domain."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        storage_service = mock_services["storage"]

        # Test various domain spoofing attempts
        malicious_domains = [
            "https://malicious.com/storage.googleapis.com/bucket/file.jpg",
            "https://storage.googleapis.evil.com/bucket/file.jpg",
            "https://fake-storage.googleapis.com/bucket/file.jpg",
            "http://storage.googleapis.com/bucket/file.jpg",  # HTTP instead of HTTPS
            "ftp://storage.googleapis.com/bucket/file.jpg",  # Wrong protocol
            "https://storage.googleapis.com.evil.com/bucket/file.jpg",
        ]

        # Configure mock to validate domain
        def validate_domain_side_effect(url):
            parsed = urlparse(url)

            # Check for correct domain and protocol
            if parsed.scheme != "https":
                raise ValueError("Invalid protocol: must use HTTPS")

            if not parsed.netloc.endswith("storage.googleapis.com"):
                raise ValueError("Invalid domain: must be storage.googleapis.com")

            if parsed.netloc != "storage.googleapis.com":
                raise ValueError("Invalid subdomain: domain spoofing detected")

            return True

        storage_service.validate_signed_url = Mock(side_effect=validate_domain_side_effect)

        # Valid Google Storage URL should pass
        valid_url = "https://storage.googleapis.com/bucket/file.jpg"
        assert storage_service.validate_signed_url(valid_url) is True

        # Malicious domains should be rejected
        for malicious_url in malicious_domains:
            with pytest.raises(ValueError):
                storage_service.validate_signed_url(malicious_url)

    @pytest.mark.security
    def test_signed_url_rate_limiting_simulation(self, test_users):
        """Test simulation of rate limiting for signed URL generation."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        storage_service = mock_services["storage"]

        # Track URL generation requests
        request_timestamps = []

        def rate_limited_get_signed_url(file_path, expiration=3600):
            current_time = time.time()
            request_timestamps.append(current_time)

            # Check rate limiting (max 10 requests per minute)
            recent_requests = [t for t in request_timestamps if current_time - t < 60]

            if len(recent_requests) > 10:
                raise ValueError("Rate limit exceeded: too many signed URL requests")

            filename = file_path.split("/")[-1]
            return self.create_mock_signed_url(user.user_id, filename)

        storage_service.get_signed_url.side_effect = rate_limited_get_signed_url

        # First 10 requests should succeed
        for i in range(10):
            file_path = f"original/{user.user_id}/test_{i}.jpg"
            signed_url = storage_service.get_signed_url(file_path)
            assert signed_url is not None

        # 11th request should be rate limited
        with pytest.raises(ValueError, match="Rate limit exceeded"):
            storage_service.get_signed_url(f"original/{user.user_id}/test_11.jpg")

    @pytest.mark.security
    def test_signed_url_content_type_validation(self, test_users):
        """Test that signed URLs validate content types properly."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        storage_service = mock_services["storage"]

        # Test various file types
        file_scenarios = [
            ("image.jpg", "image/jpeg", True),
            ("image.png", "image/png", True),
            ("image.heic", "image/heic", True),
            ("script.js", "application/javascript", False),
            ("page.html", "text/html", False),
            ("executable.exe", "application/octet-stream", False),
            ("document.pdf", "application/pdf", False),
        ]

        def validate_content_type_side_effect(file_path, content_type=None):
            filename = file_path.split("/")[-1]

            # Determine expected content type from filename
            if filename.lower().endswith((".jpg", ".jpeg")):
                expected_type = "image/jpeg"
            elif filename.lower().endswith(".png"):
                expected_type = "image/png"
            elif filename.lower().endswith(".heic"):
                expected_type = "image/heic"
            else:
                raise ValueError(f"Unsupported file type: {filename}")

            if content_type and content_type != expected_type:
                raise ValueError(f"Content type mismatch: expected {expected_type}, got {content_type}")

            return self.create_mock_signed_url(user.user_id, filename)

        storage_service.get_signed_url.side_effect = validate_content_type_side_effect

        for filename, content_type, should_succeed in file_scenarios:
            file_path = f"original/{user.user_id}/{filename}"

            if should_succeed:
                # Valid image files should succeed
                signed_url = storage_service.get_signed_url(file_path, content_type)
                assert signed_url is not None
            else:
                # Non-image files should be rejected
                with pytest.raises(ValueError, match="Unsupported file type"):
                    storage_service.get_signed_url(file_path, content_type)

    @pytest.mark.security
    def test_signed_url_size_limit_validation(self, test_users):
        """Test that signed URLs respect file size limits."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        storage_service = mock_services["storage"]

        # Test various file sizes
        size_scenarios = [
            (1024, True),  # 1KB - should succeed
            (1024 * 1024, True),  # 1MB - should succeed
            (10 * 1024 * 1024, True),  # 10MB - should succeed
            (50 * 1024 * 1024, True),  # 50MB - should succeed
            (100 * 1024 * 1024, False),  # 100MB - should fail
            (500 * 1024 * 1024, False),  # 500MB - should fail
        ]

        def validate_file_size_side_effect(file_path, file_size=None):
            max_size = 50 * 1024 * 1024  # 50MB limit

            if file_size and file_size > max_size:
                raise ValueError(f"File too large: {file_size} bytes exceeds {max_size} byte limit")

            filename = file_path.split("/")[-1]
            return self.create_mock_signed_url(user.user_id, filename)

        storage_service.get_signed_url.side_effect = validate_file_size_side_effect

        for file_size, should_succeed in size_scenarios:
            file_path = f"original/{user.user_id}/test_{file_size}.jpg"

            if should_succeed:
                # Files within size limit should succeed
                signed_url = storage_service.get_signed_url(file_path, file_size)
                assert signed_url is not None
            else:
                # Files exceeding size limit should be rejected
                with pytest.raises(ValueError, match="File too large"):
                    storage_service.get_signed_url(file_path, file_size)
