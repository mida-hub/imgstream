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


def render_empty_state(
    title: str, description: str, icon: str = "📭", action_text: str | None = None, action_page: str | None = None
) -> None:
    """
    Render an empty state message with optional action button.

    Args:
        title: Main title for the empty state
        description: Description text
        icon: Emoji icon to display
        action_text: Text for action button (optional)
        action_page: Page to navigate to when action button is clicked (optional)
    """
    # Center the empty state content
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            f"""
        <div style='text-align: center; padding: 2rem 0;'>
            <div style='font-size: 4rem; margin-bottom: 1rem;'>{icon}</div>
            <h3 style='color: #666; margin-bottom: 1rem;'>{title}</h3>
            <p style='color: #888; margin-bottom: 2rem;'>{description}</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Optional action button
        if action_text and action_page:
            if st.button(action_text, use_container_width=True, type="primary"):
                st.session_state.current_page = action_page
                st.rerun()


def render_error_message(error_type: str, message: str, details: str | None = None, show_retry: bool = False) -> None:
    """
    Render a standardized error message.

    Args:
        error_type: Type of error (e.g., "Authentication Error", "Upload Error")
        message: Main error message
        details: Additional error details (optional)
        show_retry: Whether to show a retry button (optional)
    """
    st.error(f"**{error_type}:** {message}")

    if details:
        with st.expander("🔍 Error Details"):
            st.code(details)

    if show_retry:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔄 Retry", use_container_width=True):
                st.rerun()


def render_info_card(title: str, content: str, icon: str = "ℹ️") -> None:
    """
    Render an information card.

    Args:
        title: Card title
        content: Card content
        icon: Icon to display
    """
    st.markdown(
        f"""
    <div style='
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        background-color: #f8f9fa;
    '>
        <h4 style='margin: 0 0 0.5rem 0; color: #333;'>
            {icon} {title}
        </h4>
        <p style='margin: 0; color: #666;'>
            {content}
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )


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
    """Render the application header with improved layout."""
    # Main header with breadcrumb navigation
    col1, col2, col3 = st.columns([2, 3, 2])

    with col1:
        # App logo and title
        st.markdown("# 📸 imgstream")

    with col2:
        # Breadcrumb navigation
        current_page = st.session_state.current_page
        page_titles = {"home": "Home", "upload": "Upload Photos", "gallery": "Photo Gallery", "settings": "Settings"}

        if current_page in page_titles:
            st.markdown(f"### {page_titles[current_page]}")

    with col3:
        # Status indicators
        if st.session_state.authenticated:
            st.success("🟢 Authenticated")
        else:
            st.error("🔴 Not Authenticated")

    # Subtitle and divider
    st.markdown("*Personal Photo Management with Cloud Storage*")
    st.divider()


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


def render_home_page() -> None:
    """Render the home page with improved layout and empty states."""
    if not st.session_state.authenticated:
        # Unauthenticated state
        render_empty_state(
            title="Authentication Required",
            description="Please authenticate with Cloud IAP to access your personal photo collection.",
            icon="🔐",
        )

        # Getting started information
        render_info_card(
            "Getting Started",
            "This app uses Cloud IAP for secure authentication. Upload HEIC and JPEG photos, "
            "browse your gallery in chronological order, and store photos securely in Google Cloud Storage.",
            "🚀",
        )

        # Feature highlights
        col1, col2, col3 = st.columns(3)

        with col1:
            render_info_card(
                "Secure Authentication", "Cloud IAP ensures only authorized users can access their photos.", "🔒"
            )

        with col2:
            render_info_card("Smart Storage", "Automatic lifecycle management optimizes storage costs over time.", "💾")

        with col3:
            render_info_card("Fast Browsing", "Thumbnail-based interface for quick photo discovery and viewing.", "⚡")
    else:
        # Authenticated user dashboard
        user_name = st.session_state.user_name or "User"
        st.markdown(f"## Welcome back, {user_name}! 👋")

        # Quick stats dashboard
        st.markdown("### 📊 Your Photo Library")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Photos", "0", help="Total number of uploaded photos")
        with col2:
            st.metric("Storage Used", "0 MB", help="Total storage space used")
        with col3:
            st.metric("Recent Uploads", "0", help="Photos uploaded this week")
        with col4:
            st.metric("Last Activity", "Never", help="Last time you uploaded photos")

        st.divider()

        # Quick actions section
        st.markdown("### ⚡ Quick Actions")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📤 Upload New Photos", use_container_width=True, type="primary"):
                st.session_state.current_page = "upload"
                st.rerun()

        with col2:
            if st.button("🖼️ Browse Gallery", use_container_width=True):
                st.session_state.current_page = "gallery"
                st.rerun()

        with col3:
            if st.button("⚙️ Manage Settings", use_container_width=True):
                st.session_state.current_page = "settings"
                st.rerun()

        st.divider()

        # Recent activity section (empty state for now)
        st.markdown("### 📅 Recent Activity")
        render_empty_state(
            title="No Recent Activity",
            description="Your recent photo uploads and activities will appear here.",
            icon="📭",
            action_text="Upload Your First Photo",
            action_page="upload",
        )


