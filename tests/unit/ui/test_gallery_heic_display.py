"""Tests for HEIC display functionality in gallery UI."""

from unittest.mock import Mock, patch, MagicMock

import pytest
import streamlit as st

from src.imgstream.ui.handlers.gallery import is_heic_file, convert_heic_to_web_display


@pytest.fixture
def mock_is_heic_file():
    with patch("src.imgstream.ui.components.gallery.is_heic_file") as mock:
        yield mock

@pytest.fixture
def mock_convert_heic_to_web_display():
    with patch("src.imgstream.ui.components.gallery.convert_heic_to_web_display") as mock:
        yield mock

@pytest.fixture
def mock_render_heic_fallback_display():
    with patch("src.imgstream.ui.components.gallery.render_heic_fallback_display") as mock:
        yield mock

@pytest.fixture
def mock_get_photo_original_url():
    with patch("src.imgstream.ui.components.gallery.get_photo_original_url") as mock:
        yield mock

@pytest.fixture
def mock_get_photo_thumbnail_url():
    with patch("src.imgstream.ui.components.gallery.get_photo_thumbnail_url") as mock:
        yield mock

@pytest.fixture
def mock_st():
    with patch("src.imgstream.ui.components.gallery.st") as mock:
        # Mock common streamlit components used in tests
        mock.spinner.return_value.__enter__ = Mock()
        mock.spinner.return_value.__exit__ = Mock()
        mock.image = Mock()
        mock.info = Mock()
        mock.error = Mock()
        mock.warning = Mock()
        yield mock

@pytest.fixture
def mock_gallery_handlers_st():
    # This fixture is for tests that patch st directly in handlers.gallery
    with patch("src.imgstream.ui.handlers.gallery.st") as mock:
        yield mock

@pytest.fixture
def mock_gallery_handlers_logger():
    with patch("src.imgstream.ui.handlers.gallery.logger") as mock:
        yield mock

@pytest.fixture
def mock_gallery_handlers_get_storage_service():
    with patch("src.imgstream.ui.handlers.gallery.get_storage_service") as mock:
        yield mock


