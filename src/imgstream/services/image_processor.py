"""Image processing service for imgstream application."""

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageOps

from imgstream.ui.handlers.error import ImageProcessingError, ValidationError
from ..logging_config import get_logger, log_error, log_performance

try:
    from pillow_heif import register_heif_opener  # type: ignore[import-untyped]

    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

logger = get_logger(__name__)


# Keep backward compatibility alias
UnsupportedFormatError = ValidationError


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
        # File size limits (in bytes) - configurable via environment variables
        self.MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # Default: 50MB
        self.MIN_FILE_SIZE = int(os.getenv("MIN_FILE_SIZE", 100))  # Default: 100 bytes

        # Thumbnail settings - configurable via environment variables
        self.DEFAULT_THUMBNAIL_SIZE = int(os.getenv("THUMBNAIL_MAX_SIZE", 300))  # Default: 300px
        self.DEFAULT_THUMBNAIL_QUALITY = int(os.getenv("THUMBNAIL_QUALITY", 85))  # Default: 85

        if not HEIF_AVAILABLE:
            logger.warning(
                "heif_support_unavailable",
                message="Install pillow-heif for HEIC support",
                supported_formats=list(self.SUPPORTED_FORMATS - {".heic", ".heif"}),
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
                if not HEIF_AVAILABLE:
                    logger.warning(
                        "heic_format_unsupported",
                        filename=filename,
                        extension=file_extension,
                        install_command="pip install pillow-heif",
                    )
                return HEIF_AVAILABLE
            return True

        return False

    def validate_file_size(self, image_data: bytes, filename: str) -> None:
        """
        Validate that the file size is within acceptable limits.

        Args:
            image_data: Raw image data as bytes
            filename: Name of the image file

        Raises:
            ImageProcessingError: If file size is outside acceptable limits
        """
        file_size = len(image_data)

        if file_size < self.MIN_FILE_SIZE:
            logger.warning("file_size_too_small", filename=filename, file_size=file_size, min_size=self.MIN_FILE_SIZE)
            raise ValidationError(
                f"File '{filename}' is too small ({file_size} bytes). Minimum size: {self.MIN_FILE_SIZE} bytes",
                code="file_too_small",
                user_message=f"ファイル '{filename}' が小さすぎます。最小サイズ: {self.MIN_FILE_SIZE} バイト",
                details={
                    "filename": filename,
                    "file_size": file_size,
                    "min_size": self.MIN_FILE_SIZE,
                },
            )

        if file_size > self.MAX_FILE_SIZE:
            max_size_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            current_size_mb = file_size / (1024 * 1024)
            logger.warning(
                "file_size_too_large",
                filename=filename,
                file_size=file_size,
                file_size_mb=current_size_mb,
                max_size=self.MAX_FILE_SIZE,
                max_size_mb=max_size_mb,
            )
            raise ValidationError(
                f"File '{filename}' is too large ({current_size_mb:.1f}MB). Maximum size: {max_size_mb:.0f}MB",
                code="file_too_large",
                user_message=f"ファイル '{filename}' が大きすぎます。最大サイズ: {max_size_mb:.0f}MB",
                details={
                    "filename": filename,
                    "file_size": file_size,
                    "file_size_mb": current_size_mb,
                    "max_size": self.MAX_FILE_SIZE,
                    "max_size_mb": max_size_mb,
                },
            )

        logger.debug("file_size_valid", filename=filename, file_size=file_size)

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
                    logger.debug("exif_data_not_found")
                    return None

                # Try to extract date from EXIF tags in priority order
                for tag_name in self.EXIF_DATE_TAGS:
                    date_value = self._get_exif_date_by_name(dict(exif_data), tag_name)
                    if date_value:
                        logger.debug("exif_date_extracted", tag_name=tag_name, date_value=date_value.isoformat())
                        return date_value

                logger.debug("exif_date_not_found", tags_checked=self.EXIF_DATE_TAGS)
                return None

        except Exception as e:
            log_error(e, {"operation": "extract_exif_date"})
            return None

    def extract_created_at(self, image_data: bytes) -> datetime:
        """
        Extract creation date from image, with fallback to current time.

        Args:
            image_data: Raw image data as bytes

        Returns:
            datetime: Creation date from EXIF if available, otherwise current time
        """
        # Try to extract from EXIF first
        exif_date = self.extract_exif_date(image_data)
        if exif_date:
            return exif_date

        # Fallback to current time if no EXIF date found
        logger.info("exif_date_fallback", fallback_time=datetime.now().isoformat())
        return datetime.now()

    def _get_exif_date_by_name(self, exif_data: dict[Any, Any], tag_name: str) -> datetime | None:
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
            logger.debug("exif_date_parse_failed", tag_name=tag_name, date_string=date_string, error=str(e))
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
        start_time = datetime.now()
        try:
            with Image.open(io.BytesIO(image_data)) as image:
                info = {
                    "format": image.format,
                    "mode": image.mode,
                    "size": image.size,
                    "width": image.width,
                    "height": image.height,
                    "has_exif": bool(image.getexif()),
                }

                duration = (datetime.now() - start_time).total_seconds()
                log_performance(
                    "get_image_info",
                    duration,
                    format=info["format"],
                    width=info["width"],
                    height=info["height"],
                    file_size=len(image_data),
                )

                return info
        except Exception as e:
            log_error(e, {"operation": "get_image_info", "file_size": len(image_data)})
            raise ImageProcessingError(
                f"Failed to get image info: {e}",
                code="image_info_failed",
                user_message="画像情報の取得に失敗しました。",
                details={
                    "file_size": len(image_data),
                    "operation": "get_image_info",
                },
                original_exception=e,
            ) from e

    def validate_image(self, image_data: bytes, filename: str) -> None:
        """
        Validate that the image data is valid and supported.

        Args:
            image_data: Raw image data as bytes
            filename: Name of the image file

        Raises:
            UnsupportedFormatError: If format is not supported
            ImageProcessingError: If image is invalid, corrupted, or size is invalid
        """
        start_time = datetime.now()

        # Check file size first
        self.validate_file_size(image_data, filename)

        # Check file extension
        if not self.is_supported_format(filename):
            supported_formats = ", ".join(self.SUPPORTED_FORMATS)
            logger.error(
                "unsupported_format",
                filename=filename,
                extension=Path(filename).suffix.lower(),
                supported_formats=list(self.SUPPORTED_FORMATS),
            )
            raise ValidationError(
                f"Unsupported format for file '{filename}'. Supported formats: {supported_formats}",
                code="unsupported_format",
                user_message=(
                    f"ファイル '{filename}' の形式はサポートされていません。"
                    f"対応形式: {', '.join(self.SUPPORTED_FORMATS)}"
                ),
                details={
                    "filename": filename,
                    "extension": Path(filename).suffix.lower(),
                    "supported_formats": list(self.SUPPORTED_FORMATS),
                },
            )

        # Try to open and validate the image
        try:
            with Image.open(io.BytesIO(image_data)) as image:
                # Verify the image by loading it
                image.verify()

                # Additional format-specific validation
                format_lower = image.format.lower() if image.format else ""
                if format_lower not in ["jpeg", "heic"]:
                    logger.error(
                        "invalid_detected_format",
                        filename=filename,
                        detected_format=image.format,
                        supported_formats=["JPEG", "HEIC"],
                    )
                    raise ValidationError(
                        f"Detected format '{image.format}' is not supported. Supported formats: JPEG, HEIC",
                        code="invalid_detected_format",
                        user_message=f"ファイル '{filename}' の形式 '{image.format}' はサポートされていません。",
                        details={
                            "filename": filename,
                            "detected_format": image.format,
                            "supported_formats": ["JPEG", "HEIC"],
                        },
                    )

            duration = (datetime.now() - start_time).total_seconds()
            log_performance(
                "validate_image", duration, filename=filename, file_size=len(image_data), format=format_lower
            )

            logger.debug("image_validation_success", filename=filename, format=format_lower, file_size=len(image_data))

        except ValidationError:
            raise
        except Exception as e:
            log_error(e, {"operation": "validate_image", "filename": filename, "file_size": len(image_data)})
            raise ImageProcessingError(
                f"Invalid or corrupted image file '{filename}': {e}",
                code="image_validation_failed",
                user_message=f"ファイル '{filename}' が破損しているか、無効な画像ファイルです。",
                details={
                    "filename": filename,
                    "file_size": len(image_data),
                    "operation": "validate_image",
                },
                original_exception=e,
            ) from e

    def get_validation_info(self, image_data: bytes, filename: str) -> dict:
        """
        Get detailed validation information about an image file.

        Args:
            image_data: Raw image data as bytes
            filename: Name of the image file

        Returns:
            dict: Validation information including errors and warnings
        """
        validation_info: dict[str, Any] = {
            "filename": filename,
            "file_size": len(image_data),
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "format_supported": False,
            "size_valid": False,
            "image_readable": False,
        }

        try:
            # Check file size
            self.validate_file_size(image_data, filename)
            validation_info["size_valid"] = True
        except ImageProcessingError as e:
            validation_info["is_valid"] = False
            validation_info["errors"].append(str(e))

        # Check format support
        if self.is_supported_format(filename):
            validation_info["format_supported"] = True
        else:
            validation_info["is_valid"] = False
            supported_formats = ", ".join(self.SUPPORTED_FORMATS)
            validation_info["errors"].append(f"Unsupported format. Supported formats: {supported_formats}")

        # Try to read the image
        try:
            with Image.open(io.BytesIO(image_data)) as image:
                image.verify()
                validation_info["image_readable"] = True

                # Check actual format vs extension
                if image.format:
                    detected_format = image.format.lower()
                    if detected_format not in ["jpeg", "heic"]:
                        validation_info["is_valid"] = False
                        validation_info["errors"].append(f"Detected format '{image.format}' is not supported")
                    elif detected_format == "heic" and not HEIF_AVAILABLE:
                        validation_info["is_valid"] = False
                        validation_info["errors"].append("HEIC format requires pillow-heif library")

        except Exception as e:
            validation_info["is_valid"] = False
            validation_info["errors"].append(f"Cannot read image: {e}")

        return validation_info

    def generate_thumbnail(
        self, image_data: bytes, max_size: tuple[int, int] | None = None, quality: int | None = None
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
        start_time = datetime.now()

        # Use environment variable defaults if not specified
        if max_size is None:
            max_size = (self.DEFAULT_THUMBNAIL_SIZE, self.DEFAULT_THUMBNAIL_SIZE)
        if quality is None:
            quality = self.DEFAULT_THUMBNAIL_QUALITY

        try:
            with Image.open(io.BytesIO(image_data)) as image:
                # Apply EXIF orientation to correct rotation
                image = ImageOps.exif_transpose(image)

                original_size = image.size
                original_mode = image.mode

                # Convert to RGB if necessary (for HEIC and other formats)
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")

                # Calculate thumbnail size while preserving aspect ratio
                thumbnail_size = self._calculate_thumbnail_size(original_size, max_size)

                # Resize image to exact thumbnail size (can upscale or downscale)
                resized_image = image.resize(thumbnail_size, Image.Resampling.LANCZOS)

                # Save as JPEG to bytes
                thumbnail_buffer = io.BytesIO()
                resized_image.save(thumbnail_buffer, format="JPEG", quality=quality, optimize=True)

                thumbnail_data = thumbnail_buffer.getvalue()

                duration = (datetime.now() - start_time).total_seconds()
                log_performance(
                    "generate_thumbnail",
                    duration,
                    original_size=original_size,
                    thumbnail_size=thumbnail_size,
                    original_file_size=len(image_data),
                    thumbnail_file_size=len(thumbnail_data),
                    quality=quality,
                    compression_ratio=len(image_data) / len(thumbnail_data),
                )

                logger.debug(
                    "thumbnail_generated",
                    original_size=original_size,
                    thumbnail_size=thumbnail_size,
                    original_mode=original_mode,
                    original_file_size=len(image_data),
                    thumbnail_file_size=len(thumbnail_data),
                    quality=quality,
                )

                return thumbnail_data

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "generate_thumbnail",
                    "original_file_size": len(image_data),
                    "max_size": max_size,
                    "quality": quality,
                },
            )
            raise ImageProcessingError(
                f"Failed to generate thumbnail: {e}",
                code="thumbnail_generation_failed",
                user_message="サムネイル画像の生成に失敗しました。",
                details={
                    "original_file_size": len(image_data),
                    "max_size": max_size,
                    "quality": quality,
                    "operation": "generate_thumbnail",
                },
                original_exception=e,
            ) from e

    def _calculate_thumbnail_size(self, original_size: tuple[int, int], max_size: tuple[int, int]) -> tuple[int, int]:
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

    def convert_to_web_display_jpeg(self, image_data: bytes, quality: int = 90) -> bytes:
        """
        Convert image to high-quality JPEG for web display, maintaining original dimensions.

        Args:
            image_data: Raw image data as bytes
            quality: JPEG quality (1-100, higher is better quality)

        Returns:
            bytes: Converted image data as JPEG bytes

        Raises:
            ImageProcessingError: If conversion fails
        """
        start_time = datetime.now()

        try:
            with Image.open(io.BytesIO(image_data)) as image:
                # Apply EXIF orientation to correct rotation
                image = ImageOps.exif_transpose(image)

                original_size = image.size
                original_mode = image.mode
                original_format = image.format

                # Convert to RGB if necessary (for HEIC and other formats)
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")

                # Save as JPEG to bytes with original dimensions
                jpeg_buffer = io.BytesIO()
                image.save(jpeg_buffer, format="JPEG", quality=quality, optimize=True)

                jpeg_data = jpeg_buffer.getvalue()

                duration = (datetime.now() - start_time).total_seconds()
                log_performance(
                    "convert_to_web_display_jpeg",
                    duration,
                    original_size=original_size,
                    original_format=original_format,
                    original_file_size=len(image_data),
                    jpeg_file_size=len(jpeg_data),
                    quality=quality,
                    compression_ratio=len(image_data) / len(jpeg_data),
                )

                logger.debug(
                    "web_display_jpeg_converted",
                    original_size=original_size,
                    original_mode=original_mode,
                    original_format=original_format,
                    original_file_size=len(image_data),
                    jpeg_file_size=len(jpeg_data),
                    quality=quality,
                )

                return jpeg_data

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "convert_to_web_display_jpeg",
                    "original_file_size": len(image_data),
                    "quality": quality,
                },
            )
            raise ImageProcessingError(
                f"Failed to convert image to web display JPEG: {e}",
                code="web_display_conversion_failed",
                user_message="画像のWeb表示用JPEG変換に失敗しました。",
                details={
                    "original_file_size": len(image_data),
                    "quality": quality,
                    "operation": "convert_to_web_display_jpeg",
                },
                original_exception=e,
            ) from e

    def generate_thumbnail_with_metadata(
        self, image_data: bytes, filename: str, max_size: tuple[int, int] | None = None, quality: int | None = None
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
        # Use environment variable defaults if not specified
        if max_size is None:
            max_size = (self.DEFAULT_THUMBNAIL_SIZE, self.DEFAULT_THUMBNAIL_SIZE)
        if quality is None:
            quality = self.DEFAULT_THUMBNAIL_QUALITY

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
            created_at = self.extract_exif_date(image_data)

            result = {
                "original": {
                    "filename": filename,
                    "file_size": len(image_data),
                    "format": original_info["format"],
                    "width": original_info["width"],
                    "height": original_info["height"],
                    "has_exif": original_info["has_exif"],
                    "created_at": created_at,
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
                "thumbnail_with_metadata_generated",
                filename=filename,
                original_dimensions=f"{original_info['width']}x{original_info['height']}",
                thumbnail_dimensions=f"{thumbnail_info['width']}x{thumbnail_info['height']}",
                original_size=len(image_data),
                thumbnail_size=len(thumbnail_data),
                format=original_info["format"],
                has_exif=original_info["has_exif"],
                created_at=created_at.isoformat() if created_at else None,
            )

            return result

        except (ValidationError, ImageProcessingError):
            raise
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to generate thumbnail with metadata for '{filename}': {e}",
                code="thumbnail_with_metadata_failed",
                user_message=f"ファイル '{filename}' のサムネイル生成に失敗しました。",
                details={
                    "filename": filename,
                    "operation": "generate_thumbnail_with_metadata",
                },
                original_exception=e,
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
            created_at = self.extract_exif_date(image_data)

            # Compile metadata
            metadata = {
                "filename": filename,
                "file_size": len(image_data),
                "format": image_info["format"],
                "mode": image_info["mode"],
                "width": image_info["width"],
                "height": image_info["height"],
                "has_exif": image_info["has_exif"],
                "created_at": created_at,
                "processed_at": datetime.now(),
            }

            logger.info(
                "metadata_extracted",
                filename=filename,
                dimensions=f"{image_info['width']}x{image_info['height']}",
                format=image_info["format"],
                mode=image_info["mode"],
                file_size=len(image_data),
                has_exif=image_info["has_exif"],
                created_at=created_at.isoformat() if created_at else None,
            )

            return metadata

        except (ValidationError, ImageProcessingError):
            raise
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to extract metadata from '{filename}': {e}",
                code="metadata_extraction_failed",
                user_message=f"ファイル '{filename}' のメタデータ抽出に失敗しました。",
                details={
                    "filename": filename,
                    "operation": "extract_metadata",
                },
                original_exception=e,
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
