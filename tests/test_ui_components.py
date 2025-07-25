"""Tests for UI components."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from imgstream.ui.components import (
    format_file_size,
    render_empty_state,
    render_error_message,
    render_footer,
    render_header,
    render_info_card,
)


class TestUIComponents:
    """Test UI component functions."""

    def test_format_file_size_bytes(self):
        """Test file size formatting for bytes."""
        assert format_file_size(500) == "500 B"
        assert format_file_size(1023) == "1023 B"

    def test_format_file_size_kilobytes(self):
        """Test file size formatting for kilobytes."""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"

    def test_format_file_size_megabytes(self):
        """Test file size formatting for megabytes."""
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(int(1024 * 1024 * 2.5)) == "2.5 MB"

    @patch("streamlit.columns")
    @patch("streamlit.markdown")
    @patch("streamlit.button")
    def test_render_empty_state_with_action(self, mock_button, mock_markdown, mock_columns):
        """Test render_empty_state with action button."""
        mock_columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_button.return_value = False

        # Mock session state
        with patch.object(st, "session_state", MagicMock()):
            render_empty_state("Test Title", "Test Description", "🔥", "Test Action", "test_page")

        mock_markdown.assert_called()
        mock_button.assert_called_once()

    @patch("streamlit.columns")
    @patch("streamlit.markdown")
    def test_render_empty_state_without_action(self, mock_markdown, mock_columns):
        """Test render_empty_state without action button."""
        mock_columns.return_value = [MagicMock(), MagicMock(), MagicMock()]

        render_empty_state("Test Title", "Test Description", "🔥")

        mock_markdown.assert_called()

    @patch("streamlit.error")
    @patch("streamlit.expander")
    @patch("streamlit.code")
    def test_render_error_message_with_details(self, mock_code, mock_expander, mock_error):
        """Test render_error_message with details."""
        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock()

        render_error_message("Test Error", "Test Message", "Test Details")

        mock_error.assert_called_once()
        mock_expander.assert_called_once()

    @patch("streamlit.error")
    def test_render_error_message_without_details(self, mock_error):
        """Test render_error_message without details."""
        render_error_message("Test Error", "Test Message")

        mock_error.assert_called_once()

    @patch("streamlit.markdown")
    def test_render_info_card(self, mock_markdown):
        """Test render_info_card."""
        render_info_card("Test Title", "Test Content", "🔥")

        mock_markdown.assert_called_once()

    def test_component_functions_exist(self):
        """Test that all component functions exist and are callable."""
        assert callable(render_empty_state)
        assert callable(render_error_message)
        assert callable(render_info_card)
        assert callable(format_file_size)
        assert callable(render_header)
        assert callable(render_footer)
