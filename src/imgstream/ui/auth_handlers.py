"""Authentication handlers for imgstream application."""

import streamlit as st
import structlog

from imgstream.services.auth import AuthenticationError, get_auth_service
from imgstream.ui.components import render_error_message
from imgstream.ui.dev_auth import render_dev_auth_ui, setup_dev_auth_middleware, _is_development_mode

logger = structlog.get_logger()


def authenticate_user() -> bool:
    """
    Authenticate user using Cloud IAP headers or development mode.

    Returns:
        bool: True if authentication successful, False otherwise
    """
    try:
        auth_service = get_auth_service()

        # Setup development authentication middleware
        setup_dev_auth_middleware()

        # Check if running in development mode
        if _is_development_mode():
            # Try development authentication first
            dev_user = render_dev_auth_ui()
            if dev_user:
                st.session_state.authenticated = True
                st.session_state.user_id = dev_user.user_id
                st.session_state.user_email = dev_user.email
                st.session_state.auth_error = None
                return True
            else:
                # Development mode but not authenticated yet
                st.session_state.authenticated = False
                st.session_state.auth_error = None
                return False

        # Production mode: use Cloud IAP headers
        headers = {}

        # Try to get IAP header from Streamlit context
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = dict(st.context.headers)
            # debug
            # logger.info(headers)

        # Attempt real authentication
        if auth_service.authenticate_request(headers):
            try:
                user_info = auth_service.ensure_authenticated()
                st.session_state.authenticated = True
                st.session_state.user_id = user_info.user_id
                st.session_state.user_email = user_info.email
                st.session_state.auth_error = None

                logger.info("authentication_success", user_id=user_info.user_id, email=user_info.email)
                return True
            except AuthenticationError:
                # This shouldn't happen if authenticate_request returned True
                pass

        # Authentication failed
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.user_email = None
        st.session_state.auth_error = "Cloud IAP authentication required"

        logger.warning("authentication_failed", reason="no_valid_iap_header")
        return False

    except Exception as e:
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.user_email = None
        st.session_state.auth_error = f"Authentication error: {str(e)}"

        logger.error("authentication_error", error=str(e))
        return False


def handle_logout() -> None:
    """Handle user logout."""
    auth_service = get_auth_service()
    auth_service.clear_authentication()

    # Clear session state
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.auth_error = None
    st.session_state.current_page = "home"

    logger.info("user_logout")
    st.rerun()


def require_authentication() -> bool:
    """
    Require authentication for protected pages with improved error handling.

    Returns:
        bool: True if authenticated, False otherwise
    """
    if not st.session_state.authenticated:
        # Render authentication error with better UX
        render_error_message(
            error_type="認証が必要です",
            message="このページにアクセスするには認証が必要です。",
            details=st.session_state.auth_error if st.session_state.auth_error else None,
        )

        # Quick action to go back to home
        if st.button("🏠 ホームページに戻る", use_container_width=True):
            st.session_state.current_page = "home"
            st.rerun()

        return False

    return True
