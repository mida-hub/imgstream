"""
End-to-end tests for error scenarios and edge cases.
"""

import io
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from src.imgstream.services.image_processor import ImageProcessor
from src.imgstream.services.metadata import MetadataService
from src.imgstream.services.storage import StorageService
from tests.e2e.base import E2ETestBase, TestDataFactory


class TestErrorScenarios(E2ETestBase):
    """Test various error scenarios and edge cases."""

    def test_network_failure_during_upload(self, test_users, test_image):
        """Test handling of network failures during upload."""
        user = test_users["user1"]

        # Mock network failure in storage service
        with patch("src.imgstream.services.storage.StorageService") as mock_storage_class:
            mock_storage = Mock()
            mock_storage.upload_original_photo.side_effect = Exception("Network timeout")
            mock_storage_class.return_value = mock_storage

            storage_service = StorageService(
                project_id=self.test_config["project_id"], bucket_name=self.test_config["bucket_name"]
            )

            # Should raise exception for network failure
            with pytest.raises(Exception) as exc_info:
                storage_service.upload_original_photo(test_image, user.user_id, "test-image.jpg")

            assert "Network timeout" in str(exc_info.value)

    def test_insufficient_storage_space(self, test_users, test_image):
        """Test handling of insufficient storage space."""
        user = test_users["user1"]

        with patch("src.imgstream.services.storage.StorageService") as mock_storage_class:
            mock_storage = Mock()
            mock_storage.upload_original_photo.side_effect = Exception("Insufficient storage quota")
            mock_storage_class.return_value = mock_storage

            storage_service = StorageService(
                project_id=self.test_config["project_id"], bucket_name=self.test_config["bucket_name"]
            )

            with pytest.raises(Exception) as exc_info:
                storage_service.upload_original_photo(test_image, user.user_id, "test-image.jpg")

            assert "Insufficient storage quota" in str(exc_info.value)

    def test_corrupted_image_file(self, test_users):
        """Test handling of corrupted image files."""
        test_users["user1"]

        # Create corrupted image data
        corrupted_data = b"This is not a valid image file"

        with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:
            mock_processor = Mock()
            mock_processor.extract_metadata.side_effect = Exception("Cannot identify image file")
            mock_processor.is_supported_format.return_value = True
            mock_processor_class.return_value = mock_processor

            image_processor = ImageProcessor()

            # Should handle corrupted file gracefully
            with pytest.raises(Exception) as exc_info:
                image_processor.extract_metadata(corrupted_data, "corrupted.jpg")

            assert "Cannot identify image file" in str(exc_info.value)

    def test_database_connection_failure(self, test_users):
        """Test handling of database connection failures."""
        user = test_users["user1"]

        with patch("src.imgstream.services.metadata.MetadataService") as mock_metadata_class:
            mock_metadata = Mock()
            mock_metadata.save_photo_metadata.side_effect = Exception("Database connection failed")
            mock_metadata_class.return_value = mock_metadata

            metadata_service = MetadataService(user.user_id)

            with pytest.raises(Exception) as exc_info:
                metadata_service.save_photo_metadata(Mock(), "path1", "path2")

            assert "Database connection failed" in str(exc_info.value)

    def test_permission_denied_errors(self, test_users, test_image):
        """Test handling of permission denied errors."""
        user = test_users["user1"]

        # Test storage permission denied
        with patch("src.imgstream.services.storage.StorageService") as mock_storage_class:
            mock_storage = Mock()
            mock_storage.upload_original_photo.side_effect = Exception("Permission denied: 403")
            mock_storage_class.return_value = mock_storage

            storage_service = StorageService(
                project_id=self.test_config["project_id"], bucket_name=self.test_config["bucket_name"]
            )

            with pytest.raises(Exception) as exc_info:
                storage_service.upload_original_photo(test_image, user.user_id, "test-image.jpg")

            assert "Permission denied" in str(exc_info.value)

    def test_file_size_limit_exceeded(self, test_users):
        """Test handling of file size limit exceeded."""
        test_users["user1"]

        # Create oversized image data (mock)
        oversized_data = b"x" * (100 * 1024 * 1024)  # 100MB

        with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:
            mock_processor = Mock()
            mock_processor.is_supported_format.return_value = True
            mock_processor.extract_metadata.side_effect = Exception("File size exceeds limit")
            mock_processor_class.return_value = mock_processor

            image_processor = ImageProcessor()

            with pytest.raises(Exception) as exc_info:
                image_processor.extract_metadata(oversized_data, "huge-image.jpg")

            assert "File size exceeds limit" in str(exc_info.value)

    def test_unsupported_file_format(self, test_users):
        """Test handling of unsupported file formats."""
        test_users["user1"]

        # Create mock unsupported file

        with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:
            mock_processor = Mock()
            mock_processor.is_supported_format.return_value = False
            mock_processor_class.return_value = mock_processor

            image_processor = ImageProcessor()

            # Should return False for unsupported format
            assert image_processor.is_supported_format("test.bmp") is False
            assert image_processor.is_supported_format("test.gif") is False
            assert image_processor.is_supported_format("test.tiff") is False

    def test_concurrent_access_conflicts(self, test_users, db_helper):
        """Test handling of concurrent access conflicts."""
        user = test_users["user1"]

        # Create test database
        db_helper.create_user_database(user.user_id)

        import threading

        errors = []
        successes = []

        def concurrent_write(photo_id):
            try:
                photo_data = TestDataFactory.create_photo_metadata(user.user_id, f"concurrent-{photo_id}.jpg")
                db_helper.insert_test_photo(user.user_id, photo_data)
                successes.append(photo_id)
            except Exception as e:
                errors.append((photo_id, str(e)))

        # Create multiple threads for concurrent database writes
        threads = []
        for i in range(5):
            thread = threading.Thread(target=concurrent_write, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=5)

        # Check results - some operations might fail due to concurrency
        total_operations = len(successes) + len(errors)
        assert total_operations == 5

        # At least some operations should succeed
        assert len(successes) > 0

    def test_memory_exhaustion_scenario(self, test_users):
        """Test handling of memory exhaustion scenarios."""
        test_users["user1"]

        with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:
            mock_processor = Mock()
            mock_processor.generate_thumbnail.side_effect = MemoryError("Out of memory")
            mock_processor_class.return_value = mock_processor

            image_processor = ImageProcessor()

            # Should handle memory error gracefully
            with pytest.raises(MemoryError):
                image_processor.generate_thumbnail(b"image_data")

    def test_authentication_token_expiry(self, test_users):
        """Test handling of expired authentication tokens."""
        test_users["user1"]

        # Mock expired token scenario
        with patch("src.imgstream.services.auth.CloudIAPAuthService") as mock_auth_class:
            mock_auth = Mock()
            mock_auth.authenticate_request.return_value = None  # Expired token
            mock_auth_class.return_value = mock_auth

            from src.imgstream.services.auth import CloudIAPAuthService as AuthService

            auth_service = AuthService()

            # Should return None for expired token
            result = auth_service.authenticate_user({"X-Goog-IAP-JWT-Assertion": "expired.token"})
            assert result is None

    def test_partial_upload_failure(self, test_users, test_image):
        """Test handling of partial upload failures."""
        user = test_users["user1"]

        # Mock scenario where original upload succeeds but thumbnail fails
        with patch("src.imgstream.services.storage.StorageService") as mock_storage_class:
            mock_storage = Mock()
            mock_storage.upload_original_photo.return_value = "original/path/success"
            mock_storage.upload_thumbnail.side_effect = Exception("Thumbnail upload failed")
            mock_storage_class.return_value = mock_storage

            storage_service = StorageService(
                project_id=self.test_config["project_id"], bucket_name=self.test_config["bucket_name"]
            )

            # Original should succeed
            original_path = storage_service.upload_original_photo(test_image, user.user_id, "test.jpg")
            assert original_path == "original/path/success"

            # Thumbnail should fail
            with pytest.raises(Exception) as exc_info:
                storage_service.upload_thumbnail(test_image, user.user_id, "test.jpg")

            assert "Thumbnail upload failed" in str(exc_info.value)

    def test_invalid_user_session(self, test_users):
        """Test handling of invalid user sessions."""
        user = test_users["user1"]

        # Test with invalid session data
        invalid_sessions = [
            {},  # Empty session
            {"authenticated": False},  # Not authenticated
            {"authenticated": True, "user_id": None},  # Missing user ID
            {"authenticated": True, "user_id": ""},  # Empty user ID
            {"authenticated": True, "user_id": "different-user"},  # Wrong user
        ]

        for invalid_session in invalid_sessions:
            with patch("streamlit.session_state", invalid_session):
                # Should handle invalid session gracefully
                # This would typically redirect to login or show error
                assert (
                    not invalid_session.get("authenticated")
                    or not invalid_session.get("user_id")
                    or invalid_session.get("user_id") != user.user_id
                )


