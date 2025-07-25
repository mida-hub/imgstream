"""Authentication service for imgstream application."""

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication is required but user is not authenticated."""

    pass


class AccessDeniedError(Exception):
    """Raised when user attempts to access resources they don't own."""

    pass


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

    def parse_iap_header(self, headers: dict[str, str]) -> UserInfo | None:
        """Parse Cloud IAP JWT header to extract user information."""
        jwt_token = headers.get(self.IAP_HEADER_NAME)

        if not jwt_token:
            logger.warning("Cloud IAP JWT header not found")
            return None

        try:
            user_info = self._decode_jwt_payload(jwt_token)
            logger.info(f"Successfully authenticated user: {user_info.email}")
            return user_info
        except Exception as e:
            logger.error(f"Failed to parse IAP header: {e}")
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

    def _extract_user_info(self, payload: dict[str, Any]) -> UserInfo:
        """Extract user information from JWT payload."""
        email = payload.get("email")
        sub = payload.get("sub")

        if not email:
            raise ValueError("Email not found in JWT payload")
        if not sub:
            raise ValueError("Subject (user ID) not found in JWT payload")

        name = payload.get("name")
        picture = payload.get("picture")

        return UserInfo(user_id=sub, email=email, name=name, picture=picture)

    def authenticate_request(self, headers: dict[str, str]) -> bool:
        """Authenticate a request using Cloud IAP headers."""
        user_info = self.parse_iap_header(headers)

        if user_info:
            self._current_user = user_info
            return True
        else:
            self._current_user = None
            return False

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
        self._current_user = None
        logger.info("Authentication state cleared")

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
            raise AuthenticationError("User is not authenticated")
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
            logger.warning("Access check failed: User not authenticated")
            return False

        user_storage_prefix = self.get_user_storage_path()
        user_db_prefix = self.get_user_database_path()

        # Check storage path access with exact prefix matching
        if user_storage_prefix:
            storage_prefix_clean = user_storage_prefix.rstrip("/")
            if resource_path == storage_prefix_clean or resource_path.startswith(storage_prefix_clean + "/"):
                return True

        # Check database path access
        if user_db_prefix:
            db_dir = user_db_prefix.rsplit("/", 1)[0]
            if resource_path == db_dir or resource_path.startswith(db_dir + "/") or resource_path == user_db_prefix:
                return True

        user_email = self.get_user_email()
        logger.warning(f"Access denied: User {user_email} attempted to access {resource_path}")
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
            AccessDeniedError: If user doesn't own the resource
        """
        self.ensure_authenticated()

        if not self.check_resource_access(resource_path):
            raise AccessDeniedError(f"Access denied to resource: {resource_path}")

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
