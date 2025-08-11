"""Reusable UI components for imgstream application."""

import streamlit as st


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
    # Main header with breadcrumb navigation
    col1, col2, col3 = st.columns([2, 3, 2])

    with col1:
        # App logo and title
        st.markdown("# 📸 imgstream")

    with col2:
        # 不要な表示に思える
        # Breadcrumb navigation
        current_page = st.session_state.current_page
        page_titles = {"home": "ホーム", "upload": "写真アップロード", "gallery": "写真ギャラリー", "settings": "設定"}

        # if current_page in page_titles:
        #     st.markdown(f"### {page_titles[current_page]}")

    with col3:
        # Status indicators
        if st.session_state.authenticated:
            st.success("🟢 認証済み")
        else:
            st.error("🔴 未認証")

    # Subtitle and divider
    st.divider()


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
