"""Tests for error handling and classification functionality."""

from datetime import datetime

from imgstream.ui.handlers.error import (
    AuthenticationError,
    AuthorizationError,
    DatabaseError,
    ErrorCategory,
    ErrorHandler,
    ErrorInfo,
    ErrorSeverity,
    ImageProcessingError,
    ImgStreamError,
    ImgStreamSystemError,
    NetworkError,
    StorageError,
    UploadError,
    ValidationError,
    handle_error,
)


class TestErrorInfo:
    """Test ErrorInfo dataclass."""

    def test_error_info_creation(self):
        """Test ErrorInfo creation and conversion to dict."""
        timestamp = datetime.now()
        error_info = ErrorInfo(
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            code="auth_failed",
            message="Authentication failed",
            user_message="認証に失敗しました",
            details={"user_id": "test123"},
            timestamp=timestamp,
            recoverable=True,
            retry_suggested=True,
        )

        assert error_info.category == ErrorCategory.AUTHENTICATION
        assert error_info.severity == ErrorSeverity.HIGH
        assert error_info.code == "auth_failed"
        assert error_info.recoverable is True

        # Test to_dict conversion
        error_dict = error_info.to_dict()
        assert error_dict["category"] == "authentication"
        assert error_dict["severity"] == "high"
        assert error_dict["code"] == "auth_failed"
        assert error_dict["timestamp"] == timestamp.isoformat()


class TestImgStreamError:
    """Test base ImgStreamError class."""

    def test_basic_error_creation(self):
        """Test basic error creation with defaults."""
        error = ImgStreamError("Test error message")

        assert str(error) == "Test error message"
        assert error.category == ErrorCategory.UNKNOWN
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.code == "unknown_error"
        assert error.recoverable is True
        assert error.retry_suggested is False
        assert isinstance(error.timestamp, datetime)

    def test_custom_error_creation(self):
        """Test error creation with custom parameters."""
        details = {"operation": "test_op", "user_id": "123"}
        error = ImgStreamError(
            message="Custom error",
            category=ErrorCategory.UPLOAD,
            severity=ErrorSeverity.HIGH,
            code="custom_error",
            user_message="カスタムエラーです",
            details=details,
            recoverable=False,
            retry_suggested=True,
        )

        assert error.category == ErrorCategory.UPLOAD
        assert error.severity == ErrorSeverity.HIGH
        assert error.code == "custom_error"
        assert error.user_message == "カスタムエラーです"
        assert error.details == details
        assert error.recoverable is False
        assert error.retry_suggested is True

    def test_error_info_generation(self):
        """Test ErrorInfo generation from ImgStreamError."""
        error = ImgStreamError(
            "Test message",
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.CRITICAL,
        )

        error_info = error.get_error_info()
        assert error_info.category == ErrorCategory.DATABASE
        assert error_info.severity == ErrorSeverity.CRITICAL
        assert error_info.message == "Test message"


class TestSpecificErrorTypes:
    """Test specific error type classes."""

    def test_authentication_error(self):
        """Test AuthenticationError creation."""
        error = AuthenticationError("Auth failed")

        assert error.category == ErrorCategory.AUTHENTICATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.code == "auth_failed"
        assert error.recoverable is True
        assert error.retry_suggested is True
        assert "認証に失敗しました" in error.user_message

    def test_authorization_error(self):
        """Test AuthorizationError creation."""
        error = AuthorizationError("Access denied")

        assert error.category == ErrorCategory.AUTHORIZATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.code == "access_denied"
        assert error.recoverable is False
        assert error.retry_suggested is False
        assert "権限がありません" in error.user_message

    def test_upload_error(self):
        """Test UploadError creation."""
        error = UploadError("Upload failed")

        assert error.category == ErrorCategory.UPLOAD
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.code == "upload_failed"
        assert error.recoverable is True
        assert error.retry_suggested is True
        assert "アップロードに失敗" in error.user_message

    def test_image_processing_error(self):
        """Test ImageProcessingError creation."""
        error = ImageProcessingError("Processing failed")

        assert error.category == ErrorCategory.IMAGE_PROCESSING
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.code == "image_processing_failed"
        assert "画像の処理中" in error.user_message

    def test_database_error(self):
        """Test DatabaseError creation."""
        error = DatabaseError("DB connection failed")

        assert error.category == ErrorCategory.DATABASE
        assert error.severity == ErrorSeverity.HIGH
        assert error.code == "database_error"
        assert "データベースエラー" in error.user_message

    def test_storage_error(self):
        """Test StorageError creation."""
        error = StorageError("Storage unavailable")

        assert error.category == ErrorCategory.STORAGE
        assert error.severity == ErrorSeverity.HIGH
        assert error.code == "storage_error"
        assert "ストレージエラー" in error.user_message

    def test_validation_error(self):
        """Test ValidationError creation."""
        error = ValidationError("Invalid input")

        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.LOW
        assert error.code == "validation_failed"
        assert "入力データに問題" in error.user_message

    def test_network_error(self):
        """Test NetworkError creation."""
        error = NetworkError("Connection timeout")

        assert error.category == ErrorCategory.NETWORK
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.code == "network_error"
        assert "ネットワークエラー" in error.user_message

    def test_system_error(self):
        """Test ImgStreamSystemError creation."""
        error = ImgStreamSystemError("System failure")

        assert error.category == ErrorCategory.SYSTEM
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.code == "system_error"
        assert error.recoverable is False
        assert "システムエラー" in error.user_message


