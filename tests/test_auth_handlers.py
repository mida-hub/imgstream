"""Tests for authentication handlers."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from imgstream.ui.handlers.auth_handlers import authenticate_user, handle_logout, require_authentication
from imgstream.ui.components.ui_components import render_sidebar


class TestAuthHandlers:
    """Test authentication handler functions."""

    @patch("imgstream.ui.handlers.auth_handlers.get_auth_service")
    @patch("streamlit.secrets")
    def test_authenticate_user_mock_success(self, mock_secrets, mock_get_auth_service):
        """Test authenticate_user with mock user success."""
        # Mock secrets
        mock_secrets.get.side_effect = lambda key, default=None: {
            "mock_user": {"enabled": True, "email": "test@example.com", "user_id": "test123", "name": "Test User"}
        }.get(key, default)

        # Mock auth service
        mock_auth_service = MagicMock()
        mock_auth_service.IAP_HEADER_NAME = "X-Goog-IAP-JWT-Assertion"
        mock_user_info = MagicMock()
        mock_user_info.email = "test@example.com"
        mock_user_info.user_id = "test123"
        mock_auth_service.ensure_authenticated.return_value = mock_user_info
        mock_get_auth_service.return_value = mock_auth_service

        # Mock session state
        mock_session_state = MagicMock()
        with patch.object(st, "session_state", mock_session_state):
            result = authenticate_user()

        assert result is True
        assert mock_session_state.authenticated is True
        assert mock_session_state.user_email == "test@example.com"

    @patch("imgstream.ui.handlers.auth_handlers.get_auth_service")
    def test_authenticate_user_failure(self, mock_get_auth_service):
        """Test authenticate_user failure."""
        # Mock auth service
        mock_auth_service = MagicMock()
        mock_auth_service.IAP_HEADER_NAME = "X-Goog-IAP-JWT-Assertion"
        mock_auth_service.authenticate_request.return_value = False
        mock_get_auth_service.return_value = mock_auth_service

        # Mock session state
        mock_session_state = MagicMock()
        mock_secrets_obj = MagicMock()
        mock_secrets_obj.get.return_value = None  # No mock_user

        with patch.object(st, "session_state", mock_session_state):
            with patch.object(st, "secrets", mock_secrets_obj):
                result = authenticate_user()

        assert result is False
        assert mock_session_state.authenticated is False

    @patch("imgstream.ui.handlers.auth_handlers.get_auth_service")
    def test_handle_logout(self, mock_get_auth_service):
        """Test handle_logout."""
        # Mock auth service
        mock_auth_service = MagicMock()
        mock_get_auth_service.return_value = mock_auth_service

        # Mock session state
        mock_session_state = MagicMock()
        with patch.object(st, "session_state", mock_session_state):
            with patch.object(st, "rerun") as mock_rerun:
                handle_logout()

        mock_auth_service.clear_authentication.assert_called_once()
        assert mock_session_state.authenticated is False
        mock_rerun.assert_called_once()

    @patch("imgstream.ui.handlers.auth_handlers.render_error_message")
    @patch("streamlit.button")
    def test_require_authentication_failure(self, mock_button, mock_render_error):
        """Test require_authentication when not authenticated."""
        mock_button.return_value = False

        # Mock session state
        mock_session_state = MagicMock()
        mock_session_state.authenticated = False
        mock_session_state.auth_error = "Test error"

        with patch.object(st, "session_state", mock_session_state):
            result = require_authentication()

        assert result is False
        mock_render_error.assert_called_once()

    def test_require_authentication_success(self):
        """Test require_authentication when authenticated."""
        # Mock session state
        mock_session_state = MagicMock()
        mock_session_state.authenticated = True

        with patch.object(st, "session_state", mock_session_state):
            result = require_authentication()

        assert result is True

    def test_auth_functions_exist(self):
        """Test that all auth functions exist and are callable."""
        assert callable(authenticate_user)
        assert callable(handle_logout)
        assert callable(require_authentication)
        assert callable(render_sidebar)
