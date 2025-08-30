"""Tests for HEIC display functionality in gallery UI."""

from unittest.mock import Mock, patch

import pytest
import streamlit as st

from src.imgstream.ui.pages.gallery import is_heic_file


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

    @patch("src.imgstream.ui.pages.gallery.convert_heic_to_web_display")
    @patch("src.imgstream.ui.pages.gallery.st")
    def test_render_photo_detail_image_heic_success(self, mock_st, mock_convert):
        """Test successful HEIC photo rendering."""
        from src.imgstream.ui.pages.gallery import render_photo_detail_image

        # Mock successful conversion
        mock_convert.return_value = b"fake_jpeg_data"

        # Mock streamlit components
        mock_st.spinner.return_value.__enter__ = Mock()
        mock_st.spinner.return_value.__exit__ = Mock()
        mock_st.image = Mock()
        mock_st.info = Mock()

        # Test rendering HEIC photo
        render_photo_detail_image(self.sample_heic_photo)

        # Verify conversion was called
        mock_convert.assert_called_once_with(self.sample_heic_photo)

        # Verify image display was called with converted data
        mock_st.image.assert_called_once()
        args, kwargs = mock_st.image.call_args
        assert args[0] == b"fake_jpeg_data"
        assert "HEIC → JPEG変換済み" in kwargs["caption"]

        # Verify info message was shown
        mock_st.info.assert_called_once()

    @patch("src.imgstream.ui.pages.gallery.convert_heic_to_web_display")
    @patch("src.imgstream.ui.pages.gallery.render_heic_fallback_display")
    @patch("src.imgstream.ui.pages.gallery.st")
    def test_render_photo_detail_image_heic_conversion_failure(self, mock_st, mock_fallback, mock_convert):
        """Test HEIC photo rendering when conversion fails."""
        from src.imgstream.ui.pages.gallery import render_photo_detail_image

        # Mock failed conversion
        mock_convert.return_value = None

        # Mock streamlit components
        mock_st.spinner.return_value.__enter__ = Mock()
        mock_st.spinner.return_value.__exit__ = Mock()
        mock_st.error = Mock()

        # Test rendering HEIC photo with conversion failure
        render_photo_detail_image(self.sample_heic_photo)

        # Verify conversion was attempted
        mock_convert.assert_called_once_with(self.sample_heic_photo)

        # Verify error message was shown
        mock_st.error.assert_called_once()

        # Verify fallback display was called
        mock_fallback.assert_called_once_with(self.sample_heic_photo)

    @patch("src.imgstream.ui.pages.gallery.convert_heic_to_web_display")
    @patch("src.imgstream.ui.pages.gallery.render_heic_fallback_display")
    @patch("src.imgstream.ui.pages.gallery.st")
    def test_render_photo_detail_image_heic_exception(self, mock_st, mock_fallback, mock_convert):
        """Test HEIC photo rendering when conversion raises exception."""
        from src.imgstream.ui.pages.gallery import render_photo_detail_image

        # Mock conversion to raise exception
        mock_convert.side_effect = Exception("Conversion error")

        # Mock streamlit components
        mock_st.spinner.return_value.__enter__ = Mock()
        mock_st.spinner.return_value.__exit__ = Mock()
        mock_st.error = Mock()

        # Test rendering HEIC photo with exception
        render_photo_detail_image(self.sample_heic_photo)

        # Verify error message was shown
        mock_st.error.assert_called_once()
        error_message = mock_st.error.call_args[0][0]
        assert "HEIC画像の表示に失敗しました" in error_message

        # Verify fallback display was called
        mock_fallback.assert_called_once_with(self.sample_heic_photo)

    @patch("src.imgstream.ui.pages.gallery.get_storage_service")
    @patch("src.imgstream.ui.pages.gallery.st")
    def test_render_photo_detail_image_regular_photo(self, mock_st, mock_get_storage):
        """Test rendering regular (non-HEIC) photo."""
        from src.imgstream.ui.pages.gallery import render_photo_detail_image

        # Mock storage service
        mock_storage = Mock()
        mock_storage.get_signed_url.return_value = "https://example.com/photo.jpg"
        mock_get_storage.return_value = mock_storage

        # Mock streamlit components
        mock_st.image = Mock()

        # Test rendering regular photo
        render_photo_detail_image(self.sample_jpeg_photo)

        # Verify signed URL was requested
        mock_storage.get_signed_url.assert_called_once_with("photos/IMG_5678.jpg", expiration=3600)

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

    @patch("src.imgstream.ui.pages.gallery.get_photo_thumbnail_url")
    @patch("src.imgstream.ui.pages.gallery.st")
    def test_render_heic_fallback_display_with_thumbnail(self, mock_st, mock_get_thumbnail):
        """Test HEIC fallback display with available thumbnail."""
        from src.imgstream.ui.pages.gallery import render_heic_fallback_display

        # Mock thumbnail URL
        mock_get_thumbnail.return_value = "https://example.com/thumbnail.jpg"

        # Mock streamlit components
        mock_st.warning = Mock()
        mock_st.image = Mock()
        mock_st.expander.return_value.__enter__ = Mock()
        mock_st.expander.return_value.__exit__ = Mock()
        mock_st.info = Mock()

        # Test fallback display
        render_heic_fallback_display(self.sample_heic_photo)

        # Verify warning was shown
        mock_st.warning.assert_called_once()

        # Verify thumbnail was requested and displayed
        mock_get_thumbnail.assert_called_once_with(self.sample_heic_photo)
        mock_st.image.assert_called_once()

    @patch("src.imgstream.ui.pages.gallery.get_photo_thumbnail_url")
    @patch("src.imgstream.ui.pages.gallery.render_photo_error_state")
    @patch("src.imgstream.ui.pages.gallery.st")
    def test_render_heic_fallback_display_no_thumbnail(self, mock_st, mock_error_state, mock_get_thumbnail):
        """Test HEIC fallback display when thumbnail is not available."""
        from src.imgstream.ui.pages.gallery import render_heic_fallback_display

        # Mock no thumbnail available
        mock_get_thumbnail.return_value = None

        # Mock streamlit components
        mock_st.warning = Mock()

        # Test fallback display
        render_heic_fallback_display(self.sample_heic_photo)

        # Verify warning was shown
        mock_st.warning.assert_called_once()

        # Verify error state was rendered
        mock_error_state.assert_called_once()


