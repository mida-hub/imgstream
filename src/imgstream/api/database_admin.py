"""Database administration endpoints for development and testing."""

import os
from typing import Any

import streamlit as st
from datetime import datetime

from ..services.metadata import get_metadata_service, MetadataError
from ..services.auth import get_auth_service
from ..logging_config import get_logger, log_user_action

logger = get_logger(__name__)


class DatabaseAdminError(Exception):
    """Raised when database admin operations fail."""

    pass


def is_development_environment() -> bool:
    """Check if running in development environment."""
    environment = os.getenv("ENVIRONMENT", "production").lower()
    return environment in ["development", "dev", "test", "testing"]


def require_development_environment() -> None:
    """Ensure we're running in development environment."""
    if not is_development_environment():
        raise DatabaseAdminError(
            "Database admin operations are only available in development/test environments. "
            f"Current environment: {os.getenv('ENVIRONMENT', 'production')}"
        )


def reset_user_database(user_id: str, confirm_reset: bool = False) -> dict[str, Any]:
    """
    Reset database for a specific user (development/test only).

    Args:
        user_id: User identifier
        confirm_reset: Must be True to confirm the destructive operation

    Returns:
        dict: Reset operation result

    Raises:
        DatabaseAdminError: If operation fails or not in development environment
    """
    require_development_environment()

    if not confirm_reset:
        raise DatabaseAdminError(
            "Database reset requires explicit confirmation. "
            "This is a destructive operation that will delete all local data."
        )

    logger.warning(
        "admin_database_reset_initiated",
        user_id=user_id,
        environment=os.getenv("ENVIRONMENT", "production"),
        initiated_by="admin_api",
    )

    # Get metadata service and perform reset
    try:
        metadata_service = get_metadata_service(user_id)
        result = metadata_service.force_reload_from_gcs(confirm_reset=True)

        # Add admin context to result
        result.update(
            {
                "admin_operation": True,
                "environment": os.getenv("ENVIRONMENT", "production"),
                "reset_timestamp": datetime.now().isoformat(),
            }
        )

        logger.info(
            "admin_database_reset_completed",
            **result,
        )

        return result
    except Exception as e:
        logger.error(
            "admin_database_reset_failed",
            user_id=user_id,
            error=str(e),
            environment=os.getenv("ENVIRONMENT", "production"),
        )
        raise DatabaseAdminError(f"Database reset failed: {e}") from e


def get_database_status(user_id: str) -> dict[str, Any]:
    """
    Get database status for a user (development/test only).

    Args:
        user_id: User identifier

    Returns:
        dict: Database status information

    Raises:
        DatabaseAdminError: If operation fails or not in development environment
    """
    require_development_environment()

    try:
        metadata_service = get_metadata_service(user_id)

        # Get database info
        db_info = metadata_service.get_database_info()

        # Get integrity validation
        integrity_result = metadata_service.validate_database_integrity()

        # Combine results
        status = {
            "user_id": user_id,
            "environment": os.getenv("ENVIRONMENT", "production"),
            "database_info": db_info,
            "integrity_validation": integrity_result,
            "status_timestamp": datetime.now().isoformat(),
        }

        logger.info(
            "admin_database_status_retrieved",
            **status,
        )

        return status

    except MetadataError as e:
        logger.error(
            "admin_database_status_failed",
            user_id=user_id,
            error=str(e),
        )
        raise DatabaseAdminError(f"Failed to get database status: {e}") from e
    except Exception as e:
        logger.error(
            "admin_database_status_failed",
            user_id=user_id,
            error=str(e),
        )
        raise DatabaseAdminError(f"Failed to get database status: {e}") from e


def render_database_admin_panel() -> None:
    """Render database administration panel in Streamlit."""
    if not is_development_environment():
        st.error("Database admin panel is only available in development/test environments.")
        return

    st.title("🔧 Database Administration")
    st.warning("⚠️ This panel is for development/testing only. Use with caution!")

    # Get current user
    auth_service = get_auth_service()
    try:
        user = auth_service.ensure_authenticated()
        user_id = user.user_id
    except Exception:
        st.error("Authentication required for database admin operations.")
        return

    # Database status section
    st.header("📊 Database Status")

    if st.button("🔍 Get Database Status"):
        try:
            with st.spinner("Retrieving database status..."):
                status = get_database_status(user_id)

            st.success("Database status retrieved successfully!")

            # Display status information
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Database Info")
                db_info = status["database_info"]
                st.json(db_info)

            with col2:
                st.subheader("Integrity Check")
                integrity = status["integrity_validation"]
                if integrity["valid"]:
                    st.success("✅ Database integrity is valid")
                else:
                    st.error("❌ Database integrity issues found")
                    st.json(integrity["issues"])

        except DatabaseAdminError as e:
            st.error(f"Failed to get database status: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

    # Database reset section
    st.header("🗑️ Database Reset")
    st.error(
        "⚠️ **DANGER ZONE**: Database reset will permanently delete all local data. " "This action cannot be undone!"
    )

    # Confirmation checkbox
    confirm_reset = st.checkbox(
        "I understand this will permanently delete all local data", key="confirm_database_reset"
    )

    # Reset button
    if st.button("🔥 Reset Database", disabled=not confirm_reset, type="primary" if confirm_reset else "secondary"):
        if not confirm_reset:
            st.error("Please confirm that you understand the consequences.")
            return

        try:
            with st.spinner("Resetting database... This may take a few moments."):
                result = reset_user_database(user_id, confirm_reset=True)

            st.success("Database reset completed successfully!")

            # Display reset results
            st.subheader("Reset Results")
            st.json(result)

            # Log user action
            log_user_action(
                user_id=user_id,
                action="database_reset",
                admin_operation=True,
                environment=os.getenv("ENVIRONMENT", "production"),
            )

        except DatabaseAdminError as e:
            st.error(f"Database reset failed: {e}")
        except Exception as e:
            st.error(f"Unexpected error during reset: {e}")

    # Additional information
    st.header("ℹ️ Information")

    with st.expander("What does database reset do?"):
        st.markdown(
            """
        Database reset performs the following actions:

        1. **Deletes local database file** - Removes the local DuckDB file completely
        2. **Downloads from GCS** - Attempts to download database backup from Google Cloud Storage
        3. **Recreates database** - If no GCS backup exists, creates a fresh empty database
        4. **Preserves GCS data** - Your photos and thumbnails in GCS are not affected

        **Use cases:**
        - Corrupted local database
        - Testing database synchronization
        - Starting fresh with clean state
        - Debugging database-related issues
        """
        )

    with st.expander("Environment Information"):
        st.markdown(
            f"""
        - **Environment**: {os.getenv('ENVIRONMENT', 'production')}
        - **User ID**: {user_id}
        - **Admin Panel Available**: {is_development_environment()}
        """
        )
