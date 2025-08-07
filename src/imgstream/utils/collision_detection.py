"""Collision detection utilities for filename conflicts."""

from typing import Any
import structlog

from ..services.metadata import get_metadata_service, MetadataError
from ..logging_config import log_error

logger = structlog.get_logger(__name__)


def check_filename_collisions(user_id: str, filenames: list[str]) -> dict[str, dict[str, Any]]:
    """
    Check for filename collisions across multiple files for a user.

    Args:
        user_id: User identifier
        filenames: List of filenames to check for collisions

    Returns:
        dict: Dictionary mapping filename to collision info
              Format: {filename: collision_info} where collision_info is from MetadataService.check_filename_exists()

    Raises:
        CollisionDetectionError: If collision detection fails
    """
    if not filenames:
        return {}

    try:
        metadata_service = get_metadata_service(user_id)
        collision_results = {}

        logger.info(
            "batch_collision_detection_started",
            user_id=user_id,
            total_files=len(filenames),
            filenames=filenames[:5],  # Log first 5 filenames for debugging
        )

        for filename in filenames:
            try:
                collision_info = metadata_service.check_filename_exists(filename)
                if collision_info:
                    collision_results[filename] = collision_info
                    logger.debug(
                        "collision_detected_in_batch",
                        user_id=user_id,
                        filename=filename,
                        existing_photo_id=collision_info["existing_photo"].id,
                    )

            except MetadataError as e:
                logger.warning(
                    "collision_check_failed_for_file",
                    user_id=user_id,
                    filename=filename,
                    error=str(e),
                )
                # Continue with other files even if one fails
                continue

        logger.info(
            "batch_collision_detection_completed",
            user_id=user_id,
            total_files=len(filenames),
            collisions_found=len(collision_results),
        )

        return collision_results

    except Exception as e:
        log_error(
            e,
            {
                "operation": "check_filename_collisions",
                "user_id": user_id,
                "total_files": len(filenames),
            },
        )
        raise CollisionDetectionError(f"Failed to check filename collisions: {e}") from e


def process_collision_results(
    collision_results: dict[str, dict[str, Any]], user_decisions: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    Process collision results and apply user decisions.

    Args:
        collision_results: Results from check_filename_collisions()
        user_decisions: Dictionary mapping filename to user decision ("overwrite" or "skip")

    Returns:
        dict: Processed collision information with decisions applied
              Format: {
                  "collisions": {filename: collision_info_with_decision},
                  "summary": {
                      "total_collisions": int,
                      "overwrite_count": int,
                      "skip_count": int,
                      "pending_count": int
                  }
              }
    """
    if not collision_results:
        return {
            "collisions": {},
            "summary": {
                "total_collisions": 0,
                "overwrite_count": 0,
                "skip_count": 0,
                "pending_count": 0,
            },
        }

    user_decisions = user_decisions or {}
    processed_collisions = {}
    overwrite_count = 0
    skip_count = 0
    pending_count = 0

    for filename, collision_info in collision_results.items():
        # Copy collision info and apply user decision
        processed_info = collision_info.copy()

        if filename in user_decisions:
            decision = user_decisions[filename]
            processed_info["user_decision"] = decision
            processed_info["warning_shown"] = True

            if decision == "overwrite":
                overwrite_count += 1
            elif decision == "skip":
                skip_count += 1
        else:
            # Keep as pending if no decision made
            processed_info["user_decision"] = "pending"
            pending_count += 1

        processed_collisions[filename] = processed_info

    summary = {
        "total_collisions": len(collision_results),
        "overwrite_count": overwrite_count,
        "skip_count": skip_count,
        "pending_count": pending_count,
    }

    logger.info(
        "collision_results_processed",
        total_collisions=summary["total_collisions"],
        overwrite_count=summary["overwrite_count"],
        skip_count=summary["skip_count"],
        pending_count=summary["pending_count"],
    )

    return {"collisions": processed_collisions, "summary": summary}


def filter_files_by_collision_decision(
    valid_files: list[dict[str, Any]], collision_results: dict[str, dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """
    Filter files based on collision detection results and user decisions.

    Args:
        valid_files: List of validated file information dictionaries
        collision_results: Processed collision results with user decisions

    Returns:
        dict: Categorized files
              Format: {
                  "proceed_files": [file_info],  # Files to proceed with (new + overwrite)
                  "skip_files": [file_info],     # Files to skip due to collision
                  "collision_files": [file_info] # Files with collisions (for UI display)
              }
    """
    proceed_files = []
    skip_files = []
    collision_files = []

    for file_info in valid_files:
        filename = file_info["filename"]

        if filename in collision_results:
            collision_info = collision_results[filename]
            collision_files.append(
                {
                    **file_info,
                    "collision_info": collision_info,
                }
            )

            decision = collision_info.get("user_decision", "pending")
            if decision == "overwrite":
                proceed_files.append(
                    {
                        **file_info,
                        "is_overwrite": True,
                        "collision_info": collision_info,
                    }
                )
            elif decision == "skip":
                skip_files.append(
                    {
                        **file_info,
                        "collision_info": collision_info,
                    }
                )
            # pending decisions are not included in proceed_files
        else:
            # No collision, proceed as new file
            proceed_files.append(
                {
                    **file_info,
                    "is_overwrite": False,
                }
            )

    logger.info(
        "files_filtered_by_collision_decision",
        total_files=len(valid_files),
        proceed_files=len(proceed_files),
        skip_files=len(skip_files),
        collision_files=len(collision_files),
    )

    return {
        "proceed_files": proceed_files,
        "skip_files": skip_files,
        "collision_files": collision_files,
    }


def get_collision_summary_message(collision_summary: dict[str, int]) -> str:
    """
    Generate a user-friendly summary message for collision results.

    Args:
        collision_summary: Summary from process_collision_results()

    Returns:
        str: Human-readable summary message
    """
    total = collision_summary["total_collisions"]

    if total == 0:
        return "ファイル名の衝突は検出されませんでした。"

    overwrite = collision_summary["overwrite_count"]
    skip = collision_summary["skip_count"]
    pending = collision_summary["pending_count"]

    parts = []
    if total == 1:
        parts.append("1件のファイル名衝突が検出されました")
    else:
        parts.append(f"{total}件のファイル名衝突が検出されました")

    if overwrite > 0:
        parts.append(f"{overwrite}件を上書き")
    if skip > 0:
        parts.append(f"{skip}件をスキップ")
    if pending > 0:
        parts.append(f"{pending}件が決定待ち")

    return "。".join(parts) + "。"


class CollisionDetectionError(Exception):
    """Exception raised when collision detection fails."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error