class TestErrorHandler:
    """Test ErrorHandler class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = ErrorHandler()

    def test_handle_imgstream_error(self):
        """Test handling of ImgStreamError."""
        original_error = AuthenticationError("Auth failed")
        error_info = self.handler.handle_error(original_error)

        assert error_info.category == ErrorCategory.AUTHENTICATION
        assert error_info.code == "auth_failed"
        assert self.handler.error_counts["auth_failed"] == 1

    def test_handle_generic_exception(self):
        """Test handling of generic exceptions."""
        original_error = ValueError("Invalid value")
        error_info = self.handler.handle_error(original_error)

        # ValueError with "invalid" gets classified as validation error
        assert error_info.category == ErrorCategory.VALIDATION
        assert "Invalid value" in error_info.message

    def test_error_classification_authentication(self):
        """Test classification of authentication-related errors."""
        error = Exception("JWT token invalid")
        error_info = self.handler.handle_error(error)

        assert error_info.category == ErrorCategory.AUTHENTICATION

    def test_error_classification_upload(self):
        """Test classification of upload-related errors."""
        error = Exception("File too large for upload")
        error_info = self.handler.handle_error(error)

        assert error_info.category == ErrorCategory.UPLOAD

    def test_error_classification_image_processing(self):
        """Test classification of image processing errors."""
        error = Exception("EXIF data corrupted")
        error_info = self.handler.handle_error(error)

        assert error_info.category == ErrorCategory.IMAGE_PROCESSING

    def test_error_classification_database(self):
        """Test classification of database errors."""
        error = Exception("DuckDB connection failed")
        error_info = self.handler.handle_error(error)

        assert error_info.category == ErrorCategory.DATABASE

    def test_error_classification_storage(self):
        """Test classification of storage errors."""
        error = Exception("GCS bucket not found")
        error_info = self.handler.handle_error(error)

        assert error_info.category == ErrorCategory.STORAGE

    def test_error_classification_validation(self):
        """Test classification of validation errors."""
        error = Exception("Required field missing")
        error_info = self.handler.handle_error(error)

        assert error_info.category == ErrorCategory.VALIDATION

    def test_error_classification_network(self):
        """Test classification of network errors."""
        error = Exception("Network timeout occurred")
        error_info = self.handler.handle_error(error)

        assert error_info.category == ErrorCategory.NETWORK

    def test_error_classification_system(self):
        """Test classification of system errors."""
        error = MemoryError("Out of memory")
        error_info = self.handler.handle_error(error)

        assert error_info.category == ErrorCategory.SYSTEM

    def test_error_tracking(self):
        """Test error occurrence tracking."""
        # Generate multiple errors of same type
        for _ in range(5):
            error = Exception("Test error")
            self.handler.handle_error(error)

        assert self.handler.error_counts["unknown_error"] == 5

    def test_error_statistics(self):
        """Test error statistics functionality."""
        # Generate different types of errors
        self.handler.handle_error(AuthenticationError("Auth failed"))
        self.handler.handle_error(UploadError("Upload failed"))
        self.handler.handle_error(UploadError("Another upload failed"))

        stats = self.handler.get_error_statistics()
        assert stats["auth_failed"] == 1
        assert stats["upload_failed"] == 2

        # Test reset
        self.handler.reset_statistics()
        assert len(self.handler.get_error_statistics()) == 0

    def test_context_handling(self):
        """Test error handling with context."""
        context = {"user_id": "test123", "operation": "test_op"}
        error = Exception("Test error")

        error_info = self.handler.handle_error(error, context)

        assert error_info.details["user_id"] == "test123"
        assert error_info.details["operation"] == "test_op"


class TestGlobalErrorHandler:
    """Test global error handling functions."""

    def test_global_handle_error(self):
        """Test global handle_error function."""
        error = AuthenticationError("Global auth error")
        error_info = handle_error(error)

        assert error_info.category == ErrorCategory.AUTHENTICATION
        assert error_info.code == "auth_failed"

    def test_global_handle_error_with_context(self):
        """Test global handle_error with context."""
        error = Exception("Test error")
        context = {"test_key": "test_value"}

        error_info = handle_error(error, context)

        assert error_info.details["test_key"] == "test_value"


class TestErrorIntegration:
    """Test error handling integration scenarios."""

    def test_chained_errors(self):
        """Test handling of chained exceptions."""
        original = ValueError("Original error")
        chained = ImageProcessingError("Processing failed", original_exception=original)

        error_info = handle_error(chained)

        assert error_info.category == ErrorCategory.IMAGE_PROCESSING
        # The original exception is logged but not included in details by default
        assert chained.original_exception == original

    def test_error_with_custom_user_message(self):
        """Test error with custom user message."""
        error = UploadError("Technical upload error", user_message="カスタムアップロードエラーメッセージ")

        error_info = error.get_error_info()
        assert error_info.user_message == "カスタムアップロードエラーメッセージ"

    def test_error_severity_mapping(self):
        """Test that different error types have appropriate severity."""
        validation_error = ValidationError("Invalid input")
        auth_error = AuthenticationError("Auth failed")
        system_error = ImgStreamSystemError("System failure")

        assert validation_error.severity == ErrorSeverity.LOW
        assert auth_error.severity == ErrorSeverity.HIGH
        assert system_error.severity == ErrorSeverity.CRITICAL

    def test_recoverable_flags(self):
        """Test recoverable and retry flags for different error types."""
        auth_error = AuthenticationError("Auth failed")
        authz_error = AuthorizationError("Access denied")
        system_error = ImgStreamSystemError("System failure")

        assert auth_error.recoverable is True
        assert auth_error.retry_suggested is True

        assert authz_error.recoverable is False
        assert authz_error.retry_suggested is False

        assert system_error.recoverable is False
        assert system_error.retry_suggested is False
