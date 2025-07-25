"""Gallery page for imgstream application."""

from datetime import datetime
from typing import Any

import streamlit as st
import structlog

from imgstream.services.auth import get_auth_service
from imgstream.services.metadata import get_metadata_service
from imgstream.services.storage import get_storage_service
from imgstream.ui.auth_handlers import require_authentication
from imgstream.ui.components import render_empty_state, render_error_message

logger = structlog.get_logger()


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
            st.markdown("### 🖼️ Your Photo Collection")

        with col2:
            view_mode = st.selectbox("View", ["Grid", "List"], index=0)

        with col3:
            sort_order = st.selectbox("Sort by", ["Newest First", "Oldest First"], index=0)

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
                title="No Photos Yet",
                description="Your photo collection is empty. Upload some photos to get started!",
                icon="📷",
                action_text="Upload Photos",
                action_page="upload",
            )
        else:
            # Display photo count and pagination info
            render_gallery_header(photos, total_count, has_more)

            # Render photos based on view mode
            if view_mode == "Grid":
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
        render_error_message("Gallery Error", "Failed to load your photo collection.", str(e), show_retry=True)


def initialize_gallery_pagination() -> None:
    """Initialize gallery pagination state."""
    if "gallery_page" not in st.session_state:
        st.session_state.gallery_page = 0
    if "gallery_page_size" not in st.session_state:
        st.session_state.gallery_page_size = 20  # 20 photos per page for better performance
    if "gallery_sort_order" not in st.session_state:
        st.session_state.gallery_sort_order = "Newest First"
    if "gallery_total_loaded" not in st.session_state:
        st.session_state.gallery_total_loaded = 0


def reset_gallery_pagination() -> None:
    """Reset gallery pagination to first page."""
    st.session_state.gallery_page = 0
    st.session_state.gallery_total_loaded = 0


