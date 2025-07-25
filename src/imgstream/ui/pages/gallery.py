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

        # Load photos from metadata service
        photos = load_user_photos(user_info.user_id, sort_order)

        if not photos:
            # Empty state for photos
            render_empty_state(
                title="No Photos Yet",
                description="Your photo collection is empty. Upload some photos to get started!",
                icon="📷",
                action_text="Upload Photos",
                action_page="upload",
            )
        else:
            # Display photo count
            st.markdown(f"**{len(photos)} photo(s) in your collection**")

            # Render photos based on view mode
            if view_mode == "Grid":
                render_photo_grid(photos)
            else:
                render_photo_list(photos)

            # Render photo detail modal if needed
            render_photo_detail_modal()

    except Exception as e:
        logger.error("gallery_page_error", error=str(e))
        render_error_message("Gallery Error", "Failed to load your photo collection.", str(e), show_retry=True)


def load_user_photos(user_id: str, sort_order: str = "Newest First") -> list[dict[str, Any]]:
    """
    Load user photos from metadata service.

    Args:
        user_id: User identifier
        sort_order: Sort order for photos

    Returns:
        list: List of photo metadata dictionaries
    """
    try:
        metadata_service = get_metadata_service(user_id)

        # Get photos with pagination (initial load of 50)
        photos = metadata_service.get_photos_by_date(limit=50, offset=0)

        # Convert PhotoMetadata objects to dictionaries
        photo_dicts = [photo.to_dict() for photo in photos]

        # Sort photos based on user preference
        if sort_order == "Oldest First":
            photo_dicts.reverse()

        logger.info("photos_loaded", user_id=user_id, count=len(photo_dicts), sort_order=sort_order)
        return photo_dicts

    except Exception as e:
        logger.error("load_photos_error", user_id=user_id, error=str(e))
        return []


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
