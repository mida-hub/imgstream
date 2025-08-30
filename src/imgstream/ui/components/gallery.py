"""Gallery components for imgstream application."""

from datetime import datetime
from typing import Any

import streamlit as st
import structlog

from ..handlers.gallery import (
    convert_heic_to_web_display,
    convert_utc_to_jst,
    download_original_photo,
    get_photo_original_url,
    get_photo_thumbnail_url,
    is_heic_file,
    parse_datetime_string,
)

logger = structlog.get_logger(__name__)


def render_photo_grid(photos: list[dict[str, Any]]) -> None:
    """
    Render photos in a grid layout with thumbnails.

    Args:
        photos: List of photo metadata dictionaries
    """
    # Grid configuration
    cols_per_row = 4

    # Process photos in chunks for grid layout
    for i in range(0, len(photos), cols_per_row):
        cols = st.columns(cols_per_row)

        for j, col in enumerate(cols):
            photo_index = i + j
            if photo_index < len(photos):
                photo = photos[photo_index]
                with col:
                    render_photo_thumbnail(photo)
            else:
                # Empty column for alignment
                with col:
                    st.empty()


def render_photo_list(photos: list[dict[str, Any]]) -> None:
    """
    Render photos in a list layout with details.

    Args:
        photos: List of photo metadata dictionaries
    """
    for photo in photos:
        with st.container():
            col1, col2 = st.columns([1, 3])

            with col1:
                render_photo_thumbnail(photo, size="small")

            with col2:
                render_photo_details(photo)

            st.divider()


def render_photo_thumbnail(photo: dict[str, Any], size: str = "medium") -> None:
    """
    Render a single photo thumbnail with click functionality.

    Args:
        photo: Photo metadata dictionary
        size: Thumbnail size ("small", "medium", "large")
    """
    try:
        # Get thumbnail URL
        thumbnail_path = photo.get("thumbnail_path")
        photo_id = photo.get("id")
        thumbnail_url = get_photo_thumbnail_url(thumbnail_path, photo_id)

        if thumbnail_url:
            # Display thumbnail image
            st.image(thumbnail_url, caption=photo.get("filename", "不明"), use_container_width=True)

            # Photo info overlay
            created_at = photo.get("created_at")
            if created_at:
                if isinstance(created_at, str):
                    created_at = parse_datetime_string(created_at)

                if created_at:
                    # Convert to JST for display
                    jst_created_at = convert_utc_to_jst(created_at)
                    st.caption(f"📅 {jst_created_at.strftime('%Y-%m-%d')}")

            @st.dialog(title="写真詳細", width="large")
            def show_photo_dialog():
                # Main content area
                col1, col2 = st.columns([3, 1])
                with col1:
                    render_photo_detail_image(photo)
                with col2:
                    render_photo_detail_sidebar(photo)

            # Enhanced click handler for photo details
            if st.button("🔍 詳細を表示", key=f"view_{photo.get('id', 'unknown')}", use_container_width=True):
                show_photo_dialog()

        else:
            # Fallback for missing thumbnail
            st.error("📷 サムネイルが利用できません")
            st.caption(photo.get("filename", "不明"))

    except Exception as e:
        logger.error("render_thumbnail_error", photo_id=photo.get("id"), error=str(e))
        st.error("❌ サムネイルの読み込みに失敗しました")
        st.caption(photo.get("filename", "不明"))


def _print_datetime(target_at, should_convert_utc_to_jst: bool):
    if not target_at:
        return None
    target_at_datetime = None
    if isinstance(target_at, str):
        target_at_datetime = parse_datetime_string(target_at)
    if isinstance(target_at, datetime):
        target_at_datetime = target_at
    if target_at_datetime:
        if should_convert_utc_to_jst:
            return convert_utc_to_jst(target_at_datetime).strftime("%Y-%m-%d %H:%M:%S")
        return target_at_datetime.strftime("%Y-%m-%d %H:%M:%S")

    return target_at


