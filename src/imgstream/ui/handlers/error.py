"""
Centralized error handling and classification for imgstream application.

This module provides comprehensive error classification, handling, and
user-friendly error message generation for all application components.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from imgstream.logging_config import get_logger, log_error, log_security_event

# Import Streamlit exceptions for special handling
try:
    from streamlit.runtime.scriptrunner_utils.exceptions import RerunException
except ImportError:
    # Fallback if Streamlit is not available
    RerunException = type(None)  # type: ignore

logger = get_logger(__name__)


class ErrorCategory(Enum):
    """Error categories for classification and handling."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    UPLOAD = "upload"
    IMAGE_PROCESSING = "image_processing"
    DATABASE = "database"
    STORAGE = "storage"
    VALIDATION = "validation"
    NETWORK = "network"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorInfo:
    """Structured error information."""

    category: ErrorCategory
    severity: ErrorSeverity
    code: str
    message: str
    user_message: str
    details: dict[str, Any]
    timestamp: datetime
    recoverable: bool = True
    retry_suggested: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert error info to dictionary."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "user_message": self.user_message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "recoverable": self.recoverable,
            "retry_suggested": self.retry_suggested,
        }


class ImgStreamError(Exception):
    """Base exception class for imgstream application."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
        retry_suggested: bool = False,
        original_exception: Exception | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.code = code or f"{category.value}_error"
        self.user_message = user_message or self._generate_user_message()
        self.details = details or {}
        self.recoverable = recoverable
        self.retry_suggested = retry_suggested
        self.original_exception = original_exception
        self.timestamp = datetime.now()

        # Log the error
        self._log_error()

    def _generate_user_message(self) -> str:
        """Generate user-friendly error message."""
        user_messages = {
            ErrorCategory.AUTHENTICATION: "認証に失敗しました。再度ログインしてください。",
            ErrorCategory.AUTHORIZATION: "この操作を実行する権限がありません。",
            ErrorCategory.UPLOAD: "ファイルのアップロードに失敗しました。",
            ErrorCategory.IMAGE_PROCESSING: "画像の処理中にエラーが発生しました。",
            ErrorCategory.DATABASE: "データベースエラーが発生しました。",
            ErrorCategory.STORAGE: "ストレージエラーが発生しました。",
            ErrorCategory.VALIDATION: "入力データに問題があります。",
            ErrorCategory.NETWORK: "ネットワークエラーが発生しました。",
            ErrorCategory.SYSTEM: "システムエラーが発生しました。",
            ErrorCategory.UNKNOWN: "予期しないエラーが発生しました。",
        }
        return user_messages.get(self.category, "エラーが発生しました。")

    def _log_error(self) -> None:
        """Log the error with appropriate level."""
        error_context = {
            "category": self.category.value,
            "severity": self.severity.value,
            "code": self.code,
            "recoverable": self.recoverable,
            "retry_suggested": self.retry_suggested,
            **self.details,
        }

        if self.original_exception:
            error_context["original_exception"] = str(self.original_exception)

        log_error(self, error_context)

        # Log security events for authentication/authorization errors
        if self.category in [ErrorCategory.AUTHENTICATION, ErrorCategory.AUTHORIZATION]:
            log_security_event(self.category.value, context=error_context)

    def get_error_info(self) -> ErrorInfo:
        """Get structured error information."""
        return ErrorInfo(
            category=self.category,
            severity=self.severity,
            code=self.code,
            message=str(self),
            user_message=self.user_message,
            details=self.details,
            timestamp=self.timestamp,
            recoverable=self.recoverable,
            retry_suggested=self.retry_suggested,
        )


# Specific error classes for different categories


class AuthenticationError(ImgStreamError):
    """Authentication-related errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            code=code or "auth_failed",
            user_message=user_message or "認証に失敗しました。再度ログインしてください。",
            details=details,
            recoverable=True,
            retry_suggested=True,
            original_exception=original_exception,
        )


class AuthorizationError(ImgStreamError):
    """Authorization-related errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            code=code or "access_denied",
            user_message=user_message or "この操作を実行する権限がありません。",
            details=details,
            recoverable=False,
            retry_suggested=False,
            original_exception=original_exception,
        )


class UploadError(ImgStreamError):
    """Upload-related errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
        retry_suggested: bool = True,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.UPLOAD,
            severity=ErrorSeverity.MEDIUM,
            code=code or "upload_failed",
            user_message=user_message or "ファイルのアップロードに失敗しました。再度お試しください。",
            details=details,
            recoverable=recoverable,
            retry_suggested=retry_suggested,
            original_exception=original_exception,
        )


class ImageProcessingError(ImgStreamError):
    """Image processing-related errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
        retry_suggested: bool = False,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.IMAGE_PROCESSING,
            severity=ErrorSeverity.MEDIUM,
            code=code or "image_processing_failed",
            user_message=user_message or "画像の処理中にエラーが発生しました。ファイル形式を確認してください。",
            details=details,
            recoverable=recoverable,
            retry_suggested=retry_suggested,
            original_exception=original_exception,
        )


class DatabaseError(ImgStreamError):
    """Database-related errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
        retry_suggested: bool = True,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            code=code or "database_error",
            user_message=user_message or "データベースエラーが発生しました。しばらく待ってから再度お試しください。",
            details=details,
            recoverable=recoverable,
            retry_suggested=retry_suggested,
            original_exception=original_exception,
        )


