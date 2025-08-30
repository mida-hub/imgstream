"""Tests for HEIC web display conversion functionality."""

import io
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from src.imgstream.services.image_processor import ImageProcessor
from src.imgstream.ui.handlers.error import ImageProcessingError
from src.imgstream.ui.pages.gallery import is_heic_file


class TestHEICWebDisplayConversion:
    """Test HEIC to JPEG conversion for web display."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = ImageProcessor()

    def create_test_image(self, format_type: str = "JPEG", size: tuple[int, int] = (800, 600)) -> bytes:
        """Create a test image in memory."""
        image = Image.new("RGB", size, color="red")
        buffer = io.BytesIO()
        image.save(buffer, format=format_type, quality=90)
        return buffer.getvalue()

    def test_convert_to_web_display_jpeg_success(self):
        """Test successful JPEG conversion with default quality."""
        # Create test image data
        test_image_data = self.create_test_image("JPEG", (1200, 800))

        # Convert to web display JPEG
        result = self.processor.convert_to_web_display_jpeg(test_image_data)

        # Verify result
        assert isinstance(result, bytes)
        assert len(result) > 0

        # Verify the result is a valid JPEG
        with Image.open(io.BytesIO(result)) as converted_image:
            assert converted_image.format == "JPEG"
            assert converted_image.size == (1200, 800)  # Original dimensions preserved
            assert converted_image.mode == "RGB"

    def test_convert_to_web_display_jpeg_custom_quality(self):
        """Test JPEG conversion with custom quality setting."""
        test_image_data = self.create_test_image("JPEG", (800, 600))

        # Convert with custom quality
        result = self.processor.convert_to_web_display_jpeg(test_image_data, quality=95)

        # Verify result
        assert isinstance(result, bytes)
        assert len(result) > 0

        # Verify the result is a valid JPEG
        with Image.open(io.BytesIO(result)) as converted_image:
            assert converted_image.format == "JPEG"
            assert converted_image.size == (800, 600)

    def test_convert_to_web_display_jpeg_maintains_aspect_ratio(self):
        """Test that conversion maintains original aspect ratio and dimensions."""
        # Test with various aspect ratios
        test_cases = [
            (1920, 1080),  # 16:9
            (1080, 1920),  # 9:16 (portrait)
            (1000, 1000),  # 1:1 (square)
            (1600, 900),  # 16:9 different size
        ]

        for width, height in test_cases:
            test_image_data = self.create_test_image("JPEG", (width, height))
            result = self.processor.convert_to_web_display_jpeg(test_image_data)

            with Image.open(io.BytesIO(result)) as converted_image:
                assert converted_image.size == (width, height)

    def test_convert_to_web_display_jpeg_handles_different_modes(self):
        """Test that images with different color modes are properly converted."""
        # Test with RGBA mode (should be converted to RGB)
        rgba_image = Image.new("RGBA", (400, 300), color=(255, 0, 0, 128))
        buffer = io.BytesIO()
        rgba_image.save(buffer, format="PNG")
        rgba_data = buffer.getvalue()

        result = self.processor.convert_to_web_display_jpeg(rgba_data)

        # Verify result is valid JPEG
        with Image.open(io.BytesIO(result)) as converted_image:
            assert converted_image.format == "JPEG"
            assert converted_image.mode == "RGB"  # Should be converted to RGB
            assert converted_image.size == (400, 300)

    def test_convert_to_web_display_jpeg_quality_bounds(self):
        """Test conversion with quality at boundary values."""
        test_image_data = self.create_test_image("JPEG", (400, 300))

        # Test minimum quality
        result_min = self.processor.convert_to_web_display_jpeg(test_image_data, quality=1)
        assert isinstance(result_min, bytes)
        assert len(result_min) > 0

        # Test maximum quality
        result_max = self.processor.convert_to_web_display_jpeg(test_image_data, quality=100)
        assert isinstance(result_max, bytes)
        assert len(result_max) > 0

        # Higher quality should generally result in larger file size
        assert len(result_max) >= len(result_min)

    def test_convert_to_web_display_jpeg_default_quality_90(self):
        """Test that default quality is 90 as specified in requirements."""
        test_image_data = self.create_test_image("JPEG", (600, 400))

        # Call without quality parameter
        result_default = self.processor.convert_to_web_display_jpeg(test_image_data)

        # Call with explicit quality 90
        result_explicit = self.processor.convert_to_web_display_jpeg(test_image_data, quality=90)

        # Results should be identical
        assert result_default == result_explicit

    def test_convert_to_web_display_jpeg_invalid_data(self):
        """Test conversion with invalid image data."""
        # Test with empty data
        with pytest.raises(ImageProcessingError):
            self.processor.convert_to_web_display_jpeg(b"")

        # Test with invalid image data
        with pytest.raises(ImageProcessingError):
            self.processor.convert_to_web_display_jpeg(b"not an image")

        # Test with None
        with pytest.raises((ImageProcessingError, TypeError)):
            self.processor.convert_to_web_display_jpeg(None)

    def test_convert_to_web_display_jpeg_corrupted_data(self):
        """Test conversion with corrupted image data."""
        # Create valid image data then corrupt it
        valid_data = self.create_test_image("JPEG", (400, 300))
        corrupted_data = valid_data[: len(valid_data) // 2] + b"corrupted"

        with pytest.raises(ImageProcessingError):
            self.processor.convert_to_web_display_jpeg(corrupted_data)

    def test_convert_to_web_display_jpeg_invalid_quality(self):
        """Test conversion with invalid quality values."""
        test_image_data = self.create_test_image("JPEG", (400, 300))

        # Test with quality out of range (implementation may accept 0-100)
        # Test with quality above 100
        with pytest.raises((ValueError, ImageProcessingError)):
            self.processor.convert_to_web_display_jpeg(test_image_data, quality=101)

        # Test with negative quality
        with pytest.raises((ValueError, ImageProcessingError, TypeError)):
            self.processor.convert_to_web_display_jpeg(test_image_data, quality=-1)

    def test_convert_to_web_display_jpeg_large_image(self):
        """Test conversion with very large images."""
        # Create a large test image
        large_image_data = self.create_test_image("JPEG", (4000, 3000))

        result = self.processor.convert_to_web_display_jpeg(large_image_data)

        # Verify result
        assert isinstance(result, bytes)
        assert len(result) > 0

        # Verify dimensions are preserved
        with Image.open(io.BytesIO(result)) as converted_image:
            assert converted_image.size == (4000, 3000)
            assert converted_image.format == "JPEG"


class TestHEICFileDetection:
    """Test HEIC file format detection logic."""

    def test_is_heic_file_with_heic_extensions(self):
        """Test detection of .heic files."""
        assert is_heic_file("photo.heic") is True
        assert is_heic_file("IMG_1234.HEIC") is True
        assert is_heic_file("vacation.Heic") is True
        assert is_heic_file("portrait.HeiC") is True

    def test_is_heic_file_with_heif_extensions(self):
        """Test detection of .heif files."""
        assert is_heic_file("photo.heif") is True
        assert is_heic_file("IMG_5678.HEIF") is True
        assert is_heic_file("portrait.Heif") is True
        assert is_heic_file("landscape.HeiF") is True

    def test_is_heic_file_with_non_heic_extensions(self):
        """Test that non-HEIC files are correctly identified."""
        assert is_heic_file("photo.jpg") is False
        assert is_heic_file("image.jpeg") is False
        assert is_heic_file("picture.png") is False
        assert is_heic_file("document.pdf") is False
        assert is_heic_file("video.mp4") is False
        assert is_heic_file("archive.zip") is False

    def test_is_heic_file_edge_cases(self):
        """Test edge cases for HEIC file detection."""
        # Empty or None filenames
        assert is_heic_file("") is False
        assert is_heic_file(None) is False

        # Files without extensions
        assert is_heic_file("filename") is False
        assert is_heic_file("no_extension") is False

        # Files with multiple dots
        assert is_heic_file("my.photo.heic") is True
        assert is_heic_file("backup.2024.01.15.heif") is True
        assert is_heic_file("test.file.jpg") is False

    def test_is_heic_file_case_insensitive(self):
        """Test that HEIC detection is case insensitive."""
        test_cases = [
            "photo.heic",
            "photo.HEIC",
            "photo.Heic",
            "photo.HeiC",
            "photo.heif",
            "photo.HEIF",
            "photo.Heif",
            "photo.HeiF",
        ]

        for filename in test_cases:
            assert is_heic_file(filename) is True, f"Failed for {filename}"


class TestHEICWebDisplayIntegration:
    """Test integration of HEIC web display functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = ImageProcessor()

    @patch("src.imgstream.ui.pages.gallery.get_storage_service")
    @patch("src.imgstream.ui.pages.gallery.get_image_processor")
    def test_convert_heic_to_web_display_success(self, mock_get_processor, mock_get_storage):
        """Test successful HEIC to web display conversion."""
        from src.imgstream.ui.pages.gallery import convert_heic_to_web_display

        # Mock photo data
        photo = {"id": "test_photo_123", "original_path": "photos/test.heic", "filename": "test.heic"}

        # Mock services
        mock_storage = Mock()
        mock_processor = Mock()
        mock_get_storage.return_value = mock_storage
        mock_get_processor.return_value = mock_processor

        # Mock storage service to return test image data
        test_image_data = b"fake_heic_data"
        mock_storage.download_file.return_value = test_image_data

        # Mock processor to return converted JPEG data
        converted_data = b"fake_jpeg_data"
        mock_processor.convert_to_web_display_jpeg.return_value = converted_data

        # Test conversion
        result = convert_heic_to_web_display(photo)

        # Verify calls
        mock_storage.download_file.assert_called_once_with("photos/test.heic")
        mock_processor.convert_to_web_display_jpeg.assert_called_once_with(test_image_data)

        # Verify result
        assert result == converted_data

    @patch("src.imgstream.ui.pages.gallery.get_storage_service")
    def test_convert_heic_to_web_display_storage_failure(self, mock_get_storage):
        """Test HEIC conversion when storage download fails."""
        from src.imgstream.ui.pages.gallery import convert_heic_to_web_display

        photo = {"id": "test_photo_123", "original_path": "photos/test.heic", "filename": "test.heic"}

        # Mock storage service to return None (download failure)
        mock_storage = Mock()
        mock_storage.download_file.return_value = None
        mock_get_storage.return_value = mock_storage

        # Test conversion
        result = convert_heic_to_web_display(photo)

        # Should return None on storage failure
        assert result is None

    @patch("src.imgstream.ui.pages.gallery.get_storage_service")
    @patch("src.imgstream.ui.pages.gallery.get_image_processor")
    def test_convert_heic_to_web_display_conversion_failure(self, mock_get_processor, mock_get_storage):
        """Test HEIC conversion when image processing fails."""
        from src.imgstream.ui.pages.gallery import convert_heic_to_web_display

        photo = {"id": "test_photo_123", "original_path": "photos/test.heic", "filename": "test.heic"}

        # Mock services
        mock_storage = Mock()
        mock_processor = Mock()
        mock_get_storage.return_value = mock_storage
        mock_get_processor.return_value = mock_processor

        # Mock storage to return data but processor to raise exception
        mock_storage.download_file.return_value = b"fake_heic_data"
        mock_processor.convert_to_web_display_jpeg.side_effect = ImageProcessingError("Conversion failed")

        # Test conversion
        result = convert_heic_to_web_display(photo)

        # Should return None on conversion failure
        assert result is None

    def test_convert_heic_to_web_display_missing_path(self):
        """Test HEIC conversion with missing original path."""
        from src.imgstream.ui.pages.gallery import convert_heic_to_web_display

        photo = {
            "id": "test_photo_123",
            "filename": "test.heic",
            # Missing original_path
        }

        # Test conversion
        result = convert_heic_to_web_display(photo)

        # Should return None when original_path is missing
        assert result is None
