"""Authentication handlers for imgstream application."""

import streamlit as st
import structlog

from imgstream.services.auth import AuthenticationError, get_auth_service
from imgstream.ui.components import render_error_message, render_info_card

logger = structlog.get_logger()


def authenticate_user() -> bool:
    """
    Authenticate user using Cloud IAP headers.

    Returns:
        bool: True if authentication successful, False otherwise
    """
    try:
        auth_service = get_auth_service()

        # In production, headers would come from the request
        # For development/testing, we can simulate headers or use environment variables
        headers = {}

        # Try to get IAP header from Streamlit context
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = dict(st.context.headers)

        # For development, check if we have a mock user in secrets
        if not headers.get(auth_service.IAP_HEADER_NAME) and st.secrets.get("mock_user"):
            mock_user = st.secrets.get("mock_user", {})
            if mock_user.get("enabled", False):
                # Create a mock user for development
                from imgstream.services.auth import UserInfo

                user_info = UserInfo(
                    user_id=mock_user.get("user_id", "dev_user_123"),
                    email=mock_user.get("email", "dev@example.com"),
                    name=mock_user.get("name", "Development User"),
                    picture=mock_user.get("picture"),
                )
                # Set the mock user directly (for development only)
                auth_service.set_current_user(user_info)

                st.session_state.authenticated = True
                st.session_state.user_id = user_info.user_id
                st.session_state.user_email = user_info.email
                st.session_state.user_name = user_info.name
                st.session_state.auth_error = None

                logger.info("mock_authentication_success", user_id=user_info.user_id, email=user_info.email)
                return True

        # Attempt real authentication
        if auth_service.authenticate_request(headers):
            try:
                user_info = auth_service.ensure_authenticated()
                st.session_state.authenticated = True
                st.session_state.user_id = user_info.user_id
                st.session_state.user_email = user_info.email
                st.session_state.user_name = user_info.name
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
        st.session_state.user_name = None
        st.session_state.auth_error = "Cloud IAP authentication required"

        logger.warning("authentication_failed", reason="no_valid_iap_header")
        return False

    except Exception as e:
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.user_email = None
        st.session_state.user_name = None
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
    st.session_state.user_name = None
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
            error_type="Authentication Required",
            message="You must be authenticated to access this page.",
            details=st.session_state.auth_error if st.session_state.auth_error else None,
            show_retry=True,
        )

        # Provide helpful guidance
        render_info_card(
            "How to Authenticate",
            "This application uses Google Cloud Identity-Aware Proxy (IAP). "
            "Please ensure you're accessing the application through the correct URL and "
            "have signed in with your authorized Google account.",
            "💡",
        )

        # Quick action to go back to home
        if st.button("🏠 Go to Home Page", use_container_width=True):
            st.session_state.current_page = "home"
            st.rerun()

        return False

    return True


def render_sidebar() -> None:
    """Render the application sidebar with improved navigation and layout."""
    with st.sidebar:
        # App branding in sidebar
        st.markdown("### 📸 imgstream")
        st.markdown("*Personal Photo Management*")
        st.divider()

        # Navigation menu with current page highlighting
        st.subheader("Navigation")
        pages = {"🏠 Home": "home", "📤 Upload": "upload", "🖼️ Gallery": "gallery", "⚙️ Settings": "settings"}

        current_page = st.session_state.current_page

        for page_name, page_key in pages.items():
            # Highlight current page
            is_current = page_key == current_page

            if st.button(
                page_name,
                key=f"nav_{page_key}",
                use_container_width=True,
                type="primary" if is_current else "secondary",
            ):
                logger.info("page_navigation", from_page=current_page, to_page=page_key)
                st.session_state.current_page = page_key
                st.rerun()

        st.divider()

        # User info section with improved layout
        if st.session_state.authenticated:
            st.subheader("👤 User Profile")

            # User avatar placeholder
            st.markdown("🔵")  # Placeholder for user avatar

            # User information
            user_name = st.session_state.user_name or "Unknown User"
            user_email = st.session_state.user_email or "unknown@example.com"

            st.markdown(f"**{user_name}**")
            st.markdown(f"📧 {user_email}")

            if st.secrets.get("debug", False):
                st.markdown(f"🆔 {st.session_state.user_id or 'Unknown'}")

            st.divider()

            # Quick stats in sidebar
            st.markdown("**📊 Quick Stats**")
            st.markdown("📷 Photos: 0")
            st.markdown("💾 Storage: 0 MB")
            st.markdown("📅 Last upload: Never")

            st.divider()

            # Logout button
            if st.button("🚪 Logout", use_container_width=True, type="secondary"):
                handle_logout()
        else:
            st.subheader("🔐 Authentication")
            st.info("Please authenticate to access your photos")

            if st.session_state.auth_error:
                st.error(f"**Error:** {st.session_state.auth_error}")

            # Help information for unauthenticated users
            with st.expander("ℹ️ How to authenticate"):
                st.markdown(
                    """
                **Cloud IAP Authentication**

                This application uses Google Cloud Identity-Aware Proxy (IAP) for secure authentication.

                **Steps:**
                1. Ensure you're accessing through the correct URL
                2. Sign in with your Google account
                3. Wait for authentication to complete

                **Troubleshooting:**
                - Clear browser cookies and try again
                - Check if you have the required permissions
                - Contact your administrator if issues persist
                """
                )
