"""
Centralized logging configuration for imgstream application.

This module provides structured logging setup using structlog with
consistent formatting, levels, and processors across all components.
"""

import logging
import os
import sys
from typing import Any

import structlog


class ColoredJSONRenderer:
    """Custom JSON renderer with optional color support for development."""

    def __init__(self, colors: bool = False):
        self.colors = colors
        self.json_renderer = structlog.processors.JSONRenderer()

    def __call__(self, logger: Any, method_name: str, event_dict: dict[str, Any]) -> str:
        """Render log entry as JSON with optional colors."""
        json_output = self.json_renderer(logger, method_name, event_dict)

        if not self.colors:
            return str(json_output)

        # Add colors for development (only if running in terminal)
        level = event_dict.get("level", "").upper()
        color_codes = {
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[35m",  # Magenta
        }

        reset_code = "\033[0m"
        color = color_codes.get(level, "")

        return f"{color}{str(json_output)}{reset_code}"


def get_log_level() -> int:
    """
    Get log level from environment variable or default to INFO.

    Returns:
        int: Log level constant from logging module
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()

    level_mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    return level_mapping.get(level_name, logging.INFO)


def is_development_environment() -> bool:
    """
    Check if running in development environment.

    Returns:
        bool: True if in development, False otherwise
    """
    return os.getenv("ENVIRONMENT", "development").lower() in ["development", "dev", "local"]


def configure_structured_logging() -> None:
    """
    Configure structured logging for the entire application.

    This function sets up structlog with appropriate processors,
    formatters, and output settings based on the environment.
    """
    # Determine environment settings
    log_level = get_log_level()
    is_dev = is_development_environment()
    use_colors = is_dev and sys.stderr.isatty()

    # Configure standard library logging
    logging.basicConfig(
        level=log_level,
        format="%(message)s",  # structlog will handle formatting
        stream=sys.stderr,
    )

    # Build processor chain
    processors: list[Any] = [
        # Filter by log level
        structlog.stdlib.filter_by_level,
        # Add logger name and level
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        # Handle positional arguments
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add stack info for errors
        structlog.processors.StackInfoRenderer(),
        # Format exception info
        structlog.processors.format_exc_info,
        # Handle unicode
        structlog.processors.UnicodeDecoder(),
    ]

    # Add development-specific processors
    if is_dev:
        # Add more detailed context in development
        processors.extend(
            [
                structlog.processors.add_log_level,
                structlog.dev.ConsoleRenderer() if not use_colors else ColoredJSONRenderer(colors=True),
            ]
        )
    else:
        # Production: use JSON for structured logging
        processors.append(structlog.processors.JSONRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Log configuration info
    logger = structlog.get_logger("imgstream.logging")
    logger.info(
        "logging_configured",
        log_level=logging.getLevelName(log_level),
        environment="development" if is_dev else "production",
        colors_enabled=use_colors,
    )


def get_logger(name: str | None = None) -> Any:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (optional, defaults to calling module)

    Returns:
        structlog.BoundLogger: Configured logger instance
    """
    if name is None:
        # Get the calling module name
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")

    return structlog.get_logger(name)


def log_function_call(func_name: str, **kwargs: Any) -> None:
    """
    Log function call with parameters.

    Args:
        func_name: Name of the function being called
        **kwargs: Function parameters to log
    """
    logger = get_logger("imgstream.function_calls")
    logger.debug("function_call", function=func_name, parameters=kwargs)


def log_performance(operation: str, duration: float, **context: Any) -> None:
    """
    Log performance metrics.

    Args:
        operation: Name of the operation
        duration: Duration in seconds
        **context: Additional context information
    """
    logger = get_logger("imgstream.performance")
    logger.info("performance_metric", operation=operation, duration_seconds=duration, **context)


def log_user_action(user_id: str, action: str, **context: Any) -> None:
    """
    Log user actions for audit trail.

    Args:
        user_id: User identifier
        action: Action performed
        **context: Additional context information
    """
    logger = get_logger("imgstream.user_actions")
    logger.info("user_action", user_id=user_id, action=action, **context)


def log_error(error: Exception, context: dict[str, Any] | None = None) -> None:
    """
    Log errors with structured context.

    Args:
        error: Exception that occurred
        context: Additional context information
    """
    logger = get_logger("imgstream.errors")

    error_context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    if context:
        error_context.update(context)

    logger.error("error_occurred", **error_context, exc_info=error)


def log_security_event(event_type: str, user_id: str | None = None, **context: Any) -> None:
    """
    Log security-related events.

    Args:
        event_type: Type of security event
        user_id: User identifier (if applicable)
        **context: Additional context information
    """
    logger = get_logger("imgstream.security")
    logger.warning("security_event", event_type=event_type, user_id=user_id, **context)


# Context managers for structured logging
class LogContext:
    """Context manager for adding structured context to logs."""

    def __init__(self, logger: Any, **context: Any):
        self.logger = logger
        self.context = context
        self.bound_logger: Any = None

    def __enter__(self) -> Any:
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None and self.bound_logger is not None:
            self.bound_logger.error(
                "context_exception", exception_type=exc_type.__name__, exception_message=str(exc_val), exc_info=exc_val
            )


def log_context(**context: Any) -> LogContext:
    """
    Create a logging context manager.

    Args:
        **context: Context variables to add to all log messages

    Returns:
        LogContext: Context manager for structured logging
    """
    logger = get_logger()
    return LogContext(logger, **context)
