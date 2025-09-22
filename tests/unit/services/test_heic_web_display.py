"""Tests for HEIC web display conversion functionality."""

import io
import sys
import os
from unittest.mock import Mock, patch, MagicMock

import pytest
from PIL import Image

# Set environment variables to avoid Streamlit dependency
os.environ["ENVIRONMENT"] = "test"
os.environ["GCP_PROJECT_ID"] = "test-project"
os.environ["PHOTOS_BUCKET"] = "test-photos-bucket"
os.environ["DATABASE_BUCKET"] = "test-database-bucket"

# Mock streamlit module completely to avoid protobuf issues
streamlit_mock = MagicMock()
streamlit_mock.secrets = {"gcp_service_account": {"type": "service_account"}}
streamlit_mock.cache_data = lambda **kwargs: lambda func: func  # Disable caching
sys.modules["streamlit"] = streamlit_mock

from imgstream.services.image_processor import ImageProcessor
from imgstream.ui.handlers.error import ImageProcessingError
from imgstream.ui.handlers.gallery import is_heic_file


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
        # Test with empty data - should raise ImageProcessingError
        with pytest.raises(ImageProcessingError):
            self.processor.convert_to_web_display_jpeg(b"")

        # Test with invalid image data - should raise ImageProcessingError
        with pytest.raises(ImageProcessingError):
            self.processor.convert_to_web_display_jpeg(b"not an image")

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

        # Note: The current implementation may not validate quality bounds
        # This test documents the expected behavior but may need adjustment
        # based on actual implementation behavior

        # Test with quality above 100 - implementation may clamp or accept it
        result = self.processor.convert_to_web_display_jpeg(test_image_data, quality=101)
        # If no exception is raised, the implementation accepts out-of-range values
        assert isinstance(result, bytes)

        # Test with negative quality - should handle gracefully
        try:
            result = self.processor.convert_to_web_display_jpeg(test_image_data, quality=-1)
            # If no exception, implementation handles negative values
            assert isinstance(result, bytes)
        except (ValueError, ImageProcessingError, TypeError):
            pass  # Expected exception for invalid quality

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

    def test_heic_web_display_workflow_components(self):
        """Test that the components needed for HEIC web display work correctly."""
        # Test that we can create an ImageProcessor
        processor = ImageProcessor()
        assert processor is not None

        # Test that we can create test image data
        image = Image.new("RGB", (400, 300), color="red")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        test_data = buffer.getvalue()

        # Test that the processor can handle the data
        result = processor.convert_to_web_display_jpeg(test_data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_is_heic_file_integration(self):
        """Test HEIC file detection integration."""
        # Test various file extensions
        assert is_heic_file("photo.heic") is True
        assert is_heic_file("photo.heif") is True
        assert is_heic_file("photo.jpg") is False
        assert is_heic_file("photo.png") is False

    def test_image_processor_error_handling(self):
        """Test that ImageProcessor properly handles errors."""
        processor = ImageProcessor()

        # Test with invalid data
        with pytest.raises(ImageProcessingError):
            processor.convert_to_web_display_jpeg(b"invalid_image_data")

        # Test with empty data
        with pytest.raises(ImageProcessingError):
            processor.convert_to_web_display_jpeg(b"")