"""
Main Streamlit application for imgstream.

This is the entry point for the photo management web application.
"""

import logging

import streamlit as st
import structlog

from imgstream.ui.auth_handlers import authenticate_user, render_sidebar
from imgstream.ui.components import render_error_message, render_footer, render_header
from imgstream.ui.pages.gallery import render_gallery_page
from imgstream.ui.pages.home import render_home_page
from imgstream.ui.pages.settings import render_settings_page
from imgstream.ui.pages.upload import render_upload_page

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
