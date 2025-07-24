"""
Main Streamlit application for imgstream.

This is the entry point for the photo management web application.
"""

import logging

import streamlit as st
import structlog

from imgstream.services.auth import get_auth_service

# Configure structured logging
logging.basicConfig(level=logging.INFO)
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

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
                auth_service._current_user = user_info

                st.session_state.authenticated = True
                st.session_state.user_id = user_info.user_id
                st.session_state.user_email = user_info.email
                st.session_state.user_name = user_info.name
                st.session_state.auth_error = None

                logger.info("mock_authentication_success", user_id=user_info.user_id, email=user_info.email)
                return True

        # Attempt real authentication
        if auth_service.authenticate_request(headers):
            user_info = auth_service.get_current_user()
            if user_info:
                st.session_state.authenticated = True
                st.session_state.user_id = user_info.user_id
                st.session_state.user_email = user_info.email
                st.session_state.user_name = user_info.name
                st.session_state.auth_error = None

                logger.info("authentication_success", user_id=user_info.user_id, email=user_info.email)
                return True

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
    Require authentication for protected pages.

    Returns:
        bool: True if authenticated, False otherwise
    """
    if not st.session_state.authenticated:
        st.error("🔐 Authentication required to access this page")
        st.info("Please ensure you are accessing this application through Cloud IAP.")

        if st.session_state.auth_error:
            st.error(f"Error: {st.session_state.auth_error}")

        return False

    return True


def initialize_session_state() -> None:
    """Initialize session state variables."""
    # Authentication state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "user_id" not in st.session_state:
        st.session_state.user_id = None

    if "user_email" not in st.session_state:
        st.session_state.user_email = None

    if "user_name" not in st.session_state:
        st.session_state.user_name = None

    if "auth_error" not in st.session_state:
        st.session_state.auth_error = None

    # Application state
    if "current_page" not in st.session_state:
        st.session_state.current_page = "home"

    if "photos_loaded" not in st.session_state:
        st.session_state.photos_loaded = False

    if "upload_in_progress" not in st.session_state:
        st.session_state.upload_in_progress = False


def render_header() -> None:
    """Render the application header."""
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.title("📸 imgstream")
        st.markdown("*Personal Photo Management*")


def render_sidebar() -> None:
    """Render the application sidebar."""
    with st.sidebar:
        st.header("Navigation")

        # Navigation menu
        pages = {"🏠 Home": "home", "📤 Upload": "upload", "🖼️ Gallery": "gallery", "⚙️ Settings": "settings"}

        for page_name, page_key in pages.items():
            if st.button(page_name, key=f"nav_{page_key}", use_container_width=True):
                logger.info("page_navigation", from_page=st.session_state.current_page, to_page=page_key)
                st.session_state.current_page = page_key
                st.rerun()

        st.divider()

        # User info section
        if st.session_state.authenticated:
            st.subheader("User Info")
            st.write(f"**Name:** {st.session_state.user_name or 'Unknown'}")
            st.write(f"**Email:** {st.session_state.user_email or 'Unknown'}")
            if st.secrets.get("debug", False):
                st.write(f"**User ID:** {st.session_state.user_id or 'Unknown'}")

            # Logout button
            if st.button("🚪 Logout", use_container_width=True):
                handle_logout()
        else:
            st.info("Not authenticated")
            if st.session_state.auth_error:
                st.error(f"Authentication Error: {st.session_state.auth_error}")


def render_home_page() -> None:
    """Render the home page."""
    st.header("Welcome to imgstream")

    if not st.session_state.authenticated:
        st.warning("🔐 Please authenticate to access your photos")
        st.markdown(
            """
        ### Getting Started
        1. **Authentication**: This app uses Cloud IAP for secure authentication
        2. **Upload Photos**: Support for HEIC and JPEG formats
        3. **View Gallery**: Browse your photos in chronological order
        4. **Secure Storage**: Photos are stored securely in Google Cloud Storage
        """
        )
    else:
        st.success(f"✅ Welcome back, {st.session_state.user_email}!")

        # Quick stats (placeholder)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Photos", "0", help="Total number of uploaded photos")
        with col2:
            st.metric("Storage Used", "0 MB", help="Total storage space used")
        with col3:
            st.metric("Recent Uploads", "0", help="Photos uploaded this week")

        st.markdown("---")
        st.markdown("### Quick Actions")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Upload Photos", use_container_width=True):
                st.session_state.current_page = "upload"
                st.rerun()

        with col2:
            if st.button("🖼️ View Gallery", use_container_width=True):
                st.session_state.current_page = "gallery"
                st.rerun()


def render_upload_page() -> None:
    """Render the upload page."""
    st.header("📤 Upload Photos")

    if not require_authentication():
        return

    st.info("🚧 Upload functionality will be implemented in a later task")

    # Placeholder upload interface
    st.markdown("### Supported Formats")
    st.write("- HEIC (iPhone photos)")
    st.write("- JPEG/JPG")

    # File uploader placeholder
    st.file_uploader(
        "Choose photos to upload",
        type=["heic", "jpg", "jpeg"],
        accept_multiple_files=True,
        disabled=True,
        help="File upload will be enabled in the next development phase",
    )


def render_gallery_page() -> None:
    """Render the gallery page."""
    st.header("🖼️ Photo Gallery")

    if not require_authentication():
        return

    st.info("🚧 Gallery functionality will be implemented in a later task")

    # Placeholder gallery interface
    st.markdown("### Your Photos")
    st.write("Photos will be displayed here in chronological order")

    # Placeholder for photo grid
    st.empty()


def render_settings_page() -> None:
    """Render the settings page."""
    st.header("⚙️ Settings")

    if not require_authentication():
        return

    st.info("🚧 Settings functionality will be implemented in a later task")

    # Placeholder settings
    st.markdown("### Application Settings")
    st.checkbox("Enable notifications", disabled=True)
    st.selectbox("Theme", ["Light", "Dark"], disabled=True)
    st.slider("Photos per page", 10, 100, 50, disabled=True)


def render_main_content() -> None:
    """Render the main content area based on current page."""
    current_page = st.session_state.current_page

    if current_page == "home":
        render_home_page()
    elif current_page == "upload":
        render_upload_page()
    elif current_page == "gallery":
        render_gallery_page()
    elif current_page == "settings":
        render_settings_page()
    else:
        st.error(f"Unknown page: {current_page}")


def render_footer() -> None:
    """Render the application footer."""
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.8em;'>
            imgstream - Personal Photo Management |
            Powered by Streamlit & Google Cloud
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Main application entry point."""
    logger.info("application_starting", page="main")

    # Configure Streamlit page
    st.set_page_config(
        page_title="imgstream - Photo Management",
        page_icon="📸",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get Help": None,
            "Report a bug": None,
            "About": "imgstream - Personal Photo Management Application",
        },
    )

    # Initialize session state
    initialize_session_state()

    # Attempt authentication
    authenticate_user()

    logger.info(
        "session_initialized",
        authenticated=st.session_state.authenticated,
        current_page=st.session_state.current_page,
        user_email=st.session_state.user_email,
    )

    # Render application layout
    render_header()
    render_sidebar()

    # Main content area
    with st.container():
        render_main_content()

    # Footer
    render_footer()

    # Debug info (only in development)
    if st.secrets.get("debug", False):
        with st.expander("Debug Info"):
            st.write("Session State:", st.session_state)


if __name__ == "__main__":
    main()