def load_user_photos_paginated(
    user_id: str, sort_order: str = "Newest First", page: int = 0, page_size: int = 20
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
        if sort_order == "Oldest First":
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


def load_user_photos(user_id: str, sort_order: str = "Newest First") -> list[dict[str, Any]]:
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
        thumbnail_url = get_photo_thumbnail_url(photo)

        if thumbnail_url:
            # Display thumbnail image
            st.image(thumbnail_url, caption=photo.get("filename", "Unknown"), use_column_width=True)

            # Photo info overlay
            creation_date = photo.get("created_at")
            if creation_date:
                if isinstance(creation_date, str):
                    # Parse string date
                    try:
                        creation_date = datetime.fromisoformat(creation_date.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        creation_date = None

                if creation_date:
                    st.caption(f"📅 {creation_date.strftime('%Y-%m-%d')}")

            # Click handler for photo details
            if st.button("View Details", key=f"view_{photo.get('id', 'unknown')}", use_container_width=True):
                st.session_state.selected_photo = photo
                st.session_state.show_photo_details = True
                st.rerun()

        else:
            # Fallback for missing thumbnail
            st.error("📷 Thumbnail not available")
            st.caption(photo.get("filename", "Unknown"))

    except Exception as e:
        logger.error("render_thumbnail_error", photo_id=photo.get("id"), error=str(e))
        st.error("❌ Failed to load thumbnail")
        st.caption(photo.get("filename", "Unknown"))


def render_photo_details(photo: dict[str, Any]) -> None:
    """
    Render detailed information about a photo.

    Args:
        photo: Photo metadata dictionary
    """
    # Photo filename
    filename = photo.get("filename", "Unknown")
    st.markdown(f"**📷 {filename}**")

    # Creation date
    creation_date = photo.get("created_at")
    if creation_date:
        if isinstance(creation_date, str):
            try:
                creation_date = datetime.fromisoformat(creation_date.replace("Z", "+00:00"))
                st.write(f"📅 **Created:** {creation_date.strftime('%Y-%m-%d %H:%M:%S')}")
            except (ValueError, TypeError):
                st.write(f"📅 **Created:** {creation_date}")
        else:
            st.write(f"📅 **Created:** {creation_date.strftime('%Y-%m-%d %H:%M:%S')}")

    # Upload date
    upload_date = photo.get("uploaded_at")
    if upload_date:
        if isinstance(upload_date, str):
            try:
                upload_date = datetime.fromisoformat(upload_date.replace("Z", "+00:00"))
                st.write(f"📤 **Uploaded:** {upload_date.strftime('%Y-%m-%d %H:%M:%S')}")
            except (ValueError, TypeError):
                st.write(f"📤 **Uploaded:** {upload_date}")
        else:
            st.write(f"📤 **Uploaded:** {upload_date.strftime('%Y-%m-%d %H:%M:%S')}")

    # File size
    file_size = photo.get("file_size")
    if file_size:
        file_size_mb = file_size / (1024 * 1024)
        st.write(f"💾 **Size:** {file_size_mb:.1f} MB")

    # MIME type
    mime_type = photo.get("mime_type")
    if mime_type:
        st.write(f"📄 **Type:** {mime_type}")


def get_photo_thumbnail_url(photo: dict[str, Any]) -> str | None:
    """
    Get signed URL for photo thumbnail.

    Args:
        photo: Photo metadata dictionary

    Returns:
        str: Signed URL for thumbnail, or None if failed
    """
    try:
        storage_service = get_storage_service()
        thumbnail_path = photo.get("thumbnail_path")

        if not thumbnail_path:
            logger.warning("no_thumbnail_path", photo_id=photo.get("id"))
            return None

        # Generate signed URL for thumbnail (1 hour expiration)
        signed_url = storage_service.get_signed_url(thumbnail_path, expiration=3600)
        return signed_url

    except Exception as e:
        logger.error(
            "get_thumbnail_url_error",
            photo_id=photo.get("id"),
            thumbnail_path=photo.get("thumbnail_path"),
            error=str(e),
        )
        return None


def render_photo_detail_modal() -> None:
    """Render photo detail modal if a photo is selected."""
    if st.session_state.get("show_photo_details") and st.session_state.get("selected_photo"):
        photo = st.session_state.selected_photo

        with st.container():
            st.markdown("### 🖼️ Photo Details")

            col1, col2 = st.columns([2, 1])

            with col1:
                # Show original image
                original_url = get_photo_original_url(photo)
                if original_url:
                    st.image(original_url, caption=photo.get("filename", "Unknown"))
                else:
                    st.error("Failed to load original image")

            with col2:
                render_photo_details(photo)

                # Close button
                if st.button("❌ Close", use_container_width=True):
                    st.session_state.show_photo_details = False
                    st.session_state.selected_photo = None
                    st.rerun()


def get_photo_original_url(photo: dict[str, Any]) -> str | None:
    """
    Get signed URL for original photo.

    Args:
        photo: Photo metadata dictionary

    Returns:
        str: Signed URL for original photo, or None if failed
    """
    try:
        storage_service = get_storage_service()
        original_path = photo.get("original_path")

        if not original_path:
            logger.warning("no_original_path", photo_id=photo.get("id"))
            return None

        # Generate signed URL for original (1 hour expiration)
        signed_url = storage_service.get_signed_url(original_path, expiration=3600)
        return signed_url

    except Exception as e:
        logger.error(
            "get_original_url_error", photo_id=photo.get("id"), original_path=photo.get("original_path"), error=str(e)
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
            st.markdown(f"**Showing {start_index}-{end_index} of {total_count} photo(s)**")
        else:
            st.markdown("**No photos found**")

    with col2:
        # Page info
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        current_page_display = current_page + 1

        if total_pages > 1:
            st.markdown(f"**Page {current_page_display} of {total_pages}**")


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
        if st.button("⬅️ Previous", disabled=current_page == 0, use_container_width=True):
            st.session_state.gallery_page = max(0, current_page - 1)
            st.rerun()

    # First page button
    with col2:
        if st.button("⏮️ First", disabled=current_page == 0, use_container_width=True):
            st.session_state.gallery_page = 0
            st.rerun()

    # Page info and jump
    with col3:
        # Page selector
        page_options = list(range(1, total_pages + 1))
        if page_options:
            selected_page = st.selectbox("Go to page:", page_options, index=current_page, key="page_selector")

            if selected_page - 1 != current_page:
                st.session_state.gallery_page = selected_page - 1
                st.rerun()

    # Last page button
    with col4:
        if st.button("⏭️ Last", disabled=current_page >= total_pages - 1, use_container_width=True):
            st.session_state.gallery_page = total_pages - 1
            st.rerun()

    # Next page button
    with col5:
        if st.button("Next ➡️", disabled=not has_more, use_container_width=True):
            st.session_state.gallery_page = current_page + 1
            st.rerun()

    # Load more button (alternative to pagination)
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if has_more:
            if st.button("📥 Load More Photos", use_container_width=True, type="secondary"):
                # Increase page size to show more photos on current view
                st.session_state.gallery_page_size += 20
                st.rerun()

        # Show performance tip
        if total_count > 100:
            st.info("💡 **Performance tip**: Use pagination for faster loading with large photo collections.")


def render_pagination_summary() -> None:
    """Render pagination summary information."""
    current_page = st.session_state.gallery_page
    page_size = st.session_state.gallery_page_size

    with st.expander("📊 Pagination Settings", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Current Page:** {current_page + 1}")
            st.write(f"**Photos per Page:** {page_size}")

        with col2:
            # Page size selector
            new_page_size = st.selectbox(
                "Photos per page:",
                [10, 20, 30, 50, 100],
                index=[10, 20, 30, 50, 100].index(page_size) if page_size in [10, 20, 30, 50, 100] else 1,
                key="page_size_selector",
            )

            if new_page_size != page_size:
                st.session_state.gallery_page_size = new_page_size
                st.session_state.gallery_page = 0  # Reset to first page
                st.rerun()

            # Reset pagination button
            if st.button("🔄 Reset to First Page", use_container_width=True):
                reset_gallery_pagination()
                st.rerun()
