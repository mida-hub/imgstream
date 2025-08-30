"""Gallery page for imgstream application."""

import streamlit as st
import structlog

from imgstream.services.auth import get_auth_service
from imgstream.ui.components.common import render_empty_state, render_error_message
from imgstream.ui.components.gallery import (
    render_gallery_header,
    render_pagination_controls,
    render_pagination_summary,
    render_photo_detail_modal,
    render_photo_grid,
    render_photo_list,
    reset_gallery_pagination,
)
from imgstream.ui.handlers.auth import require_authentication
from imgstream.ui.handlers.gallery import load_user_photos_paginated

logger = structlog.get_logger(__name__)


def render_gallery_page() -> None:
    """Render the gallery page with thumbnail grid display."""
    if not require_authentication():
        return

    try:
        # Get authenticated user
        auth_service = get_auth_service()
        user_info = auth_service.ensure_authenticated()

        # Gallery controls
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.markdown("### 🖼️ あなたの写真コレクション")

        with col2:
            view_mode = st.selectbox("表示", ["グリッド", "リスト"], index=0)

        with col3:
            sort_order = st.selectbox("並び順", ["新しい順", "古い順"], index=0)

        st.divider()

        # Initialize pagination state
        initialize_gallery_pagination()

        # Reset pagination if sort order changes
        if st.session_state.get("gallery_sort_order") != sort_order:
            reset_gallery_pagination()
            st.session_state.gallery_sort_order = sort_order

        # Load photos with pagination
        rerun_counter = st.session_state.get("gallery_rerun_counter", 0)
        photos, total_count, has_more = load_user_photos_paginated(
            user_info.user_id,
            sort_order,
            st.session_state.gallery_page,
            st.session_state.gallery_page_size,
            rerun_counter=rerun_counter,
        )

        if total_count == 0:
            # Empty state for photos
            render_empty_state(
                title="まだ写真がありません",
                description="写真コレクションが空です。写真をアップロードして始めましょう！",
                icon="📷",
                action_text="写真をアップロード",
                action_page="upload",
            )
        else:
            # Store photos in session state for navigation
            st.session_state.gallery_photos = photos

            # Display photo count and pagination info
            render_gallery_header(photos, total_count, has_more)

            # Render photos based on view mode
            if view_mode == "グリッド":
                render_photo_grid(photos)
            else:
                render_photo_list(photos)

            # Render pagination controls
            render_pagination_controls(has_more, total_count)

            # Render pagination summary
            render_pagination_summary()

            # Render photo detail modal if needed
            render_photo_detail_modal()

    except Exception as e:
        logger.error("gallery_page_error", error=str(e))
        render_error_message("ギャラリーエラー", "写真コレクションの読み込みに失敗しました。", str(e))


def initialize_gallery_pagination() -> None:
    """Initialize gallery pagination state."""
    if "gallery_page" not in st.session_state:
        st.session_state.gallery_page = 0
    if "gallery_page_size" not in st.session_state:
        st.session_state.gallery_page_size = 20  # 20 photos per page for better performance
    if "gallery_sort_order" not in st.session_state:
        st.session_state.gallery_sort_order = "新しい順"
    if "gallery_total_loaded" not in st.session_state:
        st.session_state.gallery_total_loaded = 0
