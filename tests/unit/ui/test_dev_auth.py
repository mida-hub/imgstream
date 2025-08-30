"""Tests for development authentication functionality."""

import os
from unittest.mock import Mock, patch

from imgstream.services.auth import UserInfo
from imgstream.ui.handlers.dev_auth import (
    _is_development_mode,
    authenticate_test_user,
    create_test_user,
)


class TestDevelopmentMode:
    """Test development mode detection."""

    def test_is_development_mode_with_development(self):
        """Test development mode detection with 'development' environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            assert _is_development_mode() is True

    def test_is_development_mode_with_dev(self):
        """Test development mode detection with 'dev' environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            assert _is_development_mode() is True

    def test_is_development_mode_with_local(self):
        """Test development mode detection with 'local' environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            assert _is_development_mode() is True

    def test_is_development_mode_with_production(self):
        """Test development mode detection with 'production' environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert _is_development_mode() is False

    def test_is_development_mode_default(self):
        """Test development mode detection with default environment."""
        with patch.dict(os.environ, {}, clear=True):
            # Default should be development
            assert _is_development_mode() is True


class TestTestUserCreation:
    """Test test user creation utilities."""

    def test_create_test_user_default(self):
        """Test creating test user with default values."""
        user = create_test_user()

        assert user.email == "test@example.com"
        assert user.user_id == "test-user-001"
        assert user.picture is None

    def test_create_test_user_custom(self):
        """Test creating test user with custom values."""
        user = create_test_user(email="custom@example.com", user_id="custom-001")

        assert user.email == "custom@example.com"
        assert user.user_id == "custom-001"
        assert user.picture is None

    @patch("imgstream.ui.handlers.dev_auth.get_auth_service")
    def test_authenticate_test_user_default(self, mock_get_auth_service):
        """Test authenticating test user with default values."""
        mock_auth_service = Mock()
        mock_get_auth_service.return_value = mock_auth_service

        user = authenticate_test_user()

        # Verify user was created with defaults
        assert user.email == "test@example.com"
        assert user.user_id == "test-user-001"

        # Verify auth service was called
        mock_auth_service.set_current_user.assert_called_once_with(user)

    @patch("imgstream.ui.handlers.dev_auth.get_auth_service")
    def test_authenticate_test_user_custom(self, mock_get_auth_service):
        """Test authenticating test user with custom user."""
        mock_auth_service = Mock()
        mock_get_auth_service.return_value = mock_auth_service

        custom_user = UserInfo(
            user_id="custom-123",
            email="custom@test.com",
            picture=None,
        )

        result_user = authenticate_test_user(custom_user)

        # Verify the same user was returned
        assert result_user == custom_user

        # Verify auth service was called with custom user
        mock_auth_service.set_current_user.assert_called_once_with(custom_user)


class TestDevelopmentAuthService:
    """Test development authentication service integration."""

    def test_development_mode_detection_in_auth_service(self):
        """Test that auth service correctly detects development mode."""
        from src.imgstream.services.auth import CloudIAPAuthService

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            auth_service = CloudIAPAuthService()
            # Verify development mode is detected
            assert auth_service._development_mode is True

    def test_development_user_creation_in_auth_service(self):
        """Test that auth service creates correct development user."""
        from src.imgstream.services.auth import CloudIAPAuthService

        env_vars = {
            "ENVIRONMENT": "development",
            "DEV_USER_EMAIL": "dev@example.com",
            "DEV_USER_ID": "dev-123",
        }

        with patch.dict(os.environ, env_vars):
            auth_service = CloudIAPAuthService()
            dev_user = auth_service._get_development_user()

            assert dev_user.email == "dev@example.com"
            assert dev_user.user_id == "dev-123"
            assert dev_user.picture is None

    def test_development_authentication_bypass(self):
        """Test that development mode bypasses IAP authentication."""
        from src.imgstream.services.auth import CloudIAPAuthService

        env_vars = {
            "ENVIRONMENT": "development",
            "DEV_USER_EMAIL": "dev@example.com",
            "DEV_USER_ID": "dev-123",
        }

        with patch.dict(os.environ, env_vars):
            auth_service = CloudIAPAuthService()

            # Test that parse_iap_header returns development user without IAP header
            user_info = auth_service.parse_iap_header({})

            assert user_info is not None
            assert user_info.email == "dev@example.com"
            assert user_info.user_id == "dev-123"

    def test_production_mode_requires_iap(self):
        """Test that production mode requires IAP authentication."""
        from src.imgstream.services.auth import CloudIAPAuthService

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            auth_service = CloudIAPAuthService()

            # Verify production mode is detected
            assert auth_service._development_mode is False

            # Test that parse_iap_header returns None without IAP header
            user_info = auth_service.parse_iap_header({})

            assert user_info is None


class TestEnvironmentVariables:
    """Test environment variable handling."""

    def test_development_user_defaults(self):
        """Test development user creation with default environment variables."""
        from src.imgstream.services.auth import CloudIAPAuthService

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            auth_service = CloudIAPAuthService()
            dev_user = auth_service._get_development_user()

            # Should use defaults when env vars are not set
            assert dev_user.email == "dev@example.com"
            assert dev_user.user_id == "dev-user-123"

    def test_development_user_custom_env_vars(self):
        """Test development user creation with custom environment variables."""
        from src.imgstream.services.auth import CloudIAPAuthService

        custom_env = {
            "ENVIRONMENT": "development",
            "DEV_USER_EMAIL": "custom@dev.com",
            "DEV_USER_ID": "custom-dev-456",
        }

        with patch.dict(os.environ, custom_env, clear=True):
            auth_service = CloudIAPAuthService()
            dev_user = auth_service._get_development_user()

            assert dev_user.email == "custom@dev.com"
            assert dev_user.user_id == "custom-dev-456"


class TestSecurityConsiderations:
    """Test security aspects of development authentication."""

    def test_development_mode_only_in_dev_environment(self):
        """Test that development mode is only enabled in development environments."""
        from src.imgstream.services.auth import CloudIAPAuthService

        production_environments = ["production", "prod", "staging"]

        for env in production_environments:
            with patch.dict(os.environ, {"ENVIRONMENT": env}, clear=True):
                auth_service = CloudIAPAuthService()
                assert (
                    auth_service._development_mode is False
                ), f"Development mode should be disabled in {env} environment"

    def test_development_user_isolation(self):
        """Test that development users have unique identifiers for isolation."""
        dev_user = create_test_user(email="dev@example.com", user_id="dev-001")
        prod_user = create_test_user(email="user@production.com", user_id="prod-001")

        # Verify users have different identifiers
        assert dev_user.email != prod_user.email
        assert dev_user.user_id != prod_user.user_id

        # Verify development user has expected properties
        assert dev_user.email == "dev@example.com"
        assert dev_user.user_id == "dev-001"
        assert dev_user.picture is None

        # Verify production user has expected properties
        assert prod_user.email == "user@production.com"
        assert prod_user.user_id == "prod-001"
        assert prod_user.picture is None
