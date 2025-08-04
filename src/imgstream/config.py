"""Configuration management for ImgStream application.

This module provides centralized configuration management using environment variables
and Streamlit secrets as fallback. Designed for simplicity and personal app usage.
"""

import os
from typing import Any

try:
    import streamlit as st

    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

from .logging_config import get_logger

logger = get_logger(__name__)


class Config:
    """Centralized configuration management using environment variables."""

    def __init__(self):
        """Initialize configuration."""
        self._cache = {}

    def get(self, key: str, default: Any = None, cast_type: type = str) -> Any:
        """Get configuration value from environment variables or Streamlit secrets.

        Args:
            key: Configuration key
            default: Default value if not found
            cast_type: Type to cast the value to (str, int, bool, float)

        Returns:
            Configuration value cast to the specified type
        """
        # Check cache first
        cache_key = f"{key}:{cast_type.__name__}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try environment variable first
        value = os.getenv(key)

        # Fallback to Streamlit secrets if available
        if value is None and STREAMLIT_AVAILABLE:
            try:
                value = st.secrets.get(key)
            except Exception:  # nosec B110
                # Ignore secrets errors (e.g., when not in Streamlit context)
                pass

        # Use default if still None
        if value is None:
            value = default

        # Cast to requested type
        if value is not None:
            try:
                if cast_type is bool:
                    # Handle boolean conversion properly
                    if isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes", "on")  # type: ignore[assignment]
                    else:
                        value = bool(value)  # type: ignore[assignment]
                elif cast_type is not str:
                    value = cast_type(value)
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to cast config value '{key}' to {cast_type.__name__}: {e}")
                value = default

        # Cache the result
        self._cache[cache_key] = value
        return value

    def get_required(self, key: str, cast_type: type = str) -> Any:
        """Get required configuration value.

        Args:
            key: Configuration key
            cast_type: Type to cast the value to

        Returns:
            Configuration value

        Raises:
            ValueError: If the required configuration is not found
        """
        value = self.get(key, cast_type=cast_type)
        if value is None:
            raise ValueError(f"Required configuration '{key}' not found")
        return value

    def is_development(self) -> bool:
        """Check if running in development mode."""
        environment = self.get("ENVIRONMENT", "development").lower()
        return environment in ["development", "dev", "local"]

    def is_production(self) -> bool:
        """Check if running in production mode."""
        environment = self.get("ENVIRONMENT", "development").lower()
        return environment in ["production", "prod"]

    def clear_cache(self):
        """Clear configuration cache."""
        self._cache.clear()


# Global configuration instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


# Convenience functions for common configuration patterns
def get_env(key: str, default: Any = None, cast_type: type = str) -> Any:
    """Get environment variable with type casting.

    Args:
        key: Environment variable name
        default: Default value if not found
        cast_type: Type to cast the value to

    Returns:
        Environment variable value cast to the specified type
    """
    return get_config().get(key, default, cast_type)


def get_required_env(key: str, cast_type: type = str) -> Any:
    """Get required environment variable.

    Args:
        key: Environment variable name
        cast_type: Type to cast the value to

    Returns:
        Environment variable value

    Raises:
        ValueError: If the required environment variable is not found
    """
    return get_config().get_required(key, cast_type)


def is_development() -> bool:
    """Check if running in development mode."""
    return get_config().is_development()


def is_production() -> bool:
    """Check if running in production mode."""
    return get_config().is_production()


# Common configuration getters
def get_project_id() -> str:
    """Get Google Cloud project ID."""
    return str(get_required_env("GOOGLE_CLOUD_PROJECT"))


def get_gcs_bucket() -> str:
    """Get GCS bucket name."""
    return str(get_required_env("GCS_BUCKET"))


def get_environment() -> str:
    """Get current environment."""
    return str(get_env("ENVIRONMENT", "development"))


def get_log_level() -> str:
    """Get log level."""
    return str(get_env("LOG_LEVEL", "INFO"))


def get_debug_mode() -> bool:
    """Get debug mode setting."""
    return get_env("DEBUG", False, bool) or is_development()
