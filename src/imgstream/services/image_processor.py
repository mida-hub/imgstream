"""Image processing service for imgstream application."""

import io
import logging
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

logger = logging.getLogger(__name__)


class ImageProcessingError(Exception):
    """Raised when image processing fails."""

    pass


class UnsupportedFormatError(Exception):
    """Raised when image format is not supported."""

    pass


class ImageProcessor:
    """Service for processing images and extracting metadata."""

    # Supported image formats
    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".heic", ".heif"}

    # EXIF date tags in priority order
    EXIF_DATE_TAGS = [
        "DateTimeOriginal",  # When photo was taken
        "DateTime",  # When file was modified
        "DateTimeDigitized",  # When photo was digitized
    ]

    def __init__(self) -> None:
        """Initialize the image processor."""
        if not HEIF_AVAILABLE:
            logger.warning(
                "HEIF support not available. Install pillow-heif for HEIC support."
            )

    def is_supported_format(self, filename: str) -> bool:
        """
        Check if the image format is supported.

        Args:
            filename: Name of the image file

        Returns:
            bool: True if format is supported, False otherwise
        """
        file_extension = Path(filename).suffix.lower()

        if file_extension in self.SUPPORTED_FORMATS:
            # Check HEIC/HEIF support specifically
            if file_extension in {".heic", ".heif"}:
                return HEIF_AVAILABLE
            return True

        return False

    def extract_exif_date(self, image_data: bytes) -> datetime | None:
        """
        Extract creation date from EXIF data.

        Args:
            image_data: Raw image data as bytes

        Returns:
            datetime: Creation date if found, None otherwise
        """
        try:
            with Image.open(io.BytesIO(image_data)) as image:
                exif_data = image.getexif()

                if not exif_data:
                    logger.debug("No EXIF data found in image")
                    return None

                # Try to extract date from EXIF tags in priority order
                for tag_name in self.EXIF_DATE_TAGS:
                    date_value = self._get_exif_date_by_name(exif_data, tag_name)
                    if date_value:
                        logger.debug(
                            f"Found date from EXIF tag '{tag_name}': {date_value}"
                        )
                        return date_value

                logger.debug("No date information found in EXIF data")
                return None

        except Exception as e:
            logger.error(f"Failed to extract EXIF date: {e}")
            return None

    def _get_exif_date_by_name(self, exif_data: dict, tag_name: str) -> datetime | None:
        """
        Get date from EXIF data by tag name.

        Args:
            exif_data: EXIF data dictionary
            tag_name: Name of the EXIF tag

        Returns:
            datetime: Parsed date if found and valid, None otherwise
        """
        try:
            # Find the tag ID for the given tag name
            tag_id = None
            for tag, name in ExifTags.TAGS.items():
                if name == tag_name:
                    tag_id = tag
                    break

            if tag_id is None:
                return None

            # Get the date string from EXIF data
            date_string = exif_data.get(tag_id)
            if not date_string:
                return None

            # Parse the date string (format: "YYYY:MM:DD HH:MM:SS")
            return datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")

        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse date from EXIF tag '{tag_name}': {e}")
            return None

    def get_image_info(self, image_data: bytes) -> dict:
        """
        Get basic image information.

        Args:
            image_data: Raw image data as bytes

        Returns:
            dict: Image information including size, format, etc.

        Raises:
            ImageProcessingError: If image cannot be processed
        """
        try:
            with Image.open(io.BytesIO(image_data)) as image:
                return {
                    "format": image.format,
                    "mode": image.mode,
                    "size": image.size,
                    "width": image.width,
                    "height": image.height,
                    "has_exif": bool(image.getexif()),
                }
        except Exception as e:
            raise ImageProcessingError(f"Failed to get image info: {e}") from e

    def validate_image(self, image_data: bytes, filename: str) -> None:
        """
        Validate that the image data is valid and supported.

        Args:
            image_data: Raw image data as bytes
            filename: Name of the image file

        Raises:
            UnsupportedFormatError: If format is not supported
            ImageProcessingError: If image is invalid or corrupted
        """
        # Check file extension
        if not self.is_supported_format(filename):
            supported_formats = ", ".join(self.SUPPORTED_FORMATS)
            raise UnsupportedFormatError(
                f"Unsupported format for file '{filename}'. "
                f"Supported formats: {supported_formats}"
            )

        # Try to open and validate the image
        try:
            with Image.open(io.BytesIO(image_data)) as image:
                # Verify the image by loading it
                image.verify()

        except Exception as e:
            raise ImageProcessingError(
                f"Invalid or corrupted image file '{filename}': {e}"
            ) from e

    def generate_thumbnail(
        self, image_data: bytes, max_size: tuple[int, int] = (300, 300), quality: int = 85
    ) -> bytes:
        """
        Generate a thumbnail image with aspect ratio preservation.

        Args:
            image_data: Raw image data as bytes
            max_size: Maximum size as (width, height) tuple
            quality: JPEG quality (1-100, higher is better quality)

        Returns:
            bytes: Thumbnail image data as JPEG bytes

        Raises:
            ImageProcessingError: If thumbnail generation fails
        """
        try:
            with Image.open(io.BytesIO(image_data)) as image:
                # Convert to RGB if necessary (for HEIC and other formats)
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")

                # Calculate thumbnail size while preserving aspect ratio
                original_size = image.size
                thumbnail_size = self._calculate_thumbnail_size(original_size, max_size)

                # Resize image to exact thumbnail size (can upscale or downscale)
                resized_image = image.resize(thumbnail_size, Image.Resampling.LANCZOS)

                # Save as JPEG to bytes
                thumbnail_buffer = io.BytesIO()
                resized_image.save(thumbnail_buffer, format="JPEG", quality=quality, optimize=True)

                thumbnail_data = thumbnail_buffer.getvalue()

                logger.debug(
                    f"Generated thumbnail: {original_size} -> {thumbnail_size}, "
                    f"size: {len(thumbnail_data)} bytes, quality: {quality}"
                )

                return thumbnail_data

        except Exception as e:
            raise ImageProcessingError(f"Failed to generate thumbnail: {e}") from e

    def _calculate_thumbnail_size(
        self, original_size: tuple[int, int], max_size: tuple[int, int]
    ) -> tuple[int, int]:
        """
        Calculate thumbnail size while preserving aspect ratio.

        Args:
            original_size: Original image size as (width, height)
            max_size: Maximum allowed size as (width, height)

        Returns:
            tuple: Calculated thumbnail size as (width, height)
        """
        original_width, original_height = original_size
        max_width, max_height = max_size

        # Calculate scaling factors for both dimensions
        width_ratio = max_width / original_width
        height_ratio = max_height / original_height

        # Use the smaller ratio to ensure the image fits within max_size
        scale_ratio = min(width_ratio, height_ratio)

        # Calculate new dimensions
        new_width = int(original_width * scale_ratio)
        new_height = int(original_height * scale_ratio)

        return (new_width, new_height)

    def generate_thumbnail_with_metadata(
        self, image_data: bytes, filename: str, max_size: tuple[int, int] = (300, 300), quality: int = 85
    ) -> dict:
        """
        Generate thumbnail and return both thumbnail data and metadata.

        Args:
            image_data: Raw image data as bytes
            filename: Name of the image file
            max_size: Maximum thumbnail size as (width, height) tuple
            quality: JPEG quality (1-100, higher is better quality)

        Returns:
            dict: Dictionary containing thumbnail data and metadata

        Raises:
            UnsupportedFormatError: If format is not supported
            ImageProcessingError: If processing fails
        """
        # Validate the image first
        self.validate_image(image_data, filename)

        try:
            # Generate thumbnail
            thumbnail_data = self.generate_thumbnail(image_data, max_size, quality)

            # Get original image info
            original_info = self.get_image_info(image_data)

            # Get thumbnail info
            thumbnail_info = self.get_image_info(thumbnail_data)

            # Extract EXIF date from original
            creation_date = self.extract_exif_date(image_data)

            result = {
                "original": {
                    "filename": filename,
                    "file_size": len(image_data),
                    "format": original_info["format"],
                    "width": original_info["width"],
                    "height": original_info["height"],
                    "has_exif": original_info["has_exif"],
                    "creation_date": creation_date,
                },
                "thumbnail": {
                    "data": thumbnail_data,
                    "file_size": len(thumbnail_data),
                    "format": thumbnail_info["format"],
                    "width": thumbnail_info["width"],
                    "height": thumbnail_info["height"],
                    "quality": quality,
                    "max_size": max_size,
                },
                "processed_at": datetime.now(),
            }

            logger.info(
                f"Generated thumbnail for {filename}: "
                f"{original_info['width']}x{original_info['height']} -> "
                f"{thumbnail_info['width']}x{thumbnail_info['height']}, "
                f"size: {len(image_data)} -> {len(thumbnail_data)} bytes"
            )

            return result

        except (UnsupportedFormatError, ImageProcessingError):
            raise
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to generate thumbnail with metadata for '{filename}': {e}"
            ) from e

    def extract_metadata(self, image_data: bytes, filename: str) -> dict:
        """
        Extract comprehensive metadata from image.

        Args:
            image_data: Raw image data as bytes
            filename: Name of the image file

        Returns:
            dict: Extracted metadata

        Raises:
            UnsupportedFormatError: If format is not supported
            ImageProcessingError: If image processing fails
        """
        # Validate the image first
        self.validate_image(image_data, filename)

        try:
            # Get basic image info
            image_info = self.get_image_info(image_data)

            # Extract EXIF date
            creation_date = self.extract_exif_date(image_data)

            # Compile metadata
            metadata = {
                "filename": filename,
                "file_size": len(image_data),
                "format": image_info["format"],
                "mode": image_info["mode"],
                "width": image_info["width"],
                "height": image_info["height"],
                "has_exif": image_info["has_exif"],
                "creation_date": creation_date,
                "processed_at": datetime.now(),
            }

            logger.info(
                f"Extracted metadata for {filename}: "
                f"{image_info['width']}x{image_info['height']}, "
                f"format: {image_info['format']}, creation_date: {creation_date}"
            )

            return metadata

        except (UnsupportedFormatError, ImageProcessingError):
            raise
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to extract metadata from '{filename}': {e}"
            ) from e


# Global image processor instance
image_processor = ImageProcessor()


def get_image_processor() -> ImageProcessor:
    """
    Get the global image processor instance.

    Returns:
        ImageProcessor: Global image processor instance
    """
    return image_processor
