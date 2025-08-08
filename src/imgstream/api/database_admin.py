"""Database administration endpoints for development and testing."""

import os
from typing import Any, Dict

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


def reset_user_database(user_id: str, confirm_reset: bool = False) -> Dict[str, Any]:
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
    
    try:
        logger.warning(
            "admin_database_reset_initiated",
            user_id=user_id,
            environment=os.getenv("ENVIRONMENT", "production"),
            initiated_by="admin_api",
        )
        
        # Get metadata service and perform reset
        metadata_service = get_metadata_service(user_id)
        result = metadata_service.force_reload_from_gcs(confirm_reset=True)
        
        # Add admin context to result
        result.update({
            "admin_operation": True,
            "environment": os.getenv("ENVIRONMENT", "production"),
            "reset_timestamp": datetime.now().isoformat(),
        })
        
        logger.info(
            "admin_database_reset_completed",
            **result,
        )
        
        return result
        
    except MetadataError as e:
        logger.error(
            "admin_database_reset_failed",
            user_id=user_id,
            error=str(e),
        )
        raise DatabaseAdminError(f"Database reset failed: {e}") from e


def get_database_status(user_id: str) -> Dict[str, Any]:
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


def validate_all_user_databases() -> Dict[str, Any]:
    """
    Validate integrity of all user databases (development/test only).
    
    Returns:
        dict: Validation results for all users
        
    Raises:
        DatabaseAdminError: If operation fails or not in development environment
    """
    require_development_environment()
    
    try:
        # This is a simplified implementation
        # In a real system, you'd need to discover all user databases
        logger.info("admin_database_validation_all_started")
        
        # For now, return a placeholder result
        # In practice, you'd iterate through all known users
        result = {
            "operation": "validate_all_databases",
            "environment": os.getenv("ENVIRONMENT", "production"),
            "validation_timestamp": datetime.now().isoformat(),
            "total_users": 0,
            "valid_databases": 0,
            "invalid_databases": 0,
            "validation_errors": [],
            "message": "Bulk validation not implemented - use individual user validation",
        }
        
        logger.info(
            "admin_database_validation_all_completed",
            **result,
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "admin_database_validation_all_failed",
            error=str(e),
        )
        raise DatabaseAdminError(f"Bulk database validation failed: {e}") from e


# Streamlit UI components for database administration

def render_database_admin_panel() -> None:
    """Render database administration panel in Streamlit."""
    if not is_development_environment():
        st.error(
            f"🚫 Database admin panel is only available in development environments. "
            f"Current environment: {os.getenv('ENVIRONMENT', 'production')}"
        )
        return
    
    st.title("🔧 Database Administration")
    st.warning(
        "⚠️ **Development Environment Only** - These operations can be destructive!"
    )
    
    # Environment info
    with st.expander("🌍 Environment Information", expanded=False):
        st.info(f"**Environment:** {os.getenv('ENVIRONMENT', 'production')}")
        st.info(f"**Admin Panel Available:** {is_development_environment()}")
    
    # User selection
    st.subheader("👤 User Selection")
    
    # Get current user if authenticated
    try:
        auth_service = get_auth_service()
        current_user = auth_service.get_current_user()
        default_user_id = current_user.user_id if current_user else ""
    except Exception:
        default_user_id = ""
    
    user_id = st.text_input(
        "User ID",
        value=default_user_id,
        help="Enter the user ID for database operations",
    )
    
    if not user_id:
        st.warning("Please enter a user ID to proceed.")
        return
    
    # Database status section
    st.subheader("📊 Database Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 Get Database Status", use_container_width=True):
            try:
                with st.spinner("Retrieving database status..."):
                    status = get_database_status(user_id)
                
                st.success("✅ Database status retrieved successfully!")
                
                # Display database info
                db_info = status["database_info"]
                st.json(db_info)
                
                # Display integrity validation
                integrity = status["integrity_validation"]
                if integrity["valid"]:
                    st.success("✅ Database integrity validation passed")
                else:
                    st.error("❌ Database integrity issues found:")
                    for issue in integrity["issues"]:
                        st.error(f"• {issue}")
                
            except DatabaseAdminError as e:
                st.error(f"❌ Failed to get database status: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")
    
    with col2:
        if st.button("🔍 Validate Database Integrity", use_container_width=True):
            try:
                with st.spinner("Validating database integrity..."):
                    metadata_service = get_metadata_service(user_id)
                    integrity_result = metadata_service.validate_database_integrity()
                
                if integrity_result["valid"]:
                    st.success("✅ Database integrity validation passed!")
                    st.info(f"Validation completed in {integrity_result['validation_duration_seconds']:.2f} seconds")
                else:
                    st.error("❌ Database integrity issues found:")
                    for issue in integrity_result["issues"]:
                        st.error(f"• {issue}")
                
            except (DatabaseAdminError, MetadataError) as e:
                st.error(f"❌ Validation failed: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")
    
    # Database reset section
    st.subheader("🔄 Database Reset")
    st.warning(
        "⚠️ **DESTRUCTIVE OPERATION** - This will delete the local database and reload from GCS!"
    )
    
    # Safety confirmation
    confirm_reset = st.checkbox(
        "I understand this is a destructive operation and will delete all local data",
        help="You must check this box to enable the reset button",
    )
    
    if st.button(
        "🔄 Reset Database",
        disabled=not confirm_reset,
        use_container_width=True,
        type="primary" if confirm_reset else "secondary",
    ):
        if not confirm_reset:
            st.error("❌ Please confirm the destructive operation first.")
            return
        
        try:
            with st.spinner("Resetting database... This may take a moment."):
                result = reset_user_database(user_id, confirm_reset=True)
            
            # Show appropriate message based on result
            if result.get('data_loss_risk', False):
                st.warning("⚠️ Database reset completed with data loss risk!")
                st.error("🚨 **WARNING**: No GCS backup was found. A new empty database was created.")
            else:
                st.success("✅ Database reset completed successfully!")
            
            # Display reset results
            st.json(result)
            
            # Show summary
            st.info(f"**Reset Duration:** {result['reset_duration_seconds']:.2f} seconds")
            st.info(f"**Local DB Deleted:** {'Yes' if result['local_db_deleted'] else 'No'}")
            
            # Color-coded GCS status
            if result['gcs_database_exists']:
                st.success(f"**GCS DB Exists:** Yes")
            else:
                st.error(f"**GCS DB Exists:** No - Data loss risk!")
            
            # Color-coded download status
            if result['download_successful']:
                st.success(f"**Download Successful:** Yes")
            elif result['gcs_database_exists']:
                st.error(f"**Download Successful:** No - Download failed!")
            else:
                st.warning(f"**Download Successful:** No - No backup to download")
            
        except DatabaseAdminError as e:
            st.error(f"❌ Database reset failed: {e}")
        except Exception as e:
            st.error(f"❌ Unexpected error during reset: {e}")
    
    # Bulk operations section
    st.subheader("🔧 Bulk Operations")
    
    if st.button("🔍 Validate All Databases", use_container_width=True):
        try:
            with st.spinner("Validating all user databases..."):
                result = validate_all_user_databases()
            
            st.info("ℹ️ Bulk validation completed")
            st.json(result)
            
        except DatabaseAdminError as e:
            st.error(f"❌ Bulk validation failed: {e}")
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")


def create_database_admin_page() -> None:
    """Create a standalone database admin page."""
    st.set_page_config(
        page_title="Database Admin",
        page_icon="🔧",
        layout="wide",
    )
    
    render_database_admin_panel()


if __name__ == "__main__":
    create_database_admin_page()