def render_photo_details(photo: dict[str, Any]) -> None:
    """
    Render detailed information about a photo.

    Args:
        photo: Photo metadata dictionary
    """

    # Creation date
    created_at = photo.get("created_at")
    # Upload date
    uploaded_at = photo.get("uploaded_at")

    created_at_should_convert_utc_to_jst = False
    if created_at and uploaded_at and isinstance(created_at, str) and isinstance(uploaded_at, str):
        # 分単位まで一致していれば exif 情報を抽出できず、作成日=アップロード日とみなして jst 変換フラグをたてる
        created_at_should_convert_utc_to_jst = created_at[0:16] == uploaded_at[0:16]

    if created_at:
        st.write(
            f"""📅 **作成日**  
{_print_datetime(created_at, should_convert_utc_to_jst=created_at_should_convert_utc_to_jst)}"""
        )

    if uploaded_at:
        st.write(f"""📤 **アップロード日**  
{_print_datetime(uploaded_at, should_convert_utc_to_jst=True)}""")

    # File size
    file_size = photo.get("file_size")
    if file_size:
        file_size_mb = file_size / (1024 * 1024)
        st.write(f"""💾 **サイズ**  
{file_size_mb:.1f} MB""")


def render_photo_detail_image(photo: dict[str, Any]) -> None:
    """
    Render the main photo image with enhanced display options.

    Args:
        photo: Photo metadata dictionary
    """
    filename = photo.get("filename", "不明")
    photo_id = photo.get("id")
    original_path = photo.get("original_path")

    # Check if this is a HEIC file that needs conversion
    if is_heic_file(filename):
        # Ensure we have valid string values for conversion
        if not original_path or not photo_id:
            st.error("❌ 画像の情報が不完全です")
            return

        try:
            # Show loading message for HEIC conversion
            with st.spinner("HEIC画像を変換中..."):
                jpeg_data = convert_heic_to_web_display(str(original_path), str(photo_id))

            if jpeg_data:
                # Display converted JPEG
                st.image(jpeg_data, caption=f"{filename} (HEIC → JPEG変換済み)", use_container_width=True)
                st.info("💡 この画像はHEIC形式からJPEGに変換されて表示されています。")
                return
            else:
                # Conversion failed, fall back to thumbnail
                st.error("❌ HEIC画像の変換に失敗しました")
                render_heic_fallback_display(photo)
                return

        except Exception as e:
            logger.error("heic_display_error", photo_id=photo_id, error=str(e))
            st.error(f"❌ HEIC画像の表示に失敗しました: {str(e)}")
            render_heic_fallback_display(photo)
            return

    # For non-HEIC files, use original URL display
    original_url = get_photo_original_url(original_path, photo_id)

    if original_url:
        try:
            # Display original image
            st.image(original_url, caption=filename, use_container_width=True)

        except Exception as e:
            st.error(f"オリジナル画像の読み込みに失敗しました: {str(e)}")
            st.error("画像が利用できません")

    else:
        st.error("画像が利用できません")
        st.info("画像がストレージから移動または削除された可能性があります。")


def render_heic_fallback_display(photo: dict[str, Any]) -> None:
    """
    Render fallback display for HEIC files when conversion fails.

    Args:
        photo: Photo metadata dictionary
    """
    st.warning("🔄 HEIC画像の変換に失敗したため、サムネイルを表示しています")
    thumbnail_path = photo.get("thumbnail_path")
    photo_id = photo.get("id")

    # Try to display thumbnail as fallback
    thumbnail_url = get_photo_thumbnail_url(thumbnail_path, photo_id)
    if thumbnail_url:
        try:
            st.image(
                thumbnail_url,
                caption=f"{photo.get('filename', '不明')} (サムネイル表示)",
                use_container_width=True,
            )
            st.info("💡 元の画像を表示するには、HEIC対応の画像ビューアーをご利用ください。")
        except Exception as e:
            logger.error("thumbnail_fallback_failed", photo_id=photo.get("id"), error=str(e))
            st.error("❌ サムネイルの表示にも失敗しました")
            st.info("画像ファイルに問題がある可能性があります。")
    else:
        st.error("❌ サムネイルが利用できません")
        st.info("画像ファイルに問題がある可能性があります。")


