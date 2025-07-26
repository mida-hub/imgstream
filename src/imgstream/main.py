"""
Main Streamlit application for imgstream.

This is the entry point for the photo management web application.
"""

import streamlit as st

from imgstream.logging_config import configure_structured_logging, get_logger
from imgstream.ui.auth_handlers import authenticate_user, render_sidebar
from imgstream.ui.components import render_error_message, render_footer, render_header
from imgstream.ui.error_display import error_context, get_error_display_manager
from imgstream.ui.pages.gallery import render_gallery_page
from imgstream.ui.pages.home import render_home_page
from imgstream.ui.pages.settings import render_settings_page
from imgstream.ui.pages.upload import render_upload_page

# Configure structured logging
configure_structured_logging()
logger = get_logger(__name__)
error_display = get_error_display_manager()


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

    with error_context(f"ページ '{current_page}' の読み込み中にエラーが発生しました"):
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
            error_display.display_error_message(
                f"ページ '{current_page}' が見つかりません。"
            )
            
            # Provide navigation back to home
            if st.button("🏠 ホームに戻る", use_container_width=True, type="primary"):
                st.session_state.current_page = "home"
                st.rerun()


def main() -> None:
    """Main application entry point."""
    logger.info("application_starting", page="main")

    try:
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

        # Attempt authentication with error handling
        with error_context("認証処理中にエラーが発生しました"):
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

    except Exception as e:
        # Handle critical application errors
        logger.error("critical_application_error", error=str(e))
        error_display.display_exception(
            e,
            context={"operation": "main_application"},
            show_details=True
        )
        
        # Provide basic recovery options
        if st.button("🔄 アプリケーションを再起動", type="primary"):
            st.rerun()


if __name__ == "__main__":
    main()
