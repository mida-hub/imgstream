"""Tests for main Streamlit application."""

# Import the main module
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from imgstream.main import main


class TestMainApplication:
    """Test main application functionality."""

    @patch("imgstream.main.authenticate_user")
    @patch("imgstream.main.logger")
    @patch("streamlit.set_page_config")
    @patch("streamlit.markdown")
    @patch("streamlit.columns")
    @patch("streamlit.sidebar")
    @patch("streamlit.container")
    @patch("streamlit.secrets")
    def test_main_function_basic(
        self,
        mock_secrets,
        mock_container,
        mock_sidebar,
        mock_columns,
        mock_markdown,
        mock_set_page_config,
        mock_logger,
        mock_authenticate,
    ):
        """Test basic main function execution."""
        mock_secrets.get.return_value = False
        mock_columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_authenticate.return_value = False

        # Mock session state
        mock_session_state = MagicMock()
        mock_session_state.authenticated = False
        mock_session_state.current_page = "home"
        mock_session_state.user_email = None

        with patch.object(st, "session_state", mock_session_state):
            main()

        # Verify page configuration
        mock_set_page_config.assert_called_once()

        # Verify basic UI elements are called
        mock_markdown.assert_called()

        # Verify authentication is attempted
        mock_authenticate.assert_called_once()

        # Verify structured logging is used
        mock_logger.info.assert_called()

    def test_main_function_can_be_imported(self):
        """Test that main function can be imported and called."""
        # This is a basic smoke test
        assert callable(main)


def test_import_main():
    """Test that main module can be imported."""
    from src.imgstream import main

    assert main is not None


def test_main_function_exists():
    """Test that main function exists."""
    from src.imgstream.main import main

    assert callable(main)


def test_structlog_configuration():
    """Test that structlog is properly configured."""
    # Import after configuration
    from imgstream.main import logger

    # Verify logger is a structlog logger
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
    assert hasattr(logger, "warning")

    # Test that logger can be called with structured data
    try:
        logger.info("test_message", key="value", number=123)
    except Exception as e:
        raise AssertionError(f"Structured logging failed: {e}") from e


def test_authentication_functions():
    """Test authentication-related functions."""
    from imgstream.main import authenticate_user, handle_logout, require_authentication

    # Verify functions exist and are callable
    assert callable(authenticate_user)
    assert callable(handle_logout)
    assert callable(require_authentication)


def test_ui_helper_functions():
    """Test UI helper functions."""
    from imgstream.main import render_empty_state, render_error_message, render_info_card

    # Verify UI helper functions exist and are callable
    assert callable(render_empty_state)
    assert callable(render_error_message)
    assert callable(render_info_card)