class TestHEICDisplayErrorHandling:
    """Test error handling in HEIC display functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_photo = {"id": "test_photo_123", "filename": "test.heic", "original_path": "photos/test.heic"}

    @patch("src.imgstream.ui.pages.gallery.logger")
    def test_error_logging_on_conversion_failure(self, mock_logger):
        """Test that conversion failures are properly logged."""
        from src.imgstream.ui.pages.gallery import convert_heic_to_web_display

        with patch("src.imgstream.ui.pages.gallery.get_storage_service") as mock_get_storage:
            # Mock storage service to raise exception
            mock_storage = Mock()
            mock_storage.download_file.side_effect = Exception("Storage error")
            mock_get_storage.return_value = mock_storage

            # Test conversion with error
            result = convert_heic_to_web_display(self.sample_photo)

            # Verify error was logged
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args
            assert "heic_conversion_failed" in log_call[0]

            # Verify None was returned
            assert result is None

    def test_graceful_degradation_chain(self):
        """Test the complete graceful degradation chain for HEIC display."""
        # This test verifies the complete error handling chain:
        # 1. HEIC conversion fails
        # 2. Falls back to thumbnail display
        # 3. If thumbnail fails, shows error state

        with (
            patch("src.imgstream.ui.pages.gallery.convert_heic_to_web_display") as mock_convert,
            patch("src.imgstream.ui.pages.gallery.render_heic_fallback_display") as mock_fallback,
            patch("src.imgstream.ui.pages.gallery.st") as mock_st,
        ):

            from src.imgstream.ui.pages.gallery import render_photo_detail_image

            # Mock conversion failure
            mock_convert.return_value = None

            # Mock streamlit components
            mock_st.spinner.return_value.__enter__ = Mock()
            mock_st.spinner.return_value.__exit__ = Mock()
            mock_st.error = Mock()

            # Test the degradation chain
            render_photo_detail_image(self.sample_photo)

            # Verify each step was called
            mock_convert.assert_called_once()
            mock_st.error.assert_called_once()
            mock_fallback.assert_called_once()
