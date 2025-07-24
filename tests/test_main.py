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

    @patch("imgstream.main.logger")
    @patch("streamlit.set_page_config")
    @patch("streamlit.title")
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
        mock_title,
        mock_set_page_config,
        mock_logger,
    ):
        """Test basic main function execution."""
        mock_secrets.get.return_value = False
        mock_columns.return_value = [MagicMock(), MagicMock(), MagicMock()]

        # Mock session state
        mock_session_state = MagicMock()
        mock_session_state.authenticated = False
        mock_session_state.current_page = "home"

        with patch.object(st, "session_state", mock_session_state):
            main()

        # Verify page configuration
        mock_set_page_config.assert_called_once()

        # Verify basic UI elements are called
        mock_title.assert_called()
        mock_markdown.assert_called()

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

    def test_structlog_configuration(self):
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
