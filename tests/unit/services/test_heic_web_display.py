"""Tests for HEIC web display conversion functionality."""

import io

import pytest
from PIL import Image

from src.imgstream.services.image_processor import ImageProcessor
from src.imgstream.ui.handlers.error import ImageProcessingError


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
            (1600, 900),   # 16:9 different size
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
