"""Authentication handlers for imgstream application."""

import os

import streamlit as st
import structlog

from imgstream.services.auth import AuthenticationError, get_auth_service
from imgstream.ui.components import render_error_message
from imgstream.ui.dev_auth import render_dev_auth_ui, setup_dev_auth_middleware

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
            show_retry=True,
        )

        # Provide helpful guidance
        # render_info_card(
        #     "認証方法",
        #     "このアプリケーションはGoogle Cloud Identity-Aware Proxy (IAP)を使用しています。"
        #     "正しいURLからアプリケーションにアクセスし、"
        #     "認証されたGoogleアカウントでサインインしていることを確認してください。",
        #     "💡",
        # )

        # Quick action to go back to home
        if st.button("🏠 ホームページに戻る", use_container_width=True):
            st.session_state.current_page = "home"
            st.rerun()

        return False

    return True


def render_sidebar() -> None:
    """Render the application sidebar with improved navigation and layout."""
    with st.sidebar:
        # App branding in sidebar
        st.markdown("### 📸 imgstream")
        st.divider()

        # Navigation menu with current page highlighting
        st.subheader("ナビゲーション")
        pages = {"🏠 ホーム": "home", "📤 アップロード": "upload", "🖼️ ギャラリー": "gallery", "⚙️ 設定": "settings"}

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
            # st.subheader("👤 ユーザープロフィール")

            # User avatar placeholder
            st.markdown("🔵")  # Placeholder for user avatar

            # User information
            user_email = st.session_state.user_email or "unknown@example.com"

            st.markdown(f"📧 {user_email}")

            from ..config import get_config

            config = get_config()
            if config.get("debug", False, bool):
                st.markdown(f"🆔 {st.session_state.user_id or '不明'}")

            st.divider()

            # Quick stats in sidebar
            st.markdown("**📊 クイック統計**")
            st.markdown("📷 写真: 0")
            st.markdown("💾 ストレージ: 0 MB")
            st.markdown("📅 最終アップロード: なし")

            st.divider()

            # Database Admin section (development only)
            if _is_development_mode():
                st.markdown("**🔧 開発ツール**")

                if st.button("🗄️ データベース管理", use_container_width=True, help="データベース管理（開発専用）"):
                    st.session_state.current_page = "database_admin"
                    st.rerun()

                st.divider()

            # Logout button
            # if st.button("🚪 ログアウト", use_container_width=True, type="secondary"):
            #     handle_logout()
        else:
            st.subheader("🔐 認証")
            st.info("写真にアクセスするには認証してください")

            if st.session_state.auth_error:
                st.error(f"**エラー:** {st.session_state.auth_error}")


def _is_development_mode() -> bool:
    """Check if running in development mode."""
    environment = os.getenv("ENVIRONMENT", "production").lower()
    return environment in ["development", "dev", "local", "test", "testing"]
