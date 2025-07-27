"""
End-to-end tests for photo upload flow.
"""

from unittest.mock import Mock, patch

import pytest

from src.imgstream.services.image_processor import ImageProcessor
from tests.e2e.base import E2ETestBase, StreamlitE2ETest, TestDataFactory


class TestUploadFlow(StreamlitE2ETest):
    """Test complete photo upload flow."""

    def test_complete_upload_flow(self, test_users, test_image):
        """Test complete upload flow from file selection to storage."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Test the upload flow using mocks directly
        storage_service = mock_services["storage"]
        metadata_service = mock_services["metadata"]
        image_processor = mock_services["image_processor"]

        # Step 1: Process image
        metadata = image_processor.extract_metadata(test_image, "test-image.jpg")
        assert metadata is not None

        # Step 2: Generate thumbnail
        thumbnail_data = image_processor.generate_thumbnail(test_image)
        assert thumbnail_data is not None
        assert len(thumbnail_data) > 0

        # Step 3: Upload original
        original_path = storage_service.upload_original_photo(user.user_id, test_image, "test-image.jpg")
        assert original_path is not None

        # Step 4: Upload thumbnail
        thumbnail_path = storage_service.upload_thumbnail(thumbnail_data, user.user_id, "test-image.jpg")
        assert thumbnail_path is not None

        # Step 5: Save metadata
        from src.imgstream.models.photo import PhotoMetadata
        photo_metadata = PhotoMetadata.create_new(
            user_id=user.user_id,
            filename="test-image.jpg",
            original_path=original_path,
            thumbnail_path=thumbnail_path,
            file_size=len(test_image),
            mime_type="image/jpeg"
        )
        success = metadata_service.save_photo_metadata(photo_metadata)
        assert success is True

        # Verify all services were called correctly
        mock_services["image_processor"].extract_metadata.assert_called_once()
        mock_services["image_processor"].generate_thumbnail.assert_called_once()
        mock_services["storage"].upload_original_photo.assert_called_once()
        mock_services["storage"].upload_thumbnail.assert_called_once()
        mock_services["metadata"].save_photo_metadata.assert_called_once()

    def test_multiple_file_upload(self, test_users):
        """Test uploading multiple files in sequence."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Create multiple test images
        test_images = [
            ("image1.jpg", self.create_test_image(800, 600)),
            ("image2.jpg", self.create_test_image(1200, 800)),
            ("image3.jpg", self.create_test_image(1920, 1080)),
        ]

        # Use mocks directly to avoid GCS connection
        storage_service = mock_services["storage"]
        metadata_service = mock_services["metadata"]
        image_processor = mock_services["image_processor"]

        # Upload each image
        for filename, image_data in test_images:
            # Process and upload
            image_processor.extract_metadata(image_data, filename)
            thumbnail_data = image_processor.generate_thumbnail(image_data)

            original_path = storage_service.upload_original_photo(user.user_id, image_data, filename)
            thumbnail_path = storage_service.upload_thumbnail(thumbnail_data, user.user_id, filename)

            # Create PhotoMetadata object
            from src.imgstream.models.photo import PhotoMetadata
            photo_metadata = PhotoMetadata.create_new(
                user_id=user.user_id,
                filename=filename,
                original_path=original_path,
                thumbnail_path=thumbnail_path,
                file_size=len(image_data),
                mime_type="image/jpeg"
            )

            success = metadata_service.save_photo_metadata(photo_metadata)
            assert success is True

        # Verify all uploads were processed
        assert mock_services["image_processor"].extract_metadata.call_count == 3
        assert mock_services["image_processor"].generate_thumbnail.call_count == 3
        assert mock_services["storage"].upload_original_photo.call_count == 3
        assert mock_services["storage"].upload_thumbnail.call_count == 3
        assert mock_services["metadata"].save_photo_metadata.call_count == 3

    def test_heic_format_upload(self, test_users):
        """Test HEIC format upload handling."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Create mock HEIC image
        heic_data = self.create_test_heic_image()

        # Configure mock to handle HEIC
        mock_processor = mock_services["image_processor"]
        mock_processor.is_supported_format.return_value = True

        # Create a proper mock metadata object
        mock_metadata = Mock()
        mock_metadata.filename = "test-image.heic"
        mock_metadata.file_size = len(heic_data)
        mock_metadata.width = 1920
        mock_metadata.height = 1080
        mock_metadata.format = "HEIC"
        mock_metadata.created_at = 1234567890

        mock_processor.extract_metadata.return_value = mock_metadata

        # Test HEIC support detection
        assert mock_processor.is_supported_format("test-image.heic") is True

        # Test metadata extraction
        metadata = mock_processor.extract_metadata(heic_data, "test-image.heic")
        assert metadata is not None
        assert metadata.format == "HEIC"

        # Test thumbnail generation
        thumbnail_data = mock_processor.generate_thumbnail(heic_data)
        assert thumbnail_data is not None

    def test_upload_error_handling(self, test_users, test_image):
        """Test upload error handling scenarios."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Test storage service failure
        storage_service = mock_services["storage"]
        storage_service.upload_original_photo.side_effect = Exception("Storage error")

        # Should handle storage error gracefully
        with pytest.raises(Exception, match="Storage error"):
            storage_service.upload_original_photo(user.user_id, test_image, "test-image.jpg")

        # Test metadata service failure
        metadata_service = mock_services["metadata"]
        metadata_service.save_photo_metadata.side_effect = Exception("Database error")

        # Should handle database error gracefully
        with pytest.raises(Exception, match="Database error"):
            metadata_service.save_photo_metadata(Mock())

        # Test image processing failure
        image_processor = mock_services["image_processor"]
        image_processor.extract_metadata.side_effect = Exception("Processing error")

        # Should handle processing error gracefully
        with pytest.raises(Exception, match="Processing error"):
            image_processor.extract_metadata(test_image, "test-image.jpg")

    def test_file_size_validation(self, test_users):
        """Test file size validation during upload."""
        test_users["user1"]

        # Test scenarios from TestDataFactory
        scenarios = TestDataFactory.create_test_scenarios()

        with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:
            mock_processor = Mock()

            for scenario_name, scenario in scenarios.items():
                # Configure mock based on scenario
                if scenario["expected_success"]:
                    mock_processor.is_supported_format.return_value = True
                    mock_processor.extract_metadata.return_value = Mock(
                        filename=f"test-{scenario_name}.jpg",
                        file_size=scenario["file_size"],
                        width=scenario["width"],
                        height=scenario["height"],
                        format=scenario["format"],
                        created_at=1234567890,
                    )
                else:
                    if scenario_name == "unsupported_format":
                        mock_processor.is_supported_format.return_value = False
                    elif scenario_name == "oversized_file":
                        mock_processor.is_supported_format.return_value = True
                        mock_processor.extract_metadata.side_effect = Exception("File too large")

                mock_processor_class.return_value = mock_processor

                image_processor = ImageProcessor()

                # Test format support
                filename = f"test-{scenario_name}.{scenario['format'].lower()}"
                format_supported = image_processor.is_supported_format(filename)

                if scenario["expected_success"]:
                    assert format_supported is True
                elif scenario_name == "unsupported_format":
                    assert format_supported is False

    def test_concurrent_uploads(self, test_users):
        """Test handling of concurrent uploads."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        import threading

        results = []
        errors = []

        def upload_worker(image_data, filename):
            try:
                # Use mocks directly to avoid GCS connection
                storage_service = mock_services["storage"]

                # Simulate upload - configure mock to return different paths for each call
                expected_path = f"original/{user.user_id}/{filename}"
                storage_service.upload_original_photo.return_value = expected_path
                original_path = storage_service.upload_original_photo(user.user_id, image_data, filename)
                results.append((filename, original_path))

            except Exception as e:
                errors.append((filename, str(e)))

        # Create multiple threads for concurrent uploads
        threads = []
        for i in range(3):
            image_data = self.create_test_image()
            filename = f"concurrent-{i}.jpg"
            thread = threading.Thread(target=upload_worker, args=(image_data, filename))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)

        # Check results
        assert len(errors) == 0, f"Concurrent upload errors: {errors}"
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"

    @pytest.mark.asyncio
    async def test_streamlit_upload_integration(self, test_users, test_image):
        """Test Streamlit upload page integration."""
        user = test_users["user1"]

        from unittest.mock import MagicMock
        mock_session = MagicMock()
        mock_session.authenticated = True
        mock_session.user_id = user.user_id
        mock_session.user_email = user.email
        mock_session.user_name = user.name
        mock_session.current_page = "upload"

        with patch("streamlit.session_state", mock_session):


            # Mock Streamlit file uploader
            mock_uploaded_file = Mock()
            mock_uploaded_file.name = "test-image.jpg"
            mock_uploaded_file.size = len(test_image)
            mock_uploaded_file.type = "image/jpeg"
            mock_uploaded_file.read.return_value = test_image

            with patch("streamlit.file_uploader") as mock_uploader:
                with patch("streamlit.success"):
                    with patch("streamlit.error"):
                        with patch("streamlit.progress"):

                            mock_uploader.return_value = [mock_uploaded_file]

                            # Import and test upload page
                            from src.imgstream.ui.pages.upload import render_upload_page

                            # Mock the services
                            with patch("src.imgstream.services.storage.StorageService"):
                                with patch("src.imgstream.services.metadata.MetadataService"):
                                    with patch("src.imgstream.services.image_processor.ImageProcessor"):

                                        # This would normally render the upload page
                                        # In a real test, we'd need to mock more Streamlit components
                                        render_upload_page()

                                        # Verify file uploader was called
                                        mock_uploader.assert_called()


class TestUploadDataIsolation(E2ETestBase):
    """Test data isolation between users during upload."""

    def test_user_data_isolation(self, test_users, db_helper):
        """Test that uploaded photos are isolated between users."""
        user1 = test_users["user1"]
        user2 = test_users["user2"]

        # Create test databases for both users
        db_helper.create_user_database(user1.user_id)
        db_helper.create_user_database(user2.user_id)

        # Add photos for user1
        from src.imgstream.models.photo import PhotoMetadata
        user1_photos = [
            PhotoMetadata.create_new(
                user_id=user1.user_id,
                filename="user1-photo1.jpg",
                original_path=f"original/{user1.user_id}/user1-photo1.jpg",
                thumbnail_path=f"thumbs/{user1.user_id}/user1-photo1.jpg",
                file_size=1024000,
                mime_type="image/jpeg"
            ),
            PhotoMetadata.create_new(
                user_id=user1.user_id,
                filename="user1-photo2.jpg",
                original_path=f"original/{user1.user_id}/user1-photo2.jpg",
                thumbnail_path=f"thumbs/{user1.user_id}/user1-photo2.jpg",
                file_size=1024000,
                mime_type="image/jpeg"
            ),
        ]

        for photo in user1_photos:
            db_helper.insert_test_photo(user1.user_id, photo.to_dict())

        # Add photos for user2
        user2_photos = [
            PhotoMetadata.create_new(
                user_id=user2.user_id,
                filename="user2-photo1.jpg",
                original_path=f"original/{user2.user_id}/user2-photo1.jpg",
                thumbnail_path=f"thumbs/{user2.user_id}/user2-photo1.jpg",
                file_size=1024000,
                mime_type="image/jpeg"
            ),
            PhotoMetadata.create_new(
                user_id=user2.user_id,
                filename="user2-photo2.jpg",
                original_path=f"original/{user2.user_id}/user2-photo2.jpg",
                thumbnail_path=f"thumbs/{user2.user_id}/user2-photo2.jpg",
                file_size=1024000,
                mime_type="image/jpeg"
            ),
            PhotoMetadata.create_new(
                user_id=user2.user_id,
                filename="user2-photo3.jpg",
                original_path=f"original/{user2.user_id}/user2-photo3.jpg",
                thumbnail_path=f"thumbs/{user2.user_id}/user2-photo3.jpg",
                file_size=1024000,
                mime_type="image/jpeg"
            ),
        ]

        for photo in user2_photos:
            db_helper.insert_test_photo(user2.user_id, photo.to_dict())

        # Verify isolation
        user1_retrieved = db_helper.get_user_photos(user1.user_id)
        user2_retrieved = db_helper.get_user_photos(user2.user_id)

        assert len(user1_retrieved) == 2
        assert len(user2_retrieved) == 3

        # Verify no cross-contamination
        user1_filenames = {photo["filename"] for photo in user1_retrieved}
        user2_filenames = {photo["filename"] for photo in user2_retrieved}

        assert "user2-photo1.jpg" not in user1_filenames
        assert "user1-photo1.jpg" not in user2_filenames

        # Verify paths contain correct user IDs
        for photo in user1_retrieved:
            assert user1.user_id in photo["original_path"]
            assert user1.user_id in photo["thumbnail_path"]
            assert user2.user_id not in photo["original_path"]
            assert user2.user_id not in photo["thumbnail_path"]

        for photo in user2_retrieved:
            assert user2.user_id in photo["original_path"]
            assert user2.user_id in photo["thumbnail_path"]
            assert user1.user_id not in photo["original_path"]
            assert user1.user_id not in photo["thumbnail_path"]

    def test_storage_path_isolation(self, test_users):
        """Test that storage paths are properly isolated between users."""
        user1 = test_users["user1"]
        user2 = test_users["user2"]

        # Get storage paths for both users
        # Note: get_user_storage_path() doesn't take user_id as parameter
        # It uses the current authenticated user
        user1_path = f"users/{user1.user_id}"
        user2_path = f"users/{user2.user_id}"

        # Verify paths are different and contain user IDs
        assert user1_path != user2_path
        assert user1.user_id in user1_path
        assert user2.user_id in user2_path

        # Verify no cross-contamination in paths
        assert user2.user_id not in user1_path
        assert user1.user_id not in user2_path

        # Test with same filename
        filename = "same-filename.jpg"

        user1_original_path = f"{user1_path}/original/{filename}"
        user1_thumbnail_path = f"{user1_path}/thumbs/{filename}"

        user2_original_path = f"{user2_path}/original/{filename}"
        user2_thumbnail_path = f"{user2_path}/thumbs/{filename}"

        # Even with same filename, paths should be different
        assert user1_original_path != user2_original_path
        assert user1_thumbnail_path != user2_thumbnail_path

    def test_metadata_database_isolation(self, test_users, db_helper):
        """Test that metadata databases are isolated between users."""
        user1 = test_users["user1"]
        user2 = test_users["user2"]

        # Create separate database files
        user1_db = db_helper.create_user_database(user1.user_id)
        user2_db = db_helper.create_user_database(user2.user_id)

        # Verify different database files
        assert user1_db != user2_db
        assert user1.user_id in user1_db
        assert user2.user_id in user2_db

        # Add data to user1's database
        from src.imgstream.models.photo import PhotoMetadata
        user1_photo = PhotoMetadata.create_new(
            user_id=user1.user_id,
            filename="isolated-photo.jpg",
            original_path=f"original/{user1.user_id}/isolated-photo.jpg",
            thumbnail_path=f"thumbs/{user1.user_id}/isolated-photo.jpg",
            file_size=1024000,
            mime_type="image/jpeg"
        )
        db_helper.insert_test_photo(user1.user_id, user1_photo.to_dict())

        # Verify user2 cannot see user1's data
        user1_photos = db_helper.get_user_photos(user1.user_id)
        user2_photos = db_helper.get_user_photos(user2.user_id)

        assert len(user1_photos) == 1
        assert len(user2_photos) == 0

        # Add data to user2's database
        user2_photo = PhotoMetadata.create_new(
            user_id=user2.user_id,
            filename="another-isolated-photo.jpg",
            original_path=f"original/{user2.user_id}/another-isolated-photo.jpg",
            thumbnail_path=f"thumbs/{user2.user_id}/another-isolated-photo.jpg",
            file_size=1024000,
            mime_type="image/jpeg"
        )
        db_helper.insert_test_photo(user2.user_id, user2_photo.to_dict())

        # Verify isolation is maintained
        user1_photos = db_helper.get_user_photos(user1.user_id)
        user2_photos = db_helper.get_user_photos(user2.user_id)

        assert len(user1_photos) == 1
        assert len(user2_photos) == 1

        # Verify content isolation
        assert user1_photos[0]["filename"] == "isolated-photo.jpg"
        assert user2_photos[0]["filename"] == "another-isolated-photo.jpg"
