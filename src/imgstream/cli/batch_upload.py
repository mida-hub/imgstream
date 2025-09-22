import os
import sys
from invoke import task, Context
from dotenv import load_dotenv
import structlog
from unittest.mock import patch, MagicMock

# Add src to path to allow for absolute imports from the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from imgstream.services.auth import UserInfo
from imgstream.ui.handlers.upload import process_single_upload

logger = structlog.get_logger()

@task
def batch_upload(c: Context, directory: str, user_id: str, on_collision: str = "skip", env_file: str = ".env", recursive: bool = False, dry_run: bool = False):
    """
    Upload images from a local directory in batch.

    Args:
        c (Context): Invoke context.
        directory (str): Path to the directory containing images.
        user_id (str): The user ID for the upload.
        on_collision (str): Action on filename collision: 'skip' or 'overwrite'. Default is 'skip'.
        env_file (str): Path to the environment file. Default is '.env'.
        recursive (bool): Search for images in subdirectories. Default is False.
        dry_run (bool): If True, lists files to be processed without uploading. Default is False.
    """
    # 1. Load environment variables
    if os.path.exists(env_file):
        logger.info(f"Loading environment variables from {env_file}")
        load_dotenv(dotenv_path=env_file)
    else:
        logger.warning(f"Environment file not found at {env_file}. Using existing environment.")

    # 2. Validate arguments
    if not os.path.isdir(directory):
        logger.error(f"Directory not found: {directory}")
        return
    if on_collision not in ["skip", "overwrite"]:
        logger.error(f"Invalid value for on_collision: {on_collision}. Must be 'skip' or 'overwrite'.")
        return

    logger.info(
        "Starting batch process",
        directory=directory,
        user_id=user_id,
        on_collision=on_collision,
        recursive=recursive,
        dry_run=dry_run,
    )

    # 3. Find image files
    supported_extensions = [".jpg", ".jpeg", ".png", ".heic", ".heif"]
    image_files = []
    if recursive:
        for root, _, files in os.walk(directory):
            for name in files:
                if os.path.splitext(name)[1].lower() in supported_extensions:
                    image_files.append(os.path.join(root, name))
    else:
        for name in os.listdir(directory):
            path = os.path.join(directory, name)
            if os.path.isfile(path) and os.path.splitext(name)[1].lower() in supported_extensions:
                image_files.append(path)

    if not image_files:
        logger.warning("No image files found to process.")
        return

    logger.info(f"Found {len(image_files)} image(s) to process.")

    # 4. If dry-run, print files and exit
    if dry_run:
        print("\n--- Dry Run Mode: Files to be processed ---")
        for file_path in image_files:
            print(f"- {file_path}")
        print("--- End of Dry Run ---")
        logger.info("Dry run completed. No files were uploaded.")
        return

    # 5. Prepare mock for authentication
    mock_user_info = UserInfo(user_id=user_id, email=f"{user_id}@cli.local", name="CLI User")
    mock_auth_service = MagicMock()
    mock_auth_service.ensure_authenticated.return_value = mock_user_info

    # 6. Process each file
    successful_uploads = 0
    failed_uploads = 0
    is_overwrite = on_collision == "overwrite"

    with patch('imgstream.ui.handlers.upload.get_auth_service') as mock_get_auth:
        mock_get_auth.return_value = mock_auth_service

        for file_path in image_files:
            filename = os.path.basename(file_path)
            logger.info(f"Processing {filename}...")
            try:
                with open(file_path, "rb") as f:
                    file_data = f.read()

                file_info = {
                    "filename": filename,
                    "data": file_data,
                    "size": len(file_data),
                }

                result = process_single_upload(file_info, is_overwrite=is_overwrite)

                if result.get("success"):
                    logger.info("Upload successful", filename=filename)
                    successful_uploads += 1
                else:
                    logger.error("Upload failed", filename=filename, error=result.get("error", "Unknown error"))
                    failed_uploads += 1

            except Exception as e:
                logger.error("An unexpected error occurred", filename=filename, error=str(e))
                failed_uploads += 1

    logger.info(
        "Batch upload finished.",
        successful=successful_uploads,
        failed=failed_uploads,
        total=len(image_files),
    )
    print(f"\nBatch upload complete. Successful: {successful_uploads}, Failed: {failed_uploads}")
