"""
Tests for the main application module.
"""

from unittest.mock import MagicMock, patch


def test_main_imports():
    """Test that main module can be imported without errors."""
    from src.imgstream import main

    assert main is not None


@patch("streamlit.set_page_config")
@patch("streamlit.title")
@patch("streamlit.subheader")
@patch("streamlit.info")
@patch("streamlit.write")
def test_main_function(
    mock_write: MagicMock,
    mock_info: MagicMock,
    mock_subheader: MagicMock,
    mock_title: MagicMock,
    mock_set_page_config: MagicMock,
):
    """Test the main function calls Streamlit functions correctly."""
    from src.imgstream.main import main

    main()

    # Verify Streamlit functions were called
    mock_set_page_config.assert_called_once()
    mock_title.assert_called_once_with("📸 imgstream")
    mock_subheader.assert_called_once_with("Personal Photo Management")
    mock_info.assert_called_once()
    mock_write.assert_called_once()