def render_photo_detail_sidebar(photo: dict[str, Any]) -> None:
    """
    Render photo detail sidebar with metadata and actions.

    Args:
        photo: Photo metadata dictionary
    """
    render_photo_details(photo)

    if st.button("📥 ダウンロード", use_container_width=True):
        download_original_photo(photo)


def render_gallery_header(photos: list[dict[str, Any]], total_count: int, has_more: bool) -> None:
    """
    Render gallery header with photo count and pagination info.

    Args:
        photos: Current page photos
        total_count: Total number of photos
        has_more: Whether there are more photos to load
    """
    current_page = st.session_state.gallery_page
    page_size = st.session_state.gallery_page_size

    # Calculate display range
    start_index = current_page * page_size + 1
    end_index = start_index + len(photos) - 1

    col1, col2 = st.columns([2, 1])

    with col1:
        if total_count > 0:
            st.markdown(f"**{total_count}枚中 {start_index}-{end_index}枚を表示**")
        else:
            st.markdown("**写真が見つかりません**")

    with col2:
        # Page info
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        current_page_display = current_page + 1

        if total_pages > 1:
            st.markdown(f"**{total_pages}ページ中 {current_page_display}ページ目**")


def render_pagination_controls(has_more: bool, total_count: int) -> None:
    """
    Render pagination controls.

    Args:
        has_more: Whether there are more photos to load
        total_count: Total number of photos
    """
    if total_count <= st.session_state.gallery_page_size:
        return  # No pagination needed

    st.divider()

    current_page = st.session_state.gallery_page
    page_size = st.session_state.gallery_page_size
    total_pages = (total_count + page_size - 1) // page_size

    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

    # Previous page button
    with col1:
        if st.button("⏮️ 最初", disabled=current_page == 0, use_container_width=True):
            st.session_state.gallery_page = 0
            st.rerun()

    # First page button
    with col2:
        if st.button("⬅️ 前へ", disabled=current_page == 0, use_container_width=True):
            st.session_state.gallery_page = max(0, current_page - 1)
            st.rerun()

    # Page info and jump
    with col3:
        # Page selector
        page_options = list(range(1, total_pages + 1))
        if page_options:
            selected_page = st.selectbox("ページに移動:", page_options, index=current_page, key="page_selector")

            if selected_page - 1 != current_page:
                st.session_state.gallery_page = selected_page - 1
                st.rerun()

    # Last page button
    with col4:
        if st.button("次へ ➡️", disabled=not has_more, use_container_width=True):
            st.session_state.gallery_page = current_page + 1
            st.rerun()

    # Next page button
    with col5:
        if st.button("⏭️ 最後", disabled=current_page >= total_pages - 1, use_container_width=True):
            st.session_state.gallery_page = total_pages - 1
            st.rerun()

    # Load more button (alternative to pagination)
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if has_more:
            if st.button("📥 さらに写真を読み込む", use_container_width=True, type="secondary"):
                # Increase page size to show more photos on current view
                st.session_state.gallery_page_size += 20
                st.rerun()


def render_pagination_summary() -> None:
    """Render pagination summary information."""
    current_page = st.session_state.gallery_page
    page_size = st.session_state.gallery_page_size

    with st.expander("📊 ページネーション設定", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**現在のページ:** {current_page + 1}")
            st.write(f"**1ページあたりの写真数:** {page_size}")

        with col2:
            # Page size selector
            new_page_size = st.selectbox(
                "1ページあたりの写真数:",
                [10, 20, 30, 50, 100],
                index=[10, 20, 30, 50, 100].index(page_size) if page_size in [10, 20, 30, 50, 100] else 1,
                key="page_size_selector",
            )

            if new_page_size != page_size:
                st.session_state.gallery_page_size = new_page_size
                st.session_state.gallery_page = 0  # Reset to first page
                st.rerun()

            # Reset pagination button
            if st.button("🔄 最初のページにリセット", use_container_width=True):
                reset_gallery_pagination()
                st.rerun()


def reset_gallery_pagination() -> None:
    """Reset gallery pagination to first page."""
    st.session_state.gallery_page = 0
    st.session_state.gallery_total_loaded = 0
