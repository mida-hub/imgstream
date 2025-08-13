"""Reusable UI components for imgstream application."""

import streamlit as st
import structlog

logger = structlog.get_logger()


def render_empty_state(
    title: str,
    description: str,
    icon: str = "📭",
    action_text: str | None = None,
    action_page: str | None = None,
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


def render_error_message(error_type: str, message: str, details: str | None = None) -> None:
    """
    Render a standardized error message.

    Args:
        error_type: Type of error (e.g., "Authentication Error", "Upload Error")
        message: Main error message
        details: Additional error details (optional)
    """
    st.error(f"**{error_type}:** {message}")

    if details:
        with st.expander("🔍 エラー詳細"):
            st.code(details)


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


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        str: Formatted file size (e.g., "1.5 MB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def render_header() -> None:
    """Render the application header with improved layout."""

    # App logo and title
    st.markdown("# 📸 imgstream")

    # Subtitle and divider
    st.divider()


def render_sidebar() -> None:
    """Render the application sidebar with improved navigation and layout."""
    with st.sidebar:
        # App branding in sidebar
        st.markdown("### 📸 imgstream")
        st.divider()

        # Navigation menu with current page highlighting
        st.subheader("ナビゲーション")

        pages = {"🏠 ホーム": "home", "📤 アップロード": "upload", "🖼️ ギャラリー": "gallery"}

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
            # User information
            user_email = st.session_state.user_email or "unknown@example.com"
            st.markdown(f"📧 {user_email}")

            st.divider()

            # Database Admin section (development only)
            if _is_development_mode():
                st.markdown("**🔧 開発ツール**")

                if st.button("🗄️ データベース管理", use_container_width=True, help="データベース管理（開発専用）"):
                    st.session_state.current_page = "database_admin"
                    st.rerun()

                st.divider()

        else:
            st.subheader("🔐 認証")
            st.info("写真にアクセスするには認証してください")

            if st.session_state.auth_error:
                st.error(f"**エラー:** {st.session_state.auth_error}")


def render_footer() -> None:
    """Render the application footer with improved layout and information."""
    st.divider()

    st.markdown(
        """
    <div style='text-align: center; color: #666; font-size: 0.8em;'>
        <strong>imgstream v0.1</strong>
    </div>
    """,
        unsafe_allow_html=True,
    )


def _is_development_mode() -> bool:
    """Check if running in development mode."""
    from ..handlers.dev_auth import _is_development_mode as dev_auth_is_development_mode

    return dev_auth_is_development_mode()
