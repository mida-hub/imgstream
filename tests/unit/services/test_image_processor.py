"""
Unit tests for image processing service.
"""

import pytest
import io
from datetime import datetime
from unittest.mock import patch, MagicMock
from PIL import Image

from src.imgstream.services.image_processor import (
    ImageProcessor,
    ImageProcessingError,
    UnsupportedFormatError,
    get_image_processor
)


class TestImageProcessor:
    """Test cases for ImageProcessor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = ImageProcessor()

    def create_test_image(self, format_type='JPEG', size=(100, 100), mode='RGB') -> bytes:
        """Create a test image in memory."""
        image = Image.new(mode, size, color='red')
        buffer = io.BytesIO()
        image.save(buffer, format=format_type)
        return buffer.getvalue()

    def test_is_supported_format_jpeg(self):
        """Test supported format check for JPEG."""
        assert self.processor.is_supported_format('test.jpg') is True
        assert self.processor.is_supported_format('test.jpeg') is True
        assert self.processor.is_supported_format('TEST.JPG') is True

    def test_is_supported_format_heic(self):
        """Test supported format check for HEIC."""
        # Result depends on whether pillow-heif is available
        result = self.processor.is_supported_format('test.heic')
        assert isinstance(result, bool)
        
        result = self.processor.is_supported_format('test.heif')
        assert isinstance(result, bool)

    def test_is_supported_format_unsupported(self):
        """Test unsupported format check."""
        assert self.processor.is_supported_format('test.png') is False
        assert self.processor.is_supported_format('test.gif') is False
        assert self.processor.is_supported_format('test.bmp') is False
        assert self.processor.is_supported_format('test.txt') is False

    def test_get_image_info_success(self):
        """Test getting image information."""
        image_data = self.create_test_image('JPEG', (200, 150))
        
        info = self.processor.get_image_info(image_data)
        
        assert info['format'] == 'JPEG'
        assert info['mode'] == 'RGB'
        assert info['size'] == (200, 150)
        assert info['width'] == 200
        assert info['height'] == 150
        assert isinstance(info['has_exif'], bool)

    def test_get_image_info_invalid_data(self):
        """Test getting image info with invalid data."""
        invalid_data = b'not an image'
        
        with pytest.raises(ImageProcessingError, match="Failed to get image info"):
            self.processor.get_image_info(invalid_data)

    def test_validate_image_success(self):
        """Test image validation with valid image."""
        image_data = self.create_test_image('JPEG')
        
        # Should not raise exception
        self.processor.validate_image(image_data, 'test.jpg')

    def test_validate_image_unsupported_format(self):
        """Test image validation with unsupported format."""
        image_data = self.create_test_image('JPEG')
        
        with pytest.raises(UnsupportedFormatError, match="Unsupported format"):
            self.processor.validate_image(image_data, 'test.png')

    def test_validate_image_invalid_data(self):
        """Test image validation with invalid data."""
        # Create invalid data that passes size check but fails image validation
        invalid_data = b'not an image but large enough' + b'x' * 200
        
        with pytest.raises(ImageProcessingError, match="Invalid or corrupted image"):
            self.processor.validate_image(invalid_data, 'test.jpg')

    def test_extract_metadata_success(self):
        """Test metadata extraction from valid image."""
        image_data = self.create_test_image('JPEG', (300, 200))
        filename = 'test.jpg'
        
        metadata = self.processor.extract_metadata(image_data, filename)
        
        assert metadata['filename'] == filename
        assert metadata['file_size'] == len(image_data)
        assert metadata['format'] == 'JPEG'
        assert metadata['mode'] == 'RGB'
        assert metadata['width'] == 300
        assert metadata['height'] == 200
        assert isinstance(metadata['has_exif'], bool)
        assert metadata['creation_date'] is None  # No EXIF in test image
        assert isinstance(metadata['processed_at'], datetime)

    def test_extract_metadata_unsupported_format(self):
        """Test metadata extraction with unsupported format."""
        image_data = self.create_test_image('JPEG')
        
        with pytest.raises(UnsupportedFormatError):
            self.processor.extract_metadata(image_data, 'test.png')

    def test_extract_exif_date_no_exif(self):
        """Test EXIF date extraction from image without EXIF."""
        image_data = self.create_test_image('JPEG')
        
        date = self.processor.extract_exif_date(image_data)
        
        assert date is None

    @patch('src.imgstream.services.image_processor.Image.open')
    def test_extract_exif_date_with_datetime_original(self, mock_open):
        """Test EXIF date extraction with DateTimeOriginal tag."""
        # Mock image with EXIF data
        mock_image = MagicMock()
        mock_exif = {36867: '2023:12:25 14:30:45'}  # DateTimeOriginal tag
        mock_image.getexif.return_value = mock_exif
        mock_open.return_value.__enter__.return_value = mock_image
        
        image_data = b'fake_image_data'
        date = self.processor.extract_exif_date(image_data)
        
        expected_date = datetime(2023, 12, 25, 14, 30, 45)
        assert date == expected_date

    @patch('src.imgstream.services.image_processor.Image.open')
    def test_extract_exif_date_with_datetime(self, mock_open):
        """Test EXIF date extraction with DateTime tag."""
        # Mock image with EXIF data (only DateTime, no DateTimeOriginal)
        mock_image = MagicMock()
        mock_exif = {306: '2023:11:20 10:15:30'}  # DateTime tag
        mock_image.getexif.return_value = mock_exif
        mock_open.return_value.__enter__.return_value = mock_image
        
        image_data = b'fake_image_data'
        date = self.processor.extract_exif_date(image_data)
        
        expected_date = datetime(2023, 11, 20, 10, 15, 30)
        assert date == expected_date

    @patch('src.imgstream.services.image_processor.Image.open')
    def test_extract_exif_date_priority_order(self, mock_open):
        """Test EXIF date extraction priority order."""
        # Mock image with multiple date tags
        mock_image = MagicMock()
        mock_exif = {
            36867: '2023:12:25 14:30:45',  # DateTimeOriginal (highest priority)
            306: '2023:11:20 10:15:30',    # DateTime
            36868: '2023:10:15 08:00:00'   # DateTimeDigitized
        }
        mock_image.getexif.return_value = mock_exif
        mock_open.return_value.__enter__.return_value = mock_image
        
        image_data = b'fake_image_data'
        date = self.processor.extract_exif_date(image_data)
        
        # Should return DateTimeOriginal (highest priority)
        expected_date = datetime(2023, 12, 25, 14, 30, 45)
        assert date == expected_date

    @patch('src.imgstream.services.image_processor.Image.open')
    def test_extract_exif_date_invalid_format(self, mock_open):
        """Test EXIF date extraction with invalid date format."""
        # Mock image with invalid date format
        mock_image = MagicMock()
        mock_exif = {36867: 'invalid_date_format'}
        mock_image.getexif.return_value = mock_exif
        mock_open.return_value.__enter__.return_value = mock_image
        
        image_data = b'fake_image_data'
        date = self.processor.extract_exif_date(image_data)
        
        assert date is None

    @patch('src.imgstream.services.image_processor.Image.open')
    def test_extract_exif_date_exception_handling(self, mock_open):
        """Test EXIF date extraction with exception."""
        mock_open.side_effect = Exception("Image processing error")
        
        image_data = b'fake_image_data'
        date = self.processor.extract_exif_date(image_data)
        
        assert date is None

    def test_get_exif_date_by_name_success(self):
        """Test getting EXIF date by tag name."""
        exif_data = {36867: '2023:12:25 14:30:45'}  # DateTimeOriginal
        
        date = self.processor._get_exif_date_by_name(exif_data, 'DateTimeOriginal')
        
        expected_date = datetime(2023, 12, 25, 14, 30, 45)
        assert date == expected_date

    def test_get_exif_date_by_name_not_found(self):
        """Test getting EXIF date by tag name when tag not found."""
        exif_data = {}
        
        date = self.processor._get_exif_date_by_name(exif_data, 'DateTimeOriginal')
        
        assert date is None

    def test_get_exif_date_by_name_invalid_tag(self):
        """Test getting EXIF date by invalid tag name."""
        exif_data = {36867: '2023:12:25 14:30:45'}
        
        date = self.processor._get_exif_date_by_name(exif_data, 'InvalidTag')
        
        assert date is None

    def test_generate_thumbnail_success(self):
        """Test successful thumbnail generation."""
        image_data = self.create_test_image('JPEG', (600, 400))
        
        thumbnail_data = self.processor.generate_thumbnail(image_data, (300, 300))
        
        # Verify thumbnail is smaller than original
        assert len(thumbnail_data) < len(image_data)
        
        # Verify thumbnail is valid JPEG
        thumbnail_info = self.processor.get_image_info(thumbnail_data)
        assert thumbnail_info['format'] == 'JPEG'
        
        # Verify aspect ratio is preserved (600:400 = 3:2)
        # With max size 300x300, should be 300x200
        assert thumbnail_info['width'] == 300
        assert thumbnail_info['height'] == 200

    def test_generate_thumbnail_portrait(self):
        """Test thumbnail generation for portrait image."""
        image_data = self.create_test_image('JPEG', (400, 600))
        
        thumbnail_data = self.processor.generate_thumbnail(image_data, (300, 300))
        
        thumbnail_info = self.processor.get_image_info(thumbnail_data)
        
        # For portrait 400x600 (2:3 ratio), with max 300x300, should be 200x300
        assert thumbnail_info['width'] == 200
        assert thumbnail_info['height'] == 300

    def test_generate_thumbnail_square(self):
        """Test thumbnail generation for square image."""
        image_data = self.create_test_image('JPEG', (500, 500))
        
        thumbnail_data = self.processor.generate_thumbnail(image_data, (300, 300))
        
        thumbnail_info = self.processor.get_image_info(thumbnail_data)
        
        # Square image should remain square
        assert thumbnail_info['width'] == 300
        assert thumbnail_info['height'] == 300

    def test_generate_thumbnail_small_image(self):
        """Test thumbnail generation for image smaller than max size."""
        image_data = self.create_test_image('JPEG', (200, 150))
        
        thumbnail_data = self.processor.generate_thumbnail(image_data, (300, 300))
        
        thumbnail_info = self.processor.get_image_info(thumbnail_data)
        
        # Small image should be upscaled to fit max size while preserving ratio
        # 200x150 (4:3 ratio) with max 300x300 should be 300x225
        assert thumbnail_info['width'] == 300
        assert thumbnail_info['height'] == 225

    def test_generate_thumbnail_custom_size(self):
        """Test thumbnail generation with custom max size."""
        image_data = self.create_test_image('JPEG', (800, 600))
        
        thumbnail_data = self.processor.generate_thumbnail(image_data, (150, 150))
        
        thumbnail_info = self.processor.get_image_info(thumbnail_data)
        
        # 800x600 (4:3 ratio) with max 150x150 should be approximately 150x112
        # Allow for small rounding differences
        assert abs(thumbnail_info['width'] - 150) <= 1
        assert abs(thumbnail_info['height'] - 112) <= 1

    def test_generate_thumbnail_quality_setting(self):
        """Test thumbnail generation with different quality settings."""
        image_data = self.create_test_image('JPEG', (400, 400))
        
        # Generate thumbnails with different quality settings
        high_quality = self.processor.generate_thumbnail(image_data, quality=95)
        low_quality = self.processor.generate_thumbnail(image_data, quality=50)
        
        # Higher quality should result in larger file size
        assert len(high_quality) > len(low_quality)

    def test_generate_thumbnail_invalid_data(self):
        """Test thumbnail generation with invalid image data."""
        invalid_data = b'not an image'
        
        with pytest.raises(ImageProcessingError, match="Failed to generate thumbnail"):
            self.processor.generate_thumbnail(invalid_data)

    def test_calculate_thumbnail_size_landscape(self):
        """Test thumbnail size calculation for landscape image."""
        original_size = (800, 600)  # 4:3 ratio
        max_size = (300, 300)
        
        result = self.processor._calculate_thumbnail_size(original_size, max_size)
        
        # Should scale to 300x225 to preserve 4:3 ratio
        assert result == (300, 225)

    def test_calculate_thumbnail_size_portrait(self):
        """Test thumbnail size calculation for portrait image."""
        original_size = (600, 800)  # 3:4 ratio
        max_size = (300, 300)
        
        result = self.processor._calculate_thumbnail_size(original_size, max_size)
        
        # Should scale to 225x300 to preserve 3:4 ratio
        assert result == (225, 300)

    def test_calculate_thumbnail_size_square(self):
        """Test thumbnail size calculation for square image."""
        original_size = (500, 500)  # 1:1 ratio
        max_size = (300, 300)
        
        result = self.processor._calculate_thumbnail_size(original_size, max_size)
        
        # Should scale to 300x300
        assert result == (300, 300)

    def test_generate_thumbnail_with_metadata_success(self):
        """Test thumbnail generation with metadata."""
        image_data = self.create_test_image('JPEG', (600, 400))
        filename = 'test.jpg'
        
        result = self.processor.generate_thumbnail_with_metadata(image_data, filename)
        
        # Check structure
        assert 'original' in result
        assert 'thumbnail' in result
        assert 'processed_at' in result
        
        # Check original metadata
        original = result['original']
        assert original['filename'] == filename
        assert original['width'] == 600
        assert original['height'] == 400
        assert original['file_size'] == len(image_data)
        
        # Check thumbnail metadata
        thumbnail = result['thumbnail']
        assert 'data' in thumbnail
        assert thumbnail['width'] == 300
        assert thumbnail['height'] == 200
        assert thumbnail['format'] == 'JPEG'
        assert thumbnail['quality'] == 85
        assert thumbnail['max_size'] == (300, 300)
        
        # Verify thumbnail data is valid
        thumbnail_info = self.processor.get_image_info(thumbnail['data'])
        assert thumbnail_info['format'] == 'JPEG'

    def test_generate_thumbnail_with_metadata_custom_params(self):
        """Test thumbnail generation with custom parameters."""
        image_data = self.create_test_image('JPEG', (400, 400))
        filename = 'test.jpg'
        
        result = self.processor.generate_thumbnail_with_metadata(
            image_data, filename, max_size=(200, 200), quality=70
        )
        
        thumbnail = result['thumbnail']
        assert thumbnail['width'] == 200
        assert thumbnail['height'] == 200
        assert thumbnail['quality'] == 70
        assert thumbnail['max_size'] == (200, 200)

    def test_generate_thumbnail_with_metadata_unsupported_format(self):
        """Test thumbnail generation with unsupported format."""
        image_data = self.create_test_image('JPEG')
        
        with pytest.raises(UnsupportedFormatError):
            self.processor.generate_thumbnail_with_metadata(image_data, 'test.png')


class TestImageProcessorGlobal:
    """Test cases for global image processor functions."""

    def test_get_image_processor(self):
        """Test getting global image processor instance."""
        processor = get_image_processor()
        
        assert isinstance(processor, ImageProcessor)
        
        # Should return the same instance
        processor2 = get_image_processor()
        assert processor is processor2


class TestImageProcessorEdgeCases:
    """Test cases for edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = ImageProcessor()

    def test_empty_filename(self):
        """Test with empty filename."""
        assert self.processor.is_supported_format('') is False

    def test_filename_without_extension(self):
        """Test with filename without extension."""
        assert self.processor.is_supported_format('filename') is False

    def test_filename_with_multiple_dots(self):
        """Test with filename containing multiple dots."""
        assert self.processor.is_supported_format('file.name.jpg') is True
        assert self.processor.is_supported_format('file.name.png') is False

    def test_case_insensitive_extensions(self):
        """Test case insensitive extension handling."""
        assert self.processor.is_supported_format('test.JPG') is True
        assert self.processor.is_supported_format('test.Jpeg') is True
        assert self.processor.is_supported_format('test.HEIC') == self.processor.is_supported_format('test.heic')

    def test_very_small_image(self):
        """Test with very small image."""
        image_data = self.create_test_image('JPEG', (1, 1))
        
        metadata = self.processor.extract_metadata(image_data, 'tiny.jpg')
        
        assert metadata['width'] == 1
        assert metadata['height'] == 1

    def test_large_filename(self):
        """Test with very long filename."""
        long_filename = 'a' * 200 + '.jpg'
        image_data = self.create_test_image('JPEG')
        
        metadata = self.processor.extract_metadata(image_data, long_filename)
        
        assert metadata['filename'] == long_filename

    def create_test_image(self, format_type='JPEG', size=(100, 100), mode='RGB') -> bytes:
        """Create a test image in memory."""
        image = Image.new(mode, size, color='red')
        buffer = io.BytesIO()
        image.save(buffer, format=format_type)
        return buffer.getvalue()
    def test_validate_file_size_valid(self):
        """Test file size validation with valid size."""
        # Create test data within valid range
        test_data = b'x' * (10 * 1024)  # 10KB
        
        # Should not raise any exception
        self.processor.validate_file_size(test_data, 'test.jpg')
    
    def test_validate_file_size_too_small(self):
        """Test file size validation with file too small."""
        # Create test data smaller than minimum
        test_data = b'x' * 50  # 50 bytes
        
        with pytest.raises(ImageProcessingError, match="File 'test.jpg' is too small"):
            self.processor.validate_file_size(test_data, 'test.jpg')
    
    def test_validate_file_size_too_large(self):
        """Test file size validation with file too large."""
        # Mock a large file size without actually creating large data
        large_data = MagicMock()
        large_data.__len__ = MagicMock(return_value=60 * 1024 * 1024)  # 60MB
        
        with pytest.raises(ImageProcessingError, match="File 'test.jpg' is too large"):
            self.processor.validate_file_size(large_data, 'test.jpg')
    
    def test_get_validation_info_valid_image(self):
        """Test getting validation info for valid image."""
        image_data = self.create_test_image('JPEG')
        
        info = self.processor.get_validation_info(image_data, 'test.jpg')
        
        assert info['is_valid'] is True
        assert info['format_supported'] is True
        assert info['size_valid'] is True
        assert info['image_readable'] is True
        assert len(info['errors']) == 0
    
    def test_get_validation_info_invalid_size(self):
        """Test getting validation info for image with invalid size."""
        # Create small invalid data
        small_data = b'x' * 50
        
        info = self.processor.get_validation_info(small_data, 'test.jpg')
        
        assert info['is_valid'] is False
        assert info['size_valid'] is False
        assert any('too small' in error for error in info['errors'])
    
    def test_get_validation_info_unsupported_format(self):
        """Test getting validation info for unsupported format."""
        image_data = self.create_test_image('JPEG')
        
        info = self.processor.get_validation_info(image_data, 'test.png')
        
        assert info['is_valid'] is False
        assert info['format_supported'] is False
        assert any('Unsupported format' in error for error in info['errors'])
    
    def test_get_validation_info_corrupted_image(self):
        """Test getting validation info for corrupted image."""
        corrupted_data = b'not an image but large enough' + b'x' * 2000
        
        info = self.processor.get_validation_info(corrupted_data, 'test.jpg')
        
        assert info['is_valid'] is False
        assert info['image_readable'] is False
        assert any('Cannot read image' in error for error in info['errors'])

    def test_enhanced_format_validation(self):
        """Test enhanced format validation with actual format detection."""
        image_data = self.create_test_image('JPEG')
        
        # Should pass for JPEG
        self.processor.validate_image(image_data, 'test.jpg')
        
        # Test with a mocked PNG format (with sufficient size)
        with patch('PIL.Image.open') as mock_open:
            mock_image = MagicMock()
            mock_image.format = 'PNG'
            mock_open.return_value.__enter__.return_value = mock_image
            
            # Create fake data with sufficient size
            fake_png_data = b'fake_png_data' + b'x' * 200
            with pytest.raises(UnsupportedFormatError, match="Detected format 'PNG' is not supported"):
                self.processor.validate_image(fake_png_data, 'test.jpg')
    def test_environment_variable_configuration(self):
        """Test environment variable configuration for file size limits."""
        # Test with environment variables set
        with patch.dict('os.environ', {
            'MAX_FILE_SIZE': '104857600',  # 100MB
            'MIN_FILE_SIZE': '2048',       # 2KB
            'THUMBNAIL_MAX_SIZE': '400',
            'THUMBNAIL_QUALITY': '90'
        }):
            # Create new processor instance to pick up env vars
            from src.imgstream.services.image_processor import ImageProcessor
            processor = ImageProcessor()
            
            # Check that environment variables are applied
            assert processor.MAX_FILE_SIZE == 104857600  # 100MB
            assert processor.MIN_FILE_SIZE == 2048       # 2KB
            assert processor.DEFAULT_THUMBNAIL_SIZE == 400
            assert processor.DEFAULT_THUMBNAIL_QUALITY == 90
    
    def test_default_values_without_env_vars(self):
        """Test default values when environment variables are not set."""
        with patch.dict('os.environ', {}, clear=True):
            # Create new processor instance
            from src.imgstream.services.image_processor import ImageProcessor
            processor = ImageProcessor()
            
            # Check default values
            assert processor.MAX_FILE_SIZE == 50 * 1024 * 1024  # 50MB
            assert processor.MIN_FILE_SIZE == 100
            assert processor.DEFAULT_THUMBNAIL_SIZE == 300
            assert processor.DEFAULT_THUMBNAIL_QUALITY == 85