class StorageError(ImgStreamError):
    """Storage-related errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
        retry_suggested: bool = True,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.STORAGE,
            severity=ErrorSeverity.HIGH,
            code=code or "storage_error",
            user_message=user_message or "ストレージエラーが発生しました。しばらく待ってから再度お試しください。",
            details=details,
            recoverable=recoverable,
            retry_suggested=retry_suggested,
            original_exception=original_exception,
        )


class ValidationError(ImgStreamError):
    """Validation-related errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            code=code or "validation_failed",
            user_message=user_message or "入力データに問題があります。内容を確認してください。",
            details=details,
            recoverable=True,
            retry_suggested=False,
            original_exception=original_exception,
        )


class NetworkError(ImgStreamError):
    """Network-related errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            code=code or "network_error",
            user_message=user_message or "ネットワークエラーが発生しました。接続を確認してください。",
            details=details,
            recoverable=True,
            retry_suggested=True,
            original_exception=original_exception,
        )


class ImgStreamSystemError(ImgStreamError):
    """System-related errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
        recoverable: bool = False,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            code=code or "system_error",
            user_message=user_message or "システムエラーが発生しました。管理者にお問い合わせください。",
            details=details,
            recoverable=recoverable,
            retry_suggested=False,
            original_exception=original_exception,
        )


class ErrorHandler:
    """Centralized error handler for the application."""

    def __init__(self) -> None:
        self.error_counts: dict[str, int] = {}
        self.logger = get_logger(__name__)

    def handle_error(
        self,
        error: Exception | ImgStreamError,
        context: dict[str, Any] | None = None,
    ) -> ErrorInfo:
        """
        Handle and classify errors.

        Args:
            error: Exception to handle
            context: Additional context information

        Returns:
            ErrorInfo: Structured error information
        """
        context = context or {}

        # If it's already an ImgStreamError, return its info
        if isinstance(error, ImgStreamError):
            error_info = error.get_error_info()
            self._track_error(error_info.code)
            return error_info

        # Classify and wrap the error
        classified_error = self._classify_error(error, context)
        error_info = classified_error.get_error_info()
        self._track_error(error_info.code)

        return error_info

    def _classify_error(
        self,
        error: Exception,
        context: dict[str, Any],
    ) -> ImgStreamError:
        """Classify an exception into appropriate ImgStreamError."""
        error_type = type(error).__name__
        error_message = str(error)

        # Authentication errors
        if any(
            keyword in error_message.lower()
            for keyword in ["authentication", "auth", "login", "jwt", "token", "unauthorized"]
        ):
            return AuthenticationError(
                message=error_message,
                details={"original_type": error_type, **context},
                original_exception=error,
            )

        # Authorization errors
        if any(
            keyword in error_message.lower() for keyword in ["permission", "access denied", "forbidden", "not allowed"]
        ):
            return AuthorizationError(
                message=error_message,
                details={"original_type": error_type, **context},
                original_exception=error,
            )

        # Upload errors
        if any(
            keyword in error_message.lower() for keyword in ["upload", "file size", "too large", "too small", "format"]
        ):
            return UploadError(
                message=error_message,
                details={"original_type": error_type, **context},
                original_exception=error,
            )

        # Image processing errors
        if any(
            keyword in error_message.lower() for keyword in ["image", "thumbnail", "exif", "pillow", "heic", "jpeg"]
        ):
            return ImageProcessingError(
                message=error_message,
                details={"original_type": error_type, **context},
                original_exception=error,
            )

        # Database errors
        if any(keyword in error_message.lower() for keyword in ["database", "duckdb", "sql", "query", "connection"]):
            return DatabaseError(
                message=error_message,
                details={"original_type": error_type, **context},
                original_exception=error,
            )

        # Storage errors
        if any(keyword in error_message.lower() for keyword in ["storage", "gcs", "bucket", "cloud", "download"]):
            return StorageError(
                message=error_message,
                details={"original_type": error_type, **context},
                original_exception=error,
            )

        # Validation errors
        if any(keyword in error_message.lower() for keyword in ["validation", "invalid", "required", "missing"]):
            return ValidationError(
                message=error_message,
                details={"original_type": error_type, **context},
                original_exception=error,
            )

        # Network errors
        if any(keyword in error_message.lower() for keyword in ["network", "connection", "timeout", "unreachable"]):
            return NetworkError(
                message=error_message,
                details={"original_type": error_type, **context},
                original_exception=error,
            )

        # System errors for critical exceptions
        if error_type in ["SystemError", "MemoryError", "OSError"]:
            return ImgStreamSystemError(
                message=error_message,
                details={"original_type": error_type, **context},
                original_exception=error,
            )

        # Default to unknown category
        return ImgStreamError(
            message=error_message,
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            details={"original_type": error_type, **context},
            original_exception=error,
        )

    def _track_error(self, error_code: str) -> None:
        """Track error occurrence for monitoring."""
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1

        # Log error frequency for monitoring
        if self.error_counts[error_code] % 10 == 0:  # Every 10th occurrence
            self.logger.warning("frequent_error_detected", error_code=error_code, count=self.error_counts[error_code])

    def get_error_statistics(self) -> dict[str, int]:
        """Get error occurrence statistics."""
        return self.error_counts.copy()

    def reset_statistics(self) -> None:
        """Reset error statistics."""
        self.error_counts.clear()


# Global error handler instance
error_handler = ErrorHandler()


def handle_error(
    error: Exception | ImgStreamError,
    context: dict[str, Any] | None = None,
) -> ErrorInfo:
    """
    Global error handling function.

    Args:
        error: Exception to handle
        context: Additional context information

    Returns:
        ErrorInfo: Structured error information
    """
    return error_handler.handle_error(error, context)


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    return error_handler