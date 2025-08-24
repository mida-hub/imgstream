"""Gallery page for imgstream application."""

from datetime import datetime, timezone, timedelta, UTC
from typing import Any

import streamlit as st
import structlog

from imgstream.services.auth import get_auth_service
from imgstream.services.metadata import get_metadata_service
from imgstream.services.storage import get_storage_service
from imgstream.ui.handlers.auth import require_authentication
from imgstream.ui.components.common import render_empty_state, render_error_message

logger = structlog.get_logger()

# JST timezone (UTC+9)
JST = timezone(timedelta(hours=9))


def is_heic_file(filename: str | None) -> bool:
    """
    Check if a file is a HEIC format based on its extension.

    Args:
        filename: The filename to check

    Returns:
        bool: True if the file is HEIC format, False otherwise
    """
    if not filename or not isinstance(filename, str):
        return False

    try:
        # Get file extension and normalize to lowercase
        if "." not in filename:
            return False

        extension = filename.lower().split(".")[-1]

        # Check for HEIC/HEIF extensions
        return extension in ["heic", "heif"]
    except (AttributeError, IndexError):
        return False


def convert_utc_to_jst(utc_datetime: datetime) -> datetime:
    """
    Convert UTC datetime to JST.

    Args:
        utc_datetime: UTC datetime object

    Returns:
        datetime: JST datetime object
    """
    if utc_datetime.tzinfo is None:
        # Assume UTC if no timezone info
        utc_datetime = utc_datetime.replace(tzinfo=UTC)
    elif utc_datetime.tzinfo != UTC:
        # Convert to UTC first if it's in a different timezone
        utc_datetime = utc_datetime.astimezone(UTC)

    return utc_datetime.astimezone(JST)


def parse_datetime_string(datetime_str: str) -> datetime | None:
    """
    Parse datetime string and return datetime object.

    Args:
        datetime_str: Datetime string in various formats

    Returns:
        datetime: Parsed datetime object or None if parsing fails
    """
    try:
        # Handle ISO format with Z suffix
        if datetime_str.endswith("Z"):
            datetime_str = datetime_str.replace("Z", "+00:00")

        return datetime.fromisoformat(datetime_str)
    except (ValueError, TypeError):
        return None