def render_upload_page() -> None:
    """Render the upload page with improved layout and information."""
    if not require_authentication():
        return

    # Development notice
    st.info("🚧 Upload functionality will be implemented in a later task")

    # Upload area with drag-and-drop styling
    st.markdown("### 📤 Upload Your Photos")

    # File format information
    col1, col2 = st.columns([1, 1])

    with col1:
        render_info_card(
            "Supported Formats",
            "• HEIC (iPhone/iPad photos)\n• JPEG/JPG (Standard photos)\n• Maximum file size: 50MB per photo",
            "📋",
        )

    with col2:
        render_info_card(
            "Smart Processing", "• Automatic EXIF data extraction\n• Thumbnail generation\n• Secure cloud storage", "⚙️"
        )

    # File uploader placeholder with better styling
    st.markdown("#### Choose Photos to Upload")

    uploaded_files = st.file_uploader(
        "Drag and drop photos here, or click to browse",
        type=["heic", "jpg", "jpeg"],
        accept_multiple_files=True,
        disabled=True,
        help="File upload will be enabled in the next development phase",
    )

    # Upload progress placeholder
    if uploaded_files:
        st.markdown("#### Upload Progress")
        st.progress(0)
        st.write("Processing photos...")

    # Upload tips
    with st.expander("💡 Upload Tips"):
        st.markdown(
            """
        **For Best Results:**

        - 📱 **iPhone Users**: HEIC format is fully supported
        - 📷 **Camera Photos**: EXIF data will be preserved for date sorting
        - 🗂️ **Batch Upload**: Select multiple photos at once
        - 📶 **Connection**: Ensure stable internet for large uploads
        - 💾 **Storage**: Photos are automatically organized by date
        - 🔒 **Privacy**: All uploads are private to your account
        """
        )

    # Storage information
    st.divider()
    st.markdown("### 💾 Storage Information")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Available Storage", "Unlimited*", help="Subject to GCP quotas")
    with col2:
        st.metric("Current Usage", "0 MB", help="Total storage used")
    with col3:
        st.metric("Photos Uploaded", "0", help="Total number of photos")


def render_gallery_page() -> None:
    """Render the gallery page with empty state and layout."""
    if not require_authentication():
        return

    # Gallery controls
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown("### 🖼️ Your Photo Collection")

    with col2:
        st.selectbox("View", ["Grid", "List"], disabled=True)

    with col3:
        st.selectbox("Sort by", ["Newest First", "Oldest First"], disabled=True)

    st.divider()

    # Development notice
    st.info("🚧 Gallery functionality will be implemented in a later task")

    # Empty state for photos
    render_empty_state(
        title="No Photos Yet",
        description="Your photo collection is empty. Upload some photos to get started!",
        icon="📷",
        action_text="Upload Photos",
        action_page="upload",
    )

    # Placeholder for future gallery features
    with st.expander("🔮 Coming Soon"):
        st.markdown(
            """
        **Gallery Features in Development:**

        - 📅 **Chronological View**: Photos sorted by creation date
        - 🔍 **Search & Filter**: Find photos by date, name, or metadata
        - 🖼️ **Thumbnail Grid**: Fast browsing with optimized thumbnails
        - 🔍 **Full-Size Preview**: Click to view original images
        - 📱 **Responsive Layout**: Works on desktop and mobile
        - 🏷️ **Smart Organization**: Automatic grouping by date and location
        """
        )


