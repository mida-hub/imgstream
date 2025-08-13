"""
Simple upload flow tests for E2E testing.
"""

import io

import pytest
from PIL import Image

from imgstream.ui.handlers.error import ValidationError
from src.imgstream.models.photo import PhotoMetadata
from src.imgstream.services.image_processor import ImageProcessor


class TestSimpleUpload:
    """Simple upload flow tests."""

    def create_test_image(self, width=800, height=600, image_format="JPEG"):
        """Create a test image for testing."""
        image = Image.new("RGB", (width, height), color="red")
        buffer = io.BytesIO()
        image.save(buffer, format=image_format, quality=95)
        return buffer.getvalue()

    def test_image_processor_initialization(self):
        """Test ImageProcessor initialization."""
        processor = ImageProcessor()
        assert processor is not None

    def test_supported_format_detection(self):
        """Test supported format detection."""
        processor = ImageProcessor()

        # Test supported formats
        assert processor.is_supported_format("test.jpg") is True
        assert processor.is_supported_format("test.jpeg") is True
        assert processor.is_supported_format("test.JPEG") is True
        assert processor.is_supported_format("test.heic") is True
        assert processor.is_supported_format("test.HEIC") is True

        # Test unsupported formats
        assert processor.is_supported_format("test.bmp") is False
        assert processor.is_supported_format("test.gif") is False
        assert processor.is_supported_format("test.png") is False
        assert processor.is_supported_format("test.txt") is False

    def test_metadata_extraction(self):
        """Test metadata extraction from image."""
        processor = ImageProcessor()
        test_image = self.create_test_image()

        metadata = processor.extract_metadata(test_image, "test.jpg")

        assert metadata is not None
        assert isinstance(metadata, dict)
        assert metadata["filename"] == "test.jpg"
        assert metadata["width"] == 800
        assert metadata["height"] == 600
        assert metadata["format"] == "JPEG"
        assert metadata["file_size"] > 0

    def test_thumbnail_generation(self):
        """Test thumbnail generation."""
        processor = ImageProcessor()
        test_image = self.create_test_image(1920, 1080)

        thumbnail_data = processor.generate_thumbnail(test_image)

        assert thumbnail_data is not None
        assert len(thumbnail_data) > 0
        assert len(thumbnail_data) < len(test_image)  # Thumbnail should be smaller

        # Verify thumbnail is a valid image
        thumbnail_image = Image.open(io.BytesIO(thumbnail_data))
        assert thumbnail_image.size[0] <= 300  # Max width
        assert thumbnail_image.size[1] <= 300  # Max height

    def test_large_image_processing(self):
        """Test processing of large images."""
        processor = ImageProcessor()
        large_image = self.create_test_image(4000, 3000)

        # Should handle large images
        metadata = processor.extract_metadata(large_image, "large.jpg")
        assert metadata["width"] == 4000
        assert metadata["height"] == 3000

        # Thumbnail should still be small
        thumbnail_data = processor.generate_thumbnail(large_image)
        thumbnail_image = Image.open(io.BytesIO(thumbnail_data))
        assert max(thumbnail_image.size) <= 300

    def test_small_image_processing(self):
        """Test processing of small images."""
        processor = ImageProcessor()
        small_image = self.create_test_image(100, 100)

        metadata = processor.extract_metadata(small_image, "small.jpg")
        assert metadata["width"] == 100
        assert metadata["height"] == 100

        # Thumbnail should be generated (may be upscaled to standard size)
        thumbnail_data = processor.generate_thumbnail(small_image)
        thumbnail_image = Image.open(io.BytesIO(thumbnail_data))
        assert thumbnail_image.size[0] <= 300  # Max thumbnail size
        assert thumbnail_image.size[1] <= 300  # Max thumbnail size

    def test_photo_metadata_model(self):
        """Test PhotoMetadata model."""

        metadata = PhotoMetadata.create_new(
            user_id="test-user",
            filename="test.jpg",
            original_path="original/test.jpg",
            thumbnail_path="thumbs/test.jpg",
            file_size=1024000,
            mime_type="image/jpeg",
        )

        assert metadata.filename == "test.jpg"
        assert metadata.file_size == 1024000
        assert metadata.user_id == "test-user"
        assert metadata.original_path == "original/test.jpg"
        assert metadata.thumbnail_path == "thumbs/test.jpg"
        assert metadata.mime_type == "image/jpeg"
        assert metadata.id is not None

        # Test string representation
        str_repr = str(metadata)
        assert "test.jpg" in str_repr

    def test_error_handling_invalid_image(self):
        """Test error handling for invalid image data."""
        processor = ImageProcessor()
        invalid_data = b"This is not an image"

        # Should raise an exception for invalid image data
        with pytest.raises(ValidationError):
            processor.extract_metadata(invalid_data, "invalid.jpg")

    def test_error_handling_empty_data(self):
        """Test error handling for empty data."""
        processor = ImageProcessor()
        empty_data = b""

        # Should raise an exception for empty data
        with pytest.raises(ValidationError):
            processor.extract_metadata(empty_data, "empty.jpg")

    def test_filename_validation(self):
        """Test filename validation and sanitization."""
        processor = ImageProcessor()

        # Test various filename formats
        test_cases = [
            ("normal.jpg", True),
            ("with spaces.jpg", True),
            ("with-dashes.jpg", True),
            ("with_underscores.jpg", True),
            ("UPPERCASE.JPG", True),
            ("mixed.Case.JPEG", True),
            ("no_extension", False),
            ("wrong.extension.txt", False),
            ("", False),
        ]

        for filename, expected in test_cases:
            result = processor.is_supported_format(filename)
            assert result == expected, f"Failed for filename: {filename}"