@st.cache_data(ttl=86400)  # 1 day cache
def convert_heic_to_web_display(original_path: str, photo_id: str) -> bytes | None:
    """
    Convert HEIC photo to JPEG for web display.

    Args:
        original_path: The GCS path to the original photo
        photo_id: The ID of the photo for logging

    Returns:
        bytes: Converted JPEG data, or None if conversion fails
    """
    try:
        from imgstream.services.storage import get_storage_service
        from imgstream.services.image_processor import get_image_processor

        # Get original image data from storage
        storage_service = get_storage_service()

        if not original_path:
            logger.warning("no_original_path_for_conversion", photo_id=photo_id)
            return None

        # Download original image data
        image_data = storage_service.download_file(original_path)
        if not image_data:
            logger.warning("failed_to_download_original", photo_id=photo_id, path=original_path)
            return None

        # Convert to web display JPEG
        image_processor = get_image_processor()
        jpeg_data = image_processor.convert_to_web_display_jpeg(image_data)

        logger.info(
            "heic_converted_for_web_display",
            photo_id=photo_id,
            original_size=len(image_data),
            jpeg_size=len(jpeg_data),
        )

        return jpeg_data

    except Exception as e:
        logger.error(
            "heic_conversion_failed",
            photo_id=photo_id,
            original_path=original_path,
            error=str(e),
        )
        return None


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
        photos, total_count, has_more = load_user_photos_paginated(
            user_info.user_id, sort_order, st.session_state.gallery_page, st.session_state.gallery_page_size
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


def reset_gallery_pagination() -> None:
    """Reset gallery pagination to first page."""
    st.session_state.gallery_page = 0
    st.session_state.gallery_total_loaded = 0


@st.cache_data(ttl=300)
def load_user_photos_paginated(
    user_id: str, sort_order: str = "新しい順", page: int = 0, page_size: int = 20
) -> tuple[list[dict[str, Any]], int, bool]:
    """
    Load user photos with pagination support.

    Args:
        user_id: User identifier
        sort_order: Sort order for photos
        page: Page number (0-based)
        page_size: Number of photos per page

    Returns:
        tuple: (photos, total_count, has_more)
    """
    try:
        metadata_service = get_metadata_service(user_id)

        # Calculate offset
        offset = page * page_size

        # Get photos with pagination (request one extra to check if there are more)
        photos = metadata_service.get_photos_by_date(limit=page_size + 1, offset=offset)

        # Check if there are more photos
        has_more = len(photos) > page_size
        if has_more:
            photos = photos[:page_size]  # Remove the extra photo

        # Convert PhotoMetadata objects to dictionaries
        photo_dicts = [photo.to_dict() for photo in photos]

        # Sort photos based on user preference
        if sort_order == "古い順":
            photo_dicts.reverse()

        # Get total count (for display purposes)
        total_count = get_user_photos_count(user_id)

        logger.info(
            "photos_loaded_paginated",
            user_id=user_id,
            count=len(photo_dicts),
            page=page,
            page_size=page_size,
            total_count=total_count,
            has_more=has_more,
            sort_order=sort_order,
        )

        return photo_dicts, total_count, has_more

    except Exception as e:
        logger.error("load_photos_paginated_error", user_id=user_id, page=page, error=str(e))
        return [], 0, False


@st.cache_data(ttl=300)
def get_user_photos_count(user_id: str) -> int:
    """
    Get total count of user photos.

    Args:
        user_id: User identifier

    Returns:
        int: Total number of photos
    """
    try:
        metadata_service = get_metadata_service(user_id)
        return metadata_service.get_photos_count()
    except Exception as e:
        logger.error("get_photos_count_error", user_id=user_id, error=str(e))
        return 0


def load_user_photos(user_id: str, sort_order: str = "新しい順") -> list[dict[str, Any]]:
    """
    Load user photos from metadata service (legacy function for compatibility).

    Args:
        user_id: User identifier
        sort_order: Sort order for photos

    Returns:
        list: List of photo metadata dictionaries
    """
    photos, _, _ = load_user_photos_paginated(user_id, sort_order, 0, 50)
    return photos


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

            # Enhanced click handler for photo details
            if st.button("🔍 詳細を表示", key=f"view_{photo.get('id', 'unknown')}", use_container_width=True):
                st.session_state.selected_photo = photo
                st.session_state.show_photo_details = True

                # Store photo context for navigation (if available)
                if "gallery_photos" in st.session_state:
                    photos = st.session_state.gallery_photos
                    try:
                        photo_index = next(i for i, p in enumerate(photos) if p.get("id") == photo.get("id"))
                        st.session_state.photo_index = photo_index
                        st.session_state.total_photos = len(photos)
                    except StopIteration:
                        pass

                st.rerun()

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
            return convert_utc_to_jst(target_at_datetime).strftime('%Y-%m-%d %H:%M:%S')
        return target_at_datetime.strftime('%Y-%m-%d %H:%M:%S')

    return target_at


def render_photo_details(photo: dict[str, Any]) -> None:
    """
    Render detailed information about a photo.

    Args:
        photo: Photo metadata dictionary
    """
    # Photo filename
    filename = photo.get("filename", "不明")
    st.markdown(f"**📷 {filename}**")

    # Creation date
    created_at = photo.get("created_at")
    # Upload date
    uploaded_at = photo.get("uploaded_at")

    created_at_should_convert_utc_to_jst = False
    if created_at and uploaded_at and isinstance(created_at, str) and isinstance(uploaded_at, str):
        # 分単位まで一致していれば exif 情報を抽出できず、作成日=アップロード日とみなして jst 変換フラグをたてる
        created_at_should_convert_utc_to_jst = created_at[0:16] == uploaded_at[0:16]

    if created_at:
        st.write(f"""📅 **作成日:** {_print_datetime(created_at, should_convert_utc_to_jst=created_at_should_convert_utc_to_jst)} JST""")

    if uploaded_at:
        st.write(f"📤 **アップロード日:** {_print_datetime(uploaded_at, should_convert_utc_to_jst=True)} JST")

    # File size
    file_size = photo.get("file_size")
    if file_size:
        file_size_mb = file_size / (1024 * 1024)
        st.write(f"💾 **サイズ:** {file_size_mb:.1f} MB")

    # MIME type
    mime_type = photo.get("mime_type")
    if mime_type:
        st.write(f"📄 **タイプ:** {mime_type}")


@st.cache_data(ttl=3000)  # 50 minute cache
def get_photo_thumbnail_url(thumbnail_path: str | None, photo_id: str | None) -> str | None:
    """
    Get signed URL for photo thumbnail.

    Args:
        thumbnail_path: The GCS path to the thumbnail
        photo_id: The ID of the photo for logging

    Returns:
        str: Signed URL for thumbnail, or None if failed
    """
    try:
        storage_service = get_storage_service()

        if not thumbnail_path:
            logger.warning("no_thumbnail_path", photo_id=photo_id)
            return None

        # Generate signed URL for thumbnail (1 hour expiration)
        signed_url = storage_service.get_signed_url(thumbnail_path, expiration=3600)
        return signed_url

    except Exception as e:
        logger.error(
            "get_thumbnail_url_error",
            photo_id=photo_id,
            thumbnail_path=thumbnail_path,
            error=str(e),
        )
        return None


def render_photo_detail_modal() -> None:
    """Render enhanced photo detail modal if a photo is selected."""
    if st.session_state.get("show_photo_details") and st.session_state.get("selected_photo"):
        photo = st.session_state.selected_photo

        # Create a full-width modal-like container
        st.markdown("---")

        # Header with navigation
        render_photo_detail_header(photo)

        # Main content area
        col1, col2 = st.columns([3, 1])

        with col1:
            render_photo_detail_image(photo)

        with col2:
            render_photo_detail_sidebar(photo)


def render_photo_detail_header(photo: dict[str, Any]) -> None:
    """
    Render photo detail header with navigation.

    Args:
        photo: Photo metadata dictionary
    """
    pass


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
        try:
            # Show loading message for HEIC conversion
            with st.spinner("HEIC画像を変換中..."):
                jpeg_data = convert_heic_to_web_display(original_path, photo_id)

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
    # Enhanced photo details
    st.markdown("#### 📋 写真詳細")
    render_photo_details(photo)

    if st.button("📥 写真をダウンロード", use_container_width=True):
        download_original_photo(photo)


def download_original_photo(photo: dict[str, Any]) -> None:
    """
    Handle original photo download.

    Args:
        photo: Photo metadata dictionary
    """
    try:
        original_path = photo.get("original_path")
        photo_id = photo.get("id")
        original_url = get_photo_original_url(original_path, photo_id)
        if original_url:
            st.success("✅ ダウンロードリンクを生成しました！")
            st.markdown(f"[📥 オリジナル写真をダウンロード]({original_url})")
            st.info("💡 上記のリンクを右クリックして「名前を付けてリンク先を保存」を選択してダウンロードしてください")
        else:
            st.error("❌ ダウンロードリンクの生成に失敗しました")
    except Exception as e:
        st.error(f"❌ ダウンロードに失敗しました: {str(e)}")


def copy_image_url(photo: dict[str, Any]) -> None:
    """
    Handle copying image URL to clipboard.

    Args:
        photo: Photo metadata dictionary
    """
    try:
        original_path = photo.get("original_path")
        photo_id = photo.get("id")
        original_url = get_photo_original_url(original_path, photo_id)
        if original_url:
            # Since we can't directly copy to clipboard in Streamlit,
            # we'll display the URL for manual copying
            st.success("✅ 画像URLをコピーする準備ができました:")
            st.code(original_url)
            st.info("💡 上記のURLを選択してコピーしてください（Ctrl+C / Cmd+C）")
        else:
            st.error("❌ 画像URLの生成に失敗しました")
    except Exception as e:
        st.error(f"❌ 画像URLの取得に失敗しました: {str(e)}")


@st.cache_data(ttl=3000)  # 50 minute cache
def get_photo_original_url(original_path: str | None, photo_id: str | None) -> str | None:
    """
    Get signed URL for original photo.

    Args:
        original_path: The GCS path to the original photo
        photo_id: The ID of the photo for logging

    Returns:
        str: Signed URL for original photo, or None if failed
    """
    try:
        storage_service = get_storage_service()

        if not original_path:
            logger.warning("no_original_path", photo_id=photo_id)
            return None

        # Generate signed URL for original (1 hour expiration)
        signed_url = storage_service.get_signed_url(original_path, expiration=3600)
        return signed_url

    except Exception as e:
        logger.error(
            "get_original_url_error", photo_id=photo_id, original_path=original_path, error=str(e)
        )
        return None


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
