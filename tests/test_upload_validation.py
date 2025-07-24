"""Tests for upload file validation functionality."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from imgstream.main import format_file_size, get_file_size_limits, validate_uploaded_files
from imgstream.services.image_processor import ImageProcessingError


class TestFileValidation:
    """Test file validation functionality."""

    def test_validate_uploaded_files_empty_list(self):
        """Test validation with empty file list."""
        valid_files, errors = validate_uploaded_files([])
        assert valid_files == []
        assert errors == []

    @patch("imgstream.main.ImageProcessor")
    def test_validate_uploaded_files_valid_file(self, mock_processor_class):
        """Test validation with valid file."""
        # Mock ImageProcessor
        mock_processor = MagicMock()
        mock_processor.is_supported_format.return_value = True
        mock_processor.validate_file_size.return_value = None
        mock_processor_class.return_value = mock_processor

        # Mock uploaded file
        mock_file = MagicMock()
        mock_file.name = "test.jpg"
        mock_file.read.return_value = b"fake_image_data"

        valid_files, errors = validate_uploaded_files([mock_file])

        assert len(valid_files) == 1
        assert len(errors) == 0
        assert valid_files[0]["filename"] == "test.jpg"
        assert valid_files[0]["size"] == len(b"fake_image_data")

    @patch("imgstream.main.ImageProcessor")
    def test_validate_uploaded_files_unsupported_format(self, mock_processor_class):
        """Test validation with unsupported file format."""
        # Mock ImageProcessor
        mock_processor = MagicMock()
        mock_processor.is_supported_format.return_value = False
        mock_processor_class.return_value = mock_processor

        # Mock uploaded file
        mock_file = MagicMock()
        mock_file.name = "test.png"
        mock_file.read.return_value = b"fake_image_data"

        valid_files, errors = validate_uploaded_files([mock_file])

        assert len(valid_files) == 0
        assert len(errors) == 1
        assert errors[0]["filename"] == "test.png"
        assert "Unsupported file format" in errors[0]["error"]

    @patch("imgstream.main.ImageProcessor")
    def test_validate_uploaded_files_size_error(self, mock_processor_class):
        """Test validation with file size error."""
        # Mock ImageProcessor
        mock_processor = MagicMock()
        mock_processor.is_supported_format.return_value = True
        mock_processor.validate_file_size.side_effect = ImageProcessingError("File too large")
        mock_processor_class.return_value = mock_processor

        # Mock uploaded file
        mock_file = MagicMock()
        mock_file.name = "large_file.jpg"
        mock_file.read.return_value = b"fake_image_data"

        valid_files, errors = validate_uploaded_files([mock_file])

        assert len(valid_files) == 0
        assert len(errors) == 1
        assert errors[0]["filename"] == "large_file.jpg"
        assert "Validation failed" in errors[0]["error"]

    @patch("imgstream.main.ImageProcessor")
    def test_validate_uploaded_files_mixed_results(self, mock_processor_class):
        """Test validation with mix of valid and invalid files."""
        # Mock ImageProcessor
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        # Mock uploaded files
        valid_file = MagicMock()
        valid_file.name = "valid.jpg"
        valid_file.read.return_value = b"valid_data"

        invalid_file = MagicMock()
        invalid_file.name = "invalid.png"
        invalid_file.read.return_value = b"invalid_data"

        # Configure mock behavior
        def mock_is_supported(filename):
            return filename.endswith(".jpg")

        mock_processor.is_supported_format.side_effect = mock_is_supported
        mock_processor.validate_file_size.return_value = None

        valid_files, errors = validate_uploaded_files([valid_file, invalid_file])

        assert len(valid_files) == 1
        assert len(errors) == 1
        assert valid_files[0]["filename"] == "valid.jpg"
        assert errors[0]["filename"] == "invalid.png"


class TestFileUtilities:
    """Test file utility functions."""

    def test_format_file_size_bytes(self):
        """Test file size formatting for bytes."""
        assert format_file_size(500) == "500 B"
        assert format_file_size(1023) == "1023 B"

    def test_format_file_size_kilobytes(self):
        """Test file size formatting for kilobytes."""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"
        assert format_file_size(1024 * 1023) == "1023.0 KB"

    def test_format_file_size_megabytes(self):
        """Test file size formatting for megabytes."""
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(1024 * 1024 * 2.5) == "2.5 MB"
        assert format_file_size(1024 * 1024 * 50) == "50.0 MB"

    @patch("imgstream.main.ImageProcessor")
    def test_get_file_size_limits(self, mock_processor_class):
        """Test getting file size limits."""
        mock_processor = MagicMock()
        mock_processor.MIN_FILE_SIZE = 100
        mock_processor.MAX_FILE_SIZE = 50 * 1024 * 1024
        mock_processor_class.return_value = mock_processor

        min_size, max_size = get_file_size_limits()

        assert min_size == 100
        assert max_size == 50 * 1024 * 1024


class TestUploadPageIntegration:
    """Test upload page integration."""

    def test_upload_page_functions_exist(self):
        """Test that upload page functions exist and are callable."""
        from imgstream.main import format_file_size, render_upload_page, validate_uploaded_files

        assert callable(render_upload_page)
        assert callable(validate_uploaded_files)
        assert callable(format_file_size)
