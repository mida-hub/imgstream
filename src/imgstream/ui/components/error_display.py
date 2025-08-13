"""
Streamlit error display components for user-friendly error presentation.

This module provides components for displaying errors in a user-friendly way
within the Streamlit interface, with appropriate styling and actions.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

import streamlit as st

from imgstream.ui.handlers.error_handling import ErrorInfo, ErrorSeverity
from ...logging_config import get_logger

# Type alias for Streamlit container
StreamlitContainer = Any

logger = get_logger(__name__)


class ErrorDisplayManager:
    """Manager for displaying errors in Streamlit interface."""

    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    def display_error(
        self,
        error_info: ErrorInfo,
        container: StreamlitContainer | None = None,
        show_details: bool = False,
        show_retry_button: bool = True,
        retry_callback: Callable | None = None,
    ) -> None:
        """
        Display error information in Streamlit interface.

        Args:
            error_info: Structured error information
            container: Streamlit container to display in (optional)
            show_details: Whether to show technical details
            show_retry_button: Whether to show retry button
            retry_callback: Function to call when retry is clicked
        """
        # Choose appropriate Streamlit alert type based on severity
        alert_type = self._get_alert_type(error_info.severity)

        # Define the display function
        def _display_content() -> None:
            # Main error message
            if alert_type == "error":
                st.error(error_info.user_message)
            elif alert_type == "warning":
                st.warning(error_info.user_message)
            else:
                st.info(error_info.user_message)

            # Error details in expander (if requested)
            if show_details and error_info.details:
                with st.expander("詳細情報", expanded=False):
                    st.write("**エラーコード:**", error_info.code)
                    st.write("**カテゴリ:**", error_info.category.value)
                    st.write("**発生時刻:**", error_info.timestamp.strftime("%Y-%m-%d %H:%M:%S"))

                    if error_info.details:
                        st.write("**詳細:**")
                        for key, value in error_info.details.items():
                            if key not in ["original_exception"]:  # Hide sensitive info
                                st.write(f"- {key}: {value}")

            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 2])

            with col1:
                if show_retry_button and error_info.retry_suggested and retry_callback:
                    if st.button("再試行", key=f"retry_{error_info.code}_{error_info.timestamp}"):
                        try:
                            retry_callback()
                            st.success("再試行しました")
                            st.rerun()
                        except Exception as e:
                            st.error(f"再試行に失敗しました: {str(e)}")

            with col2:
                if st.button("閉じる", key=f"close_{error_info.code}_{error_info.timestamp}"):
                    st.rerun()

        # Use container if provided, otherwise display directly
        if container is not None:
            with container:
                _display_content()
        else:
            _display_content()

        # Log the error display
        self.logger.info(
            "error_displayed_to_user",
            error_code=error_info.code,
            category=error_info.category.value,
            severity=error_info.severity.value,
            user_message=error_info.user_message,
        )

    def display_exception(
        self,
        exception: Exception,
        context: dict[str, Any] | None = None,
        container: StreamlitContainer | None = None,
        show_details: bool = False,
        retry_callback: Callable | None = None,
    ) -> None:
        """
        Display exception with automatic error handling.

        Args:
            exception: Exception to display
            context: Additional context information
            container: Streamlit container to display in
            show_details: Whether to show technical details
            retry_callback: Function to call when retry is clicked
        """
        from ..error_handling import handle_error

        error_info = handle_error(exception, context)
        self.display_error(
            error_info=error_info,
            container=container,
            show_details=show_details,
            retry_callback=retry_callback,
        )

    def display_validation_errors(
        self,
        errors: dict[str, str],
        container: StreamlitContainer | None = None,
    ) -> None:
        """
        Display validation errors for form fields.

        Args:
            errors: Dictionary of field names to error messages
            container: Streamlit container to display in
        """
        display_container = container if container is not None else st

        with display_container:  # type: ignore
            st.error("入力内容に問題があります:")
            for field, message in errors.items():
                st.write(f"• **{field}**: {message}")

    def display_success_message(
        self,
        message: str,
        container: StreamlitContainer | None = None,
        auto_dismiss: bool = True,
    ) -> None:
        """
        Display success message.

        Args:
            message: Success message to display
            container: Streamlit container to display in
            auto_dismiss: Whether to auto-dismiss after delay
        """
        display_container = container if container is not None else st

        with display_container:  # type: ignore
            st.success(message)

            if auto_dismiss:
                # Auto-dismiss after 3 seconds (using session state)
                if "success_message_time" not in st.session_state:
                    st.session_state.success_message_time = datetime.now()

                # Check if 3 seconds have passed
                elapsed = (datetime.now() - st.session_state.success_message_time).total_seconds()
                if elapsed > 3:
                    del st.session_state.success_message_time
                    st.rerun()

    def display_info_message(
        self,
        message: str,
        container: StreamlitContainer | None = None,
    ) -> None:
        """
        Display informational message.

        Args:
            message: Info message to display
            container: Streamlit container to display in
        """
        display_container = container if container is not None else st

        with display_container:  # type: ignore
            st.info(message)

    def display_warning_message(
        self,
        message: str,
        container: StreamlitContainer | None = None,
    ) -> None:
        """
        Display warning message.

        Args:
            message: Warning message to display
            container: Streamlit container to display in
        """
        display_container = container if container is not None else st

        with display_container:  # type: ignore
            st.warning(message)

    def _get_alert_type(self, severity: ErrorSeverity) -> str:
        """Get appropriate Streamlit alert type for error severity."""
        severity_mapping = {
            ErrorSeverity.LOW: "info",
            ErrorSeverity.MEDIUM: "warning",
            ErrorSeverity.HIGH: "error",
            ErrorSeverity.CRITICAL: "error",
        }
        return severity_mapping.get(severity, "error")

    def create_error_boundary(
        self,
        func: Callable,
        error_message: str = "操作中にエラーが発生しました",
        show_details: bool = False,
        retry_callback: Callable | None = None,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """
        Create an error boundary around a function call.

        Args:
            func: Function to execute
            error_message: Custom error message
            show_details: Whether to show technical details
            retry_callback: Function to call for retry
            context: Additional context for error handling

        Returns:
            Function result or None if error occurred
        """
        try:
            return func()
        except Exception as e:
            self.display_exception(
                exception=e,
                context=context,
                show_details=show_details,
                retry_callback=retry_callback,
            )
            return None


# Streamlit-specific error handling decorators and utilities


def streamlit_error_handler(
    error_message: str = "操作中にエラーが発生しました",
    show_details: bool = False,
    show_retry: bool = True,
) -> Callable:
    """
    Decorator for Streamlit functions to handle errors gracefully.

    Args:
        error_message: Custom error message
        show_details: Whether to show technical details
        show_retry: Whether to show retry button
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_display_manager.display_exception(
                    exception=e,
                    show_details=show_details,
                )
                return None

        return wrapper

    return decorator


