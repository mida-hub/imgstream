"""Gallery handlers for imgstream application."""

from datetime import datetime, timezone, timedelta, UTC
from typing import Any

import streamlit as st
import structlog

from imgstream.services.metadata import get_metadata_service
from imgstream.services.storage import get_storage_service
from imgstream.services.image_processor import get_image_processor

logger = structlog.get_logger(__name__)

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


@st.cache_data(ttl=300)
def load_user_photos_paginated(
    user_id: str, sort_order: str = "新しい順", page: int = 0, page_size: int = 20, rerun_counter: int = 0
) -> tuple[list[dict[str, Any]], int, bool]:
    """
    Load user photos with pagination support.

    Args:
        user_id: User identifier
        sort_order: Sort order for photos
        page: Page number (0-based)
        page_size: Number of photos per page
        rerun_counter: A counter to manually trigger a cache refresh

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
        total_count = get_user_photos_count(user_id, rerun_counter=rerun_counter)

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
def get_user_photos_count(user_id: str, rerun_counter: int = 0) -> int:
    """
    Get total count of user photos.

    Args:
        user_id: User identifier
        rerun_counter: A counter to manually trigger a cache refresh

    Returns:
        int: Total number of photos
    """
    try:
        metadata_service = get_metadata_service(user_id)
        return metadata_service.get_photos_count()
    except Exception as e:
        logger.error("get_photos_count_error", user_id=user_id, error=str(e))
        return 0


def load_user_photos(user_id: str, sort_order: str = "新しい順", rerun_counter: int = 0) -> list[dict[str, Any]]:
    """
    Load user photos from metadata service (legacy function for compatibility).

    Args:
        user_id: User identifier
        sort_order: Sort order for photos
        rerun_counter: A counter to manually trigger a cache refresh

    Returns:
        list: List of photo metadata dictionaries
    """
    photos, _, _ = load_user_photos_paginated(user_id, sort_order, 0, 50, rerun_counter=rerun_counter)
    return photos


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
        logger.error("get_original_url_error", photo_id=photo_id, original_path=original_path, error=str(e))
        return None