def render_settings_page() -> None:
    """Render the settings page with organized sections."""
    if not require_authentication():
        return

    # Development notice
    st.info("🚧 Settings functionality will be implemented in a later task")

    # Settings sections
    st.markdown("### ⚙️ Application Settings")

    # Account settings
    with st.expander("👤 Account Settings", expanded=True):
        st.markdown("**Profile Information**")

        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Display Name", value=st.session_state.user_name or "", disabled=True)
        with col2:
            st.text_input("Email", value=st.session_state.user_email or "", disabled=True)

        st.markdown("**Account Actions**")
        col1, col2 = st.columns(2)
        with col1:
            st.button("🔄 Refresh Profile", disabled=True)
        with col2:
            st.button("📧 Update Email Preferences", disabled=True)

    # Display settings
    with st.expander("🎨 Display Settings"):
        st.markdown("**Appearance**")
        st.selectbox("Theme", ["Light", "Dark", "Auto"], disabled=True)
        st.selectbox("Language", ["English", "日本語"], disabled=True)

        st.markdown("**Gallery View**")
        st.slider("Photos per page", 10, 100, 50, disabled=True)
        st.selectbox("Default sort order", ["Newest First", "Oldest First"], disabled=True)

    # Notification settings
    with st.expander("🔔 Notification Settings"):
        st.checkbox("Enable upload notifications", disabled=True)
        st.checkbox("Enable storage alerts", disabled=True)
        st.checkbox("Enable weekly summary", disabled=True)

    # Privacy and security
    with st.expander("🔒 Privacy & Security"):
        st.markdown("**Data Management**")
        st.button("📊 Download My Data", disabled=True)
        st.button("🗑️ Delete All Photos", disabled=True, type="secondary")

        st.markdown("**Security**")
        st.write("Authentication: Cloud IAP ✅")
        st.write("Data Encryption: Enabled ✅")
        st.write("Access Logs: Available ✅")

    # Storage settings
    with st.expander("💾 Storage Settings"):
        st.markdown("**Storage Management**")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Storage Used", "0 MB")
            st.metric("Number of Photos", "0")
        with col2:
            st.metric("Thumbnail Storage", "0 MB")
            st.metric("Original Photos", "0 MB")

        st.markdown("**Lifecycle Settings**")
        st.info("Original photos automatically move to Coldline storage after 30 days to reduce costs.")

        st.button("🧹 Optimize Storage", disabled=True)

    # Advanced settings
    with st.expander("🔧 Advanced Settings"):
        st.markdown("**Debug Information**")
        if st.secrets.get("debug", False):
            st.json(
                {
                    "user_id": st.session_state.user_id,
                    "authenticated": st.session_state.authenticated,
                    "current_page": st.session_state.current_page,
                    "session_keys": list(st.session_state.keys()),
                }
            )
        else:
            st.info("Debug mode is disabled")

        st.markdown("**System Information**")
        st.write("Application Version: 0.1.0")
        st.write("Last Updated: Development Build")
        st.write("Region: asia-northeast1")


def render_main_content() -> None:
    """Render the main content area based on current page with error handling."""
    current_page = st.session_state.current_page

    try:
        if current_page == "home":
            render_home_page()
        elif current_page == "upload":
            render_upload_page()
        elif current_page == "gallery":
            render_gallery_page()
        elif current_page == "settings":
            render_settings_page()
        else:
            # Handle unknown page with better error message
            render_error_message(
                error_type="Page Not Found",
                message=f"The page '{current_page}' does not exist.",
                details="Available pages: home, upload, gallery, settings",
                show_retry=False,
            )

            # Provide navigation back to home
            if st.button("🏠 Return to Home", use_container_width=True, type="primary"):
                st.session_state.current_page = "home"
                st.rerun()

    except Exception as e:
        # Handle any unexpected errors in page rendering
        logger.error("page_render_error", page=current_page, error=str(e))

        render_error_message(
            error_type="Page Rendering Error",
            message="An unexpected error occurred while loading this page.",
            details=str(e),
            show_retry=True,
        )

        # Provide fallback navigation
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏠 Go to Home", use_container_width=True):
                st.session_state.current_page = "home"
                st.rerun()
        with col2:
            if st.button("🔄 Reload Page", use_container_width=True):
                st.rerun()


def render_footer() -> None:
    """Render the application footer with improved layout and information."""
    st.divider()

    # Footer content in columns
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        st.markdown(
            """
        <div style='text-align: left; color: #666; font-size: 0.8em;'>
            <strong>imgstream</strong><br>
            Version 0.1.0
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
        <div style='text-align: center; color: #666; font-size: 0.8em;'>
            Personal Photo Management<br>
            Powered by Streamlit & Google Cloud Platform
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
        <div style='text-align: right; color: #666; font-size: 0.8em;'>
            🌏 asia-northeast1<br>
            🔒 Secure & Private
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Additional footer information
    st.markdown(
        """
    <div style='text-align: center; color: #888; font-size: 0.7em; margin-top: 1rem;'>
        Built with ❤️ for personal photo management |
        Data stored securely in Google Cloud Storage |
        Authenticated via Cloud IAP
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