def handle_upload_errors(func: Callable) -> Callable:
    """Decorator specifically for upload-related functions."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            from ..error_handling import UploadError, handle_error

            # Convert to upload error if not already
            if not isinstance(e, UploadError):
                error_info = handle_error(e, {"operation": "upload"})
            else:
                error_info = e.get_error_info()

            error_display_manager.display_error(error_info, show_retry_button=True)
            return None

    return wrapper


def handle_auth_errors(func: Callable) -> Callable:
    """Decorator specifically for authentication-related functions."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            from ..error_handling import AuthenticationError, handle_error

            # Convert to auth error if not already
            if not isinstance(e, AuthenticationError):
                error_info = handle_error(e, {"operation": "authentication"})
            else:
                error_info = e.get_error_info()

            error_display_manager.display_error(error_info, show_retry_button=False)

            # Redirect to login or show auth UI
            st.stop()

    return wrapper


# Global error display manager instance
error_display_manager = ErrorDisplayManager()


def get_error_display_manager() -> ErrorDisplayManager:
    """Get the global error display manager instance."""
    return error_display_manager


# Utility functions for common error scenarios


def display_file_validation_error(filename: str, errors: list[str]) -> None:
    """Display file validation errors."""
    st.error(f"ファイル '{filename}' の検証に失敗しました:")
    for error in errors:
        st.write(f"• {error}")


def display_upload_progress_error(filename: str, error_message: str) -> None:
    """Display upload progress error."""
    st.error(f"'{filename}' のアップロード中にエラーが発生しました: {error_message}")


def display_image_processing_error(filename: str, error_message: str) -> None:
    """Display image processing error."""
    st.error(f"'{filename}' の画像処理中にエラーが発生しました: {error_message}")


def display_database_error(operation: str) -> None:
    """Display database operation error."""
    st.error(f"データベース操作 '{operation}' でエラーが発生しました。しばらく待ってから再度お試しください。")


def display_storage_error(operation: str) -> None:
    """Display storage operation error."""
    st.error(f"ストレージ操作 '{operation}' でエラーが発生しました。しばらく待ってから再度お試しください。")


def display_network_error() -> None:
    """Display network error."""
    st.error("ネットワークエラーが発生しました。インターネット接続を確認してください。")


def display_system_error() -> None:
    """Display system error."""
    st.error("システムエラーが発生しました。管理者にお問い合わせください。")


# Context managers for error handling


class StreamlitErrorContext:
    """Context manager for handling errors in Streamlit code blocks."""

    def __init__(
        self,
        error_message: str = "操作中にエラーが発生しました",
        show_details: bool = False,
        container: StreamlitContainer | None = None,
    ):
        self.error_message = error_message
        self.show_details = show_details
        self.container = container

    def __enter__(self) -> "StreamlitErrorContext":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is not None:
            # Import RerunException for special handling
            try:
                from streamlit.runtime.scriptrunner_utils.exceptions import RerunException

                # RerunException is a normal control flow exception, not an error
                if isinstance(exc_val, RerunException):
                    return False  # Let RerunException propagate normally
            except ImportError:
                pass  # Streamlit not available

            # Handle all other exceptions
            error_display_manager.display_exception(
                exception=exc_val,
                container=self.container,
                show_details=self.show_details,
            )
            return True  # Suppress the exception
        return False


def error_context(
    error_message: str = "操作中にエラーが発生しました",
    show_details: bool = False,
    container: StreamlitContainer | None = None,
) -> StreamlitErrorContext:
    """Create an error context manager for Streamlit operations."""
    return StreamlitErrorContext(error_message, show_details, container)
