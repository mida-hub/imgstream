"""Unit tests for development mode validation improvements."""

import pytest
from unittest.mock import patch

from src.imgstream.services.auth import CloudIAPAuthService


class TestDevelopmentModeValidation:
    """Test development mode validation and error handling."""

    def test_invalid_dev_email_fallback(self):
        """Test fallback to default email when DEV_USER_EMAIL is invalid."""
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DEV_USER_EMAIL": "invalid-email",  # No @ symbol
                "DEV_USER_NAME": "Test User",
                "DEV_USER_ID": "test-123",
            },
        ):
            service = CloudIAPAuthService()
            user = service._get_development_user()

            # Should fallback to default email
            assert user.email == "dev@example.com"
            assert user.name == "Test User"
            assert user.user_id == "test-123"

    def test_empty_dev_email_fallback(self):
        """Test fallback to default email when DEV_USER_EMAIL is empty."""
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DEV_USER_EMAIL": "",
                "DEV_USER_NAME": "Test User",
                "DEV_USER_ID": "test-123",
            },
        ):
            service = CloudIAPAuthService()
            user = service._get_development_user()

            assert user.email == "dev@example.com"
            assert user.name == "Test User"
            assert user.user_id == "test-123"

    def test_empty_dev_name_fallback(self):
        """Test fallback to default name when DEV_USER_NAME is empty."""
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DEV_USER_EMAIL": "test@example.com",
                "DEV_USER_NAME": "   ",  # Only whitespace
                "DEV_USER_ID": "test-123",
            },
        ):
            service = CloudIAPAuthService()
            user = service._get_development_user()

            assert user.email == "test@example.com"
            assert user.name == "Development User"
            assert user.user_id == "test-123"

    def test_empty_dev_user_id_fallback(self):
        """Test fallback to default user ID when DEV_USER_ID is empty."""
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DEV_USER_EMAIL": "test@example.com",
                "DEV_USER_NAME": "Test User",
                "DEV_USER_ID": "",
            },
        ):
            service = CloudIAPAuthService()
            user = service._get_development_user()

            assert user.email == "test@example.com"
            assert user.name == "Test User"
            assert user.user_id == "dev-user-123"

    def test_environment_mode_detection_test(self):
        """Test that 'test' environment is detected as development mode."""
        with patch.dict("os.environ", {"ENVIRONMENT": "test"}):
            service = CloudIAPAuthService()
            assert service._development_mode is True

    def test_environment_mode_detection_local(self):
        """Test that 'local' environment is detected as development mode."""
        with patch.dict("os.environ", {"ENVIRONMENT": "local"}):
            service = CloudIAPAuthService()
            assert service._development_mode is True

    def test_environment_mode_detection_production(self):
        """Test that 'production' environment is detected as production mode."""
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            service = CloudIAPAuthService()
            assert service._development_mode is False

    def test_environment_mode_detection_staging(self):
        """Test that 'staging' environment is detected as production mode."""
        with patch.dict("os.environ", {"ENVIRONMENT": "staging"}):
            service = CloudIAPAuthService()
            assert service._development_mode is False

    def test_environment_mode_with_whitespace(self):
        """Test that environment detection handles whitespace correctly."""
        with patch.dict("os.environ", {"ENVIRONMENT": "  development  "}):
            service = CloudIAPAuthService()
            assert service._development_mode is True

    def test_all_invalid_dev_vars_fallback(self):
        """Test fallback when all development environment variables are invalid."""
        with patch.dict(
            "os.environ",
            {"ENVIRONMENT": "development", "DEV_USER_EMAIL": "invalid", "DEV_USER_NAME": "", "DEV_USER_ID": "   "},
        ):
            service = CloudIAPAuthService()
            user = service._get_development_user()

            # All should fallback to defaults
            assert user.email == "dev@example.com"
            assert user.name == "Development User"
            assert user.user_id == "dev-user-123"
            assert user.picture is None

    def test_development_user_consistency(self):
        """Test that development user creation is consistent across calls."""
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DEV_USER_EMAIL": "consistent@example.com",
                "DEV_USER_NAME": "Consistent User",
                "DEV_USER_ID": "consistent-123",
            },
        ):
            service = CloudIAPAuthService()

            user1 = service._get_development_user()
            user2 = service._get_development_user()

            # Should be identical
            assert user1.user_id == user2.user_id
            assert user1.email == user2.email
            assert user1.name == user2.name
            assert user1.picture == user2.picture
