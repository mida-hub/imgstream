"""Authentication service for imgstream application."""

import base64
import json
from dataclasses import dataclass
from typing import Any

from ..error_handling import AuthenticationError, AuthorizationError
from ..logging_config import get_logger, log_error, log_security_event, log_user_action

logger = get_logger(__name__)


# Keep backward compatibility aliases
AccessDeniedError = AuthorizationError


@dataclass
class UserInfo:
    """Represents authenticated user information from Cloud IAP."""

    user_id: str
    email: str
    name: str | None = None
    picture: str | None = None

    def get_storage_path_prefix(self) -> str:
        """Get the storage path prefix for this user."""
        safe_email = self.email.replace("@", "_at_").replace(".", "_dot_")
        return f"photos/{safe_email}/"

    def get_database_path(self) -> str:
        """Get the database file path for this user."""
        safe_email = self.email.replace("@", "_at_").replace(".", "_dot_")
        return f"dbs/{safe_email}/metadata.db"


class CloudIAPAuthService:
    """Service for handling Cloud IAP authentication."""

    IAP_HEADER_NAME = "X-Goog-IAP-JWT-Assertion"

    def __init__(self) -> None:
        """Initialize the Cloud IAP authentication service."""
        self._current_user: UserInfo | None = None
        self._development_mode = self._is_development_mode()

        if self._development_mode:
            logger.info("development_auth_mode_enabled", message="Using development authentication mode")

    def _is_development_mode(self) -> bool:
        """Check if running in development mode."""
        import os

        environment = os.getenv("ENVIRONMENT", "development").lower().strip()

        # List of environment values that indicate development mode
        dev_environments = ["development", "dev", "local", "test"]

        is_dev = environment in dev_environments

        logger.debug(
            "environment_mode_check",
            environment=environment,
            is_development=is_dev,
            message=f"Environment mode determined: {'development' if is_dev else 'production'}",
        )

        return is_dev

    def _get_development_user(self) -> UserInfo:
        """Get development user for local testing."""
        import os

        dev_email = os.getenv("DEV_USER_EMAIL", "dev@example.com")
        dev_name = os.getenv("DEV_USER_NAME", "Development User")
        dev_user_id = os.getenv("DEV_USER_ID", "dev-user-123")

        # Basic validation for development user data
        if not dev_email or "@" not in dev_email:
            logger.warning("invalid_dev_user_email", email=dev_email, message="Using default email")
            dev_email = "dev@example.com"

        if not dev_name or not dev_name.strip():
            logger.warning("invalid_dev_user_name", name=dev_name, message="Using default name")
            dev_name = "Development User"

        if not dev_user_id or not dev_user_id.strip():
            logger.warning("invalid_dev_user_id", user_id=dev_user_id, message="Using default user ID")
            dev_user_id = "dev-user-123"

        logger.debug(
            "development_user_created",
            user_id=dev_user_id,
            email=dev_email,
            name=dev_name,
            message="Development user created successfully",
        )

        return UserInfo(user_id=dev_user_id, email=dev_email, name=dev_name, picture=None)

    def parse_iap_header(self, headers: dict[str, str]) -> UserInfo | None:
        """Parse Cloud IAP JWT header to extract user information."""
        # Development mode: bypass IAP authentication
        if self._development_mode:
            dev_user = self._get_development_user()
            log_user_action(dev_user.user_id, "development_authentication", email=dev_user.email, mode="development")
            return dev_user

        # Production mode: use Cloud IAP
        jwt_token = headers.get(self.IAP_HEADER_NAME)

        if not jwt_token:
            log_security_event("missing_iap_header", context={"headers_present": list(headers.keys())})
            return None

        try:
            user_info = self._decode_jwt_payload(jwt_token)
            log_user_action(user_info.user_id, "authentication_success", email=user_info.email)
            return user_info
        except Exception as e:
            log_error(e, {"operation": "parse_iap_header", "has_token": bool(jwt_token)})
            log_security_event("authentication_failure", context={"error": str(e)})
            return None

    def _decode_jwt_payload(self, jwt_token: str) -> UserInfo:
        """Decode JWT token payload to extract user information."""
        try:
            parts = jwt_token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid JWT token format")

            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes.decode("utf-8"))

            return self._extract_user_info(payload)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to decode JWT payload: {e}") from e

    def _sanitize_user_input(self, value: str | None) -> str | None:
        """Sanitize user input to prevent XSS and injection attacks."""
        if not value:
            return value

        # Remove potentially dangerous characters and patterns
        import html
        import re

        sanitized = str(value)

        # Remove SQL injection patterns first (before HTML escaping)
        sql_patterns = [
            r"(?i)(drop\s+table|delete\s+from|union\s+select|insert\s+into)",
            r"(?i)(--|\*\/|\/\*)",
            r"(?i)(or\s+1\s*=\s*1|and\s+1\s*=\s*1)",
        ]

        for pattern in sql_patterns:
            sanitized = re.sub(pattern, "", sanitized)

        # Remove XSS patterns (before HTML escaping)
        xss_patterns = [
            r"(?i)<script[^>]*>.*?</script>",
            r"(?i)<img[^>]*onerror[^>]*>",
            r"(?i)<svg[^>]*onload[^>]*>",
            r"(?i)javascript:",
        ]

        for pattern in xss_patterns:
            sanitized = re.sub(pattern, "", sanitized)

        # HTML escape the value after pattern removal
        sanitized = html.escape(sanitized)

        return sanitized

    def _extract_user_info(self, payload: dict[str, Any]) -> UserInfo:
        """Extract user information from JWT payload."""
        email = payload.get("email")
        sub = payload.get("sub")

        if not email:
            raise ValueError("Email not found in JWT payload")
        if not sub:
            raise ValueError("Subject (user ID) not found in JWT payload")

        # Sanitize all user inputs to prevent XSS and injection attacks
        sanitized_email = self._sanitize_user_input(email)
        sanitized_sub = self._sanitize_user_input(sub)
        sanitized_name = self._sanitize_user_input(payload.get("name"))
        sanitized_picture = self._sanitize_user_input(payload.get("picture"))

        # Ensure required fields are not None after sanitization
        if not sanitized_email:
            raise ValueError("Email became invalid after sanitization")
        if not sanitized_sub:
            raise ValueError("Subject (user ID) became invalid after sanitization")

        return UserInfo(user_id=sanitized_sub, email=sanitized_email, name=sanitized_name, picture=sanitized_picture)

    def authenticate_request(self, headers: dict[str, str]) -> UserInfo | None:
        """
        Authenticate a request using IAP headers.
        Args:
            headers: Request headers containing IAP JWT assertion
        Returns:
            UserInfo | None: UserInfo object if authentication successful, None otherwise
        """
        user_info = self.parse_iap_header(headers)
        if user_info:
            self._current_user = user_info
            logger.info("request_authenticated", user_id=user_info.user_id, email=user_info.email)
            return user_info
        else:
            self._current_user = None
            log_security_event("request_authentication_failed")
            return None

    def get_current_user(self) -> UserInfo | None:
        """Get the currently authenticated user."""
        return self._current_user

    def is_authenticated(self) -> bool:
        """Check if a user is currently authenticated."""
        return self._current_user is not None

    def get_user_id(self) -> str | None:
        """Get the current user's ID."""
        return self._current_user.user_id if self._current_user else None

    def get_user_email(self) -> str | None:
        """Get the current user's email."""
        return self._current_user.email if self._current_user else None

    def get_user_storage_path(self) -> str | None:
        """Get the storage path prefix for the current user."""
        if self._current_user:
            return self._current_user.get_storage_path_prefix()
        return None

    def get_user_database_path(self) -> str | None:
        """Get the database path for the current user."""
        if self._current_user:
            return self._current_user.get_database_path()
        return None

    def clear_authentication(self) -> None:
        """Clear the current authentication state."""
        user_id = self._current_user.user_id if self._current_user else None
        self._current_user = None
        log_user_action(user_id or "unknown", "authentication_cleared")

    def set_current_user(self, user_info: UserInfo | None) -> None:
        """Set the current user (for testing/development purposes)."""
        self._current_user = user_info

    def ensure_authenticated(self) -> UserInfo:
        """
        Ensure user is authenticated, raise exception if not.

        Returns:
            UserInfo: Current authenticated user information

        Raises:
            AuthenticationError: If user is not authenticated
        """
        if not self.is_authenticated():
            raise AuthenticationError(
                "User is not authenticated",
                code="user_not_authenticated",
                details={"operation": "ensure_authenticated"},
            )
        return self._current_user  # type: ignore

    def check_resource_access(self, resource_path: str) -> bool:
        """
        Check if current user has access to the specified resource path.

        Args:
            resource_path: Path to the resource (e.g., "photos/user123/file.jpg")

        Returns:
            bool: True if user has access, False otherwise
        """
        if not self.is_authenticated():
            log_security_event("access_check_unauthenticated", context={"resource_path": resource_path})
            return False

        user_storage_prefix = self.get_user_storage_path()
        user_db_prefix = self.get_user_database_path()

        # Check storage path access with exact prefix matching
        if user_storage_prefix:
            storage_prefix_clean = user_storage_prefix.rstrip("/")
            if resource_path == storage_prefix_clean or resource_path.startswith(storage_prefix_clean + "/"):
                logger.debug(
                    "resource_access_granted",
                    user_id=self.get_user_id(),
                    resource_path=resource_path,
                    access_type="storage",
                )
                return True

        # Check database path access
        if user_db_prefix:
            db_dir = user_db_prefix.rsplit("/", 1)[0]
            if resource_path == db_dir or resource_path.startswith(db_dir + "/") or resource_path == user_db_prefix:
                logger.debug(
                    "resource_access_granted",
                    user_id=self.get_user_id(),
                    resource_path=resource_path,
                    access_type="database",
                )
                return True

        user_email = self.get_user_email()
        log_security_event(
            "access_denied",
            user_id=self.get_user_id(),
            context={"user_email": user_email, "resource_path": resource_path},
        )
        return False

    def get_user_resource_paths(self) -> dict[str, str]:
        """
        Get all resource paths for the current user.

        Returns:
            dict: Dictionary containing user's resource paths

        Raises:
            AuthenticationError: If user is not authenticated
        """
        user = self.ensure_authenticated()

        safe_email = user.email.replace("@", "_at_").replace(".", "_dot_")
        storage_prefix = user.get_storage_path_prefix()

        return {
            "storage_prefix": storage_prefix,
            "database_path": user.get_database_path(),
            "original_photos": f"{storage_prefix}original/",
            "thumbnails": f"{storage_prefix}thumbs/",
            "database_dir": f"dbs/{safe_email}/",
        }

    def validate_user_ownership(self, resource_path: str) -> None:
        """
        Validate that the current user owns the specified resource.

        Args:
            resource_path: Path to the resource to validate

        Raises:
            AuthenticationError: If user is not authenticated
            AuthorizationError: If user doesn't own the resource
        """
        self.ensure_authenticated()

        if not self.check_resource_access(resource_path):
            raise AuthorizationError(
                f"Access denied to resource: {resource_path}",
                code="resource_access_denied",
                details={
                    "resource_path": resource_path,
                    "user_id": self.get_user_id(),
                    "user_email": self.get_user_email(),
                },
            )

    def require_authentication(self) -> None:
        """
        Decorator-style method to require authentication.

        Raises:
            AuthenticationError: If user is not authenticated
        """
        self.ensure_authenticated()


# Global authentication service instance
auth_service = CloudIAPAuthService()


def get_auth_service() -> CloudIAPAuthService:
    """Get the global authentication service instance."""
    return auth_service