class TestGalleryHEICDisplay:
    """Test HEIC display functionality in gallery UI."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_heic_photo = {
            "id": "test_heic_123",
            "filename": "IMG_1234.heic",
            "original_path": "photos/IMG_1234.heic",
            "thumbnail_path": "thumbnails/IMG_1234_thumb.jpg",
        }

        self.sample_jpeg_photo = {
            "id": "test_jpeg_456",
            "filename": "IMG_5678.jpg",
            "original_path": "photos/IMG_5678.jpg",
            "thumbnail_path": "thumbnails/IMG_5678_thumb.jpg",
        }

    def test_render_photo_detail_image_heic_success(self, mock_st, mock_is_heic_file, mock_convert_heic_to_web_display):
        """Test successful HEIC photo rendering."""
        from src.imgstream.ui.components.gallery import render_photo_detail_image

        # Mock HEIC file detection
        mock_is_heic_file.return_value = True

        # Mock successful conversion
        mock_convert_heic_to_web_display.return_value = b"fake_jpeg_data"

        # Test rendering HEIC photo
        render_photo_detail_image(self.sample_heic_photo)

        # Verify HEIC detection was called
        mock_is_heic_file.assert_called_once_with(self.sample_heic_photo["filename"])

        # Verify conversion was called with correct arguments
        mock_convert_heic_to_web_display.assert_called_once_with(self.sample_heic_photo["original_path"], self.sample_heic_photo["id"])

        # Verify image display was called with converted data
        mock_st.image.assert_called_once()
        args, kwargs = mock_st.image.call_args
        assert args[0] == b"fake_jpeg_data"
        assert "HEIC → JPEG変換済み" in kwargs["caption"]

        # Verify info message was shown
        mock_st.info.assert_called_once()

    def test_render_photo_detail_image_heic_conversion_failure(
        self, mock_st, mock_render_heic_fallback_display, mock_is_heic_file, mock_convert_heic_to_web_display
    ):
        """Test HEIC photo rendering when conversion fails."""
        from src.imgstream.ui.components.gallery import render_photo_detail_image

        # Mock HEIC file detection
        mock_is_heic_file.return_value = True

        # Mock failed conversion
        mock_convert_heic_to_web_display.return_value = None

        # Test rendering HEIC photo with conversion failure
        render_photo_detail_image(self.sample_heic_photo)

        # Verify HEIC detection was called
        mock_is_heic_file.assert_called_once_with(self.sample_heic_photo["filename"])

        # Verify conversion was attempted with correct arguments
        mock_convert_heic_to_web_display.assert_called_once_with(self.sample_heic_photo["original_path"], self.sample_heic_photo["id"])

        # Verify error message was shown
        mock_st.error.assert_called_once()

        # Verify fallback display was called
        mock_render_heic_fallback_display.assert_called_once_with(self.sample_heic_photo)

    def test_render_photo_detail_image_heic_exception(self, mock_st, mock_render_heic_fallback_display, mock_is_heic_file, mock_convert_heic_to_web_display):
        """Test HEIC photo rendering when conversion raises exception."""
        from src.imgstream.ui.components.gallery import render_photo_detail_image

        # Mock HEIC file detection
        mock_is_heic_file.return_value = True

        # Mock conversion to raise exception
        mock_convert_heic_to_web_display.side_effect = Exception("Conversion error")

        # Test rendering HEIC photo with exception
        render_photo_detail_image(self.sample_heic_photo)

        # Verify HEIC detection was called
        mock_is_heic_file.assert_called_once_with(self.sample_heic_photo["filename"])

        # Verify error message was shown
        mock_st.error.assert_called_once()
        error_message = mock_st.error.call_args[0][0]
        assert "HEIC画像の表示に失敗しました" in error_message

        # Verify fallback display was called
        mock_render_heic_fallback_display.assert_called_once_with(self.sample_heic_photo)

    def test_render_photo_detail_image_regular_photo(self, mock_st, mock_is_heic_file, mock_get_photo_original_url):
        """Test rendering regular (non-HEIC) photo."""
        from src.imgstream.ui.components.gallery import render_photo_detail_image

        # Mock non-HEIC file detection
        mock_is_heic_file.return_value = False

        # Mock original URL
        mock_get_photo_original_url.return_value = "https://example.com/photo.jpg"

        # Test rendering regular photo
        render_photo_detail_image(self.sample_jpeg_photo)

        # Verify HEIC detection was called
        mock_is_heic_file.assert_called_once_with(self.sample_jpeg_photo["filename"])

        # Verify original URL was requested with correct arguments
        mock_get_photo_original_url.assert_called_once_with(
            self.sample_jpeg_photo["original_path"], self.sample_jpeg_photo["id"]
        )

        # Verify image was displayed with URL
        mock_st.image.assert_called_once()
        args, kwargs = mock_st.image.call_args
        assert args[0] == "https://example.com/photo.jpg"

    def test_is_heic_file_integration(self):
        """Test HEIC file detection integration with photo objects."""
        # Test with HEIC photo
        assert is_heic_file(self.sample_heic_photo["filename"]) is True

        # Test with JPEG photo
        assert is_heic_file(self.sample_jpeg_photo["filename"]) is False

        # Test with various HEIC extensions
        heic_filenames = ["IMG_1234.heic", "photo.HEIC", "vacation.Heif", "portrait.HEIF"]

        for filename in heic_filenames:
            photo = {"filename": filename}
            assert is_heic_file(photo["filename"]) is True

    def test_render_heic_fallback_display_with_thumbnail(self, mock_st, mock_get_photo_thumbnail_url):
        """Test HEIC fallback display with available thumbnail."""
        from src.imgstream.ui.components.gallery import render_heic_fallback_display

        # Mock thumbnail URL
        mock_get_photo_thumbnail_url.return_value = "https://example.com/thumbnail.jpg"

        # Test fallback display
        render_heic_fallback_display(self.sample_heic_photo)

        # Verify warning was shown
        mock_st.warning.assert_called_once()

        # Verify thumbnail was requested with correct arguments
        mock_get_photo_thumbnail_url.assert_called_once_with(
            self.sample_heic_photo["thumbnail_path"], self.sample_heic_photo["id"]
        )
        mock_st.image.assert_called_once()

    def test_render_heic_fallback_display_no_thumbnail(self, mock_st, mock_get_photo_thumbnail_url):
        """Test HEIC fallback display when thumbnail is not available."""
        from src.imgstream.ui.components.gallery import render_heic_fallback_display

        # Mock no thumbnail available
        mock_get_photo_thumbnail_url.return_value = None

        # Test fallback display
        render_heic_fallback_display(self.sample_heic_photo)

        # Verify warning was shown
        mock_st.warning.assert_called_once()

        # Verify thumbnail was requested with correct arguments
        mock_get_photo_thumbnail_url.assert_called_once_with(
            self.sample_heic_photo["thumbnail_path"], self.sample_heic_photo["id"]
        )

        # Verify error message was shown when no thumbnail available
        mock_st.error.assert_called_once()
        mock_st.info.assert_called_once()


class TestHEICDisplayErrorHandling:
    """Test error handling in HEIC display functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_photo = {"id": "test_photo_123", "filename": "test.heic", "original_path": "photos/test.heic"}

    def test_error_logging_on_conversion_failure(self, mock_gallery_handlers_logger, mock_gallery_handlers_get_storage_service):
        """Test that conversion failures are properly logged."""
        # Mock storage service to raise exception
        mock_storage = Mock()
        mock_storage.download_file.side_effect = Exception("Storage error")
        mock_gallery_handlers_get_storage_service.return_value = mock_storage

        # Test conversion with error using correct arguments
        result = convert_heic_to_web_display(self.sample_photo["original_path"], self.sample_photo["id"])

        # Verify error was logged
        mock_gallery_handlers_logger.error.assert_called_once()
        log_call = mock_gallery_handlers_logger.error.call_args[0][0]
        assert "heic_conversion_failed" in log_call

        # Verify None was returned
        assert result is None

    def test_graceful_degradation_chain(self, mock_convert_heic_to_web_display, mock_is_heic_file, mock_render_heic_fallback_display, mock_st):
        """Test the complete graceful degradation chain for HEIC display."""
        # This test verifies the complete error handling chain:
        # 1. HEIC conversion fails
        # 2. Falls back to thumbnail display
        # 3. If thumbnail fails, shows error state

        from src.imgstream.ui.components.gallery import render_photo_detail_image

        # Mock HEIC file detection
        mock_is_heic_file.return_value = True

        # Mock conversion failure
        mock_convert_heic_to_web_display.return_value = None

        # Test the degradation chain
        render_photo_detail_image(self.sample_photo)

        # Verify each step was called
        mock_is_heic_file.assert_called_once()
        mock_convert_heic_to_web_display.assert_called_once()
        mock_st.error.assert_called_once()
        mock_render_heic_fallback_display.assert_called_once()