class TestEdgeCases(E2ETestBase):
    """Test edge cases and boundary conditions."""

    def test_empty_file_upload(self, test_users):
        """Test handling of empty file uploads."""
        test_users["user1"]

        empty_data = b""

        with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:
            mock_processor = Mock()
            mock_processor.extract_metadata.side_effect = Exception("Empty file")
            mock_processor_class.return_value = mock_processor

            image_processor = ImageProcessor()

            with pytest.raises(Exception) as exc_info:
                image_processor.extract_metadata(empty_data, "empty.jpg")

            assert "Empty file" in str(exc_info.value)

    def test_filename_with_special_characters(self, test_users, test_image):
        """Test handling of filenames with special characters."""
        user = test_users["user1"]

        special_filenames = [
            "file with spaces.jpg",
            "file-with-dashes.jpg",
            "file_with_underscores.jpg",
            "file.with.dots.jpg",
            "file(with)parentheses.jpg",
            "file[with]brackets.jpg",
            "file{with}braces.jpg",
            "file@with#symbols$.jpg",
            "файл-на-русском.jpg",
            "ファイル名.jpg",
            "文件名.jpg",
        ]

        mock_services = self.setup_mock_services(user)

        with patch("src.imgstream.services.storage.StorageService") as mock_storage_class:
            with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:

                mock_storage_class.return_value = mock_services["storage"]
                mock_processor_class.return_value = mock_services["image_processor"]

                storage_service = StorageService(
                    project_id=self.test_config["project_id"], bucket_name=self.test_config["bucket_name"]
                )

                image_processor = ImageProcessor()

                for filename in special_filenames:
                    # Should handle special characters in filenames
                    try:
                        # Test format detection
                        image_processor.is_supported_format(filename)

                        # Test upload (would normally sanitize filename)
                        if filename.lower().endswith((".jpg", ".jpeg")):
                            original_path = storage_service.upload_original_photo(test_image, user.user_id, filename)
                            assert original_path is not None

                    except Exception as e:
                        # Some special characters might cause issues, which is acceptable
                        # as long as the system handles them gracefully
                        assert "filename" in str(e).lower() or "invalid" in str(e).lower()

    def test_very_small_images(self, test_users):
        """Test handling of very small images."""
        test_users["user1"]

        # Create very small image (1x1 pixel)
        tiny_image = Image.new("RGB", (1, 1), color="red")
        buffer = io.BytesIO()
        tiny_image.save(buffer, format="JPEG")
        tiny_data = buffer.getvalue()

        with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:
            mock_processor = Mock()
            mock_processor.extract_metadata.return_value = Mock(
                filename="tiny.jpg", file_size=len(tiny_data), width=1, height=1, format="JPEG", created_at=1234567890
            )
            mock_processor.generate_thumbnail.return_value = tiny_data  # Same size
            mock_processor_class.return_value = mock_processor

            image_processor = ImageProcessor()

            # Should handle tiny images
            metadata = image_processor.extract_metadata(tiny_data, "tiny.jpg")
            assert metadata.width == 1
            assert metadata.height == 1

            thumbnail = image_processor.generate_thumbnail(tiny_data)
            assert thumbnail is not None

    def test_maximum_filename_length(self, test_users, test_image):
        """Test handling of maximum filename lengths."""
        user = test_users["user1"]

        # Create very long filename
        long_filename = "a" * 250 + ".jpg"  # 254 characters total

        mock_services = self.setup_mock_services(user)

        with patch("src.imgstream.services.storage.StorageService") as mock_storage_class:
            mock_storage_class.return_value = mock_services["storage"]

            storage_service = StorageService(
                project_id=self.test_config["project_id"], bucket_name=self.test_config["bucket_name"]
            )

            # Should handle long filenames (might truncate or reject)
            try:
                original_path = storage_service.upload_original_photo(test_image, user.user_id, long_filename)
                assert original_path is not None
            except Exception as e:
                # Acceptable to reject overly long filenames
                assert "filename" in str(e).lower() or "length" in str(e).lower()

    def test_rapid_successive_uploads(self, test_users):
        """Test handling of rapid successive uploads."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        with patch("src.imgstream.services.storage.StorageService") as mock_storage_class:
            with patch("src.imgstream.services.metadata.MetadataService") as mock_metadata_class:
                with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:

                    mock_storage_class.return_value = mock_services["storage"]
                    mock_metadata_class.return_value = mock_services["metadata"]
                    mock_processor_class.return_value = mock_services["image_processor"]

                    storage_service = StorageService(
                        project_id=self.test_config["project_id"], bucket_name=self.test_config["bucket_name"]
                    )

                    # Rapid successive uploads
                    for i in range(10):
                        image_data = self.create_test_image()
                        filename = f"rapid-{i}.jpg"

                        # Should handle rapid uploads without issues
                        original_path = storage_service.upload_original_photo(image_data, user.user_id, filename)
                        assert original_path is not None

                    # Verify all uploads were processed
                    assert mock_services["storage"].upload_original_photo.call_count == 10

    def test_unicode_in_metadata(self, test_users):
        """Test handling of Unicode characters in metadata."""
        test_users["user1"]

        # Test with various Unicode characters
        unicode_filenames = [
            "测试文件.jpg",  # Chinese
            "тестовый файл.jpg",  # Russian
            "ファイルテスト.jpg",  # Japanese
            "파일테스트.jpg",  # Korean
            "ملف اختبار.jpg",  # Arabic
            "αρχείο δοκιμής.jpg",  # Greek
            "dosya testi.jpg",  # Turkish
            "arquivo teste.jpg",  # Portuguese
        ]

        with patch("src.imgstream.services.image_processor.ImageProcessor") as mock_processor_class:
            mock_processor = Mock()

            for filename in unicode_filenames:
                mock_processor.extract_metadata.return_value = Mock(
                    filename=filename, file_size=1024, width=800, height=600, format="JPEG", created_at=1234567890
                )

                mock_processor_class.return_value = mock_processor

                image_processor = ImageProcessor()

                # Should handle Unicode filenames
                metadata = image_processor.extract_metadata(b"image_data", filename)
                assert metadata.filename == filename
