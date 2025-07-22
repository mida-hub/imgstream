"""
Services module for imgstream application.

This module contains all service classes that handle business logic:
- AuthService: Cloud IAP authentication and user management
- StorageService: Google Cloud Storage operations
- ImageProcessor: Image processing and thumbnail generation
- MetadataService: DuckDB metadata management
"""

from .auth import CloudIAPAuthService, UserInfo, get_auth_service
from .image_processor import ImageProcessor, get_image_processor, ImageProcessingError, UnsupportedFormatError

__all__ = [
    "CloudIAPAuthService",
    "UserInfo", 
    "get_auth_service",
    "ImageProcessor",
    "get_image_processor",
    "ImageProcessingError",
    "UnsupportedFormatError"
]
