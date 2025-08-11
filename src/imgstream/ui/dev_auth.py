"""
Development authentication UI for local testing.

This module provides a simple authentication interface for local development
when Cloud IAP is not available.
"""

import os

import streamlit as st

from ..logging_config import get_logger
from ..services.auth import UserInfo, get_auth_service

logger = get_logger(__name__)


def render_dev_auth_ui() -> UserInfo | None:
    """
    Render development authentication UI.

    Returns:
        UserInfo: User information if authenticated, None otherwise
    """
    if not _is_development_mode():
        return None

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔧 開発モード")

    # Check if user is already authenticated in development mode
    auth_service = get_auth_service()
    if auth_service.is_authenticated():
        current_user = auth_service.get_current_user()
        if current_user:
            st.sidebar.success(f"認証済み: {current_user.email}")

            if st.sidebar.button("ログアウト"):
                auth_service.clear_authentication()
                st.rerun()

            return current_user

    # Development authentication form
    st.sidebar.info("ローカル開発用認証")

    with st.sidebar.form("dev_auth_form"):
        email = st.text_input(
            "メールアドレス",
            value=os.getenv("DEV_USER_EMAIL", "developer@example.com"),
            help="開発用のメールアドレスを入力してください",
        )

        user_id = st.text_input(
            "ユーザーID", value=os.getenv("DEV_USER_ID", "dev-local-001"), help="開発用のユーザーIDを入力してください"
        )

        submitted = st.form_submit_button("開発認証でログイン")

        if submitted:
            if email and user_id:
                # Create development user
                dev_user = UserInfo(user_id=user_id, email=email, picture=None)

                # Set authenticated user
                auth_service.set_current_user(dev_user)

                logger.info("development_login", user_id=user_id, email=email)

                st.sidebar.success("開発認証でログインしました")
                st.rerun()
            else:
                st.sidebar.error("メールアドレスとユーザーIDを入力してください")

    return None


def render_dev_auth_info() -> None:
    """Render development authentication information."""
    if not _is_development_mode():
        return

    with st.expander("🔧 開発モード情報", expanded=False):
        st.info(
            """
        **開発モードが有効です**

        このモードでは以下の機能が利用できます：
        - Cloud IAPを使用しない認証
        - 任意のユーザー情報でのログイン
        - 開発用のストレージとデータベース

        **注意**: 本番環境では自動的に無効になります。
        """
        )

        # Show current environment variables
        st.markdown("**環境変数:**")
        env_vars = {
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "未設定"),
            "DEV_USER_EMAIL": os.getenv("DEV_USER_EMAIL", "未設定"),
            "DEV_USER_ID": os.getenv("DEV_USER_ID", "未設定"),
        }

        for key, value in env_vars.items():
            st.text(f"{key}: {value}")


def _is_development_mode() -> bool:
    """Check if running in development mode."""
    environment = os.getenv("ENVIRONMENT", "development").lower()
    return environment in ["development", "dev", "local"]


def setup_dev_auth_middleware() -> None:
    """
    Setup development authentication middleware.

    This function should be called early in the application startup
    to configure development authentication if needed.
    """
    if not _is_development_mode():
        return

    # Add development mode indicator to the page
    st.markdown(
        """
    <div style="
        position: fixed;
        top: 0;
        right: 0;
        background-color: #ff6b6b;
        color: white;
        padding: 5px 10px;
        font-size: 12px;
        z-index: 999;
        border-radius: 0 0 0 5px;
    ">
        🔧 DEV MODE
    </div>
    """,
        unsafe_allow_html=True,
    )

    logger.debug("development_auth_middleware_setup")


# Utility functions for testing


def create_test_user(email: str = "test@example.com", user_id: str = "test-user-001") -> UserInfo:
    """Create a test user for development/testing purposes."""
    return UserInfo(user_id=user_id, email=email, picture=None)


def authenticate_test_user(user: UserInfo | None = None) -> UserInfo:
    """Authenticate a test user for development/testing purposes."""
    if user is None:
        user = create_test_user()

    auth_service = get_auth_service()
    auth_service.set_current_user(user)

    logger.info("test_user_authenticated", user_id=user.user_id, email=user.email)

    return user
