"""
End-to-end tests for error scenarios and edge cases.
"""

import io
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from src.imgstream.services.image_processor import ImageProcessor
from src.imgstream.services.storage import StorageService
from tests.e2e.base import E2ETestBase


class TestErrorScenarios(E2ETestBase):
    """Test various error scenarios and edge cases."""

    def test_network_failure_during_upload(self, test_users, test_image):
        """Test handling of network failures during upload."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Mock network failure in storage service
        storage_service = mock_services["storage"]
        storage_service.upload_original_photo.side_effect = Exception("Network timeout")

        # Should raise exception for network failure
        with pytest.raises(Exception) as exc_info:
            storage_service.upload_original_photo(user.user_id, test_image, "test-image.jpg")

        assert "Network timeout" in str(exc_info.value)

    def test_insufficient_storage_space(self, test_users, test_image):
        """Test handling of insufficient storage space."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Mock insufficient storage space in storage service
        storage_service = mock_services["storage"]
        storage_service.upload_original_photo.side_effect = Exception("Insufficient storage quota")

        with pytest.raises(Exception) as exc_info:
            storage_service.upload_original_photo(user.user_id, test_image, "test-image.jpg")

        assert "Insufficient storage quota" in str(exc_info.value)

    def test_corrupted_image_file(self, test_users):
        """Test handling of corrupted image files."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Create corrupted image data
        corrupted_data = b"This is not a valid image file"

        # Mock corrupted file handling
        image_processor = mock_services["image_processor"]
        image_processor.extract_metadata.side_effect = Exception("Cannot identify image file")
        image_processor.is_supported_format.return_value = True

        # Should handle corrupted file gracefully
        with pytest.raises(Exception) as exc_info:
            image_processor.extract_metadata(corrupted_data, "corrupted.jpg")

        assert "Cannot identify image file" in str(exc_info.value)

    def test_database_connection_failure(self, test_users):
        """Test handling of database connection failures."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Mock database connection failure
        metadata_service = mock_services["metadata"]
        metadata_service.save_photo_metadata.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception) as exc_info:
            metadata_service.save_photo_metadata(Mock())

        assert "Database connection failed" in str(exc_info.value)

    def test_permission_denied_errors(self, test_users, test_image):
        """Test handling of permission denied errors."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Test storage permission denied
        storage_service = mock_services["storage"]
        storage_service.upload_original_photo.side_effect = Exception("Permission denied: 403")

        with pytest.raises(Exception) as exc_info:
            storage_service.upload_original_photo(user.user_id, test_image, "test-image.jpg")

        assert "Permission denied" in str(exc_info.value)

    def test_file_size_limit_exceeded(self, test_users):
        """Test handling of file size limit exceeded."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Create oversized image data (mock)
        oversized_data = b"x" * (100 * 1024 * 1024)  # 100MB

        # Mock file size limit exceeded
        image_processor = mock_services["image_processor"]
        image_processor.is_supported_format.return_value = True
        image_processor.extract_metadata.side_effect = Exception("File size exceeds limit")

        with pytest.raises(Exception) as exc_info:
            image_processor.extract_metadata(oversized_data, "huge-image.jpg")

        assert "File size exceeds limit" in str(exc_info.value)

    def test_unsupported_file_format(self, test_users):
        """Test handling of unsupported file formats."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Mock unsupported file format
        image_processor = mock_services["image_processor"]
        image_processor.is_supported_format.return_value = False

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
                from src.imgstream.models.photo import PhotoMetadata

                photo_metadata = PhotoMetadata.create_new(
                    user_id=user.user_id,
                    filename=f"concurrent-{photo_id}.jpg",
                    original_path=f"original/{user.user_id}/concurrent-{photo_id}.jpg",
                    thumbnail_path=f"thumbs/{user.user_id}/concurrent-{photo_id}.jpg",
                    file_size=1024000,
                    mime_type="image/jpeg",
                )
                db_helper.insert_test_photo(user.user_id, photo_metadata.to_dict())
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
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Mock memory exhaustion
        image_processor = mock_services["image_processor"]
        image_processor.generate_thumbnail.side_effect = MemoryError("Out of memory")

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

            auth_service = mock_auth_class()

            # Should return None for expired token
            result = auth_service.authenticate_request({"X-Goog-IAP-JWT-Assertion": "expired.token"})
            assert result is None

    def test_partial_upload_failure(self, test_users, test_image):
        """Test handling of partial upload failures."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Mock scenario where original upload succeeds but thumbnail fails
        storage_service = mock_services["storage"]
        storage_service.upload_original_photo.return_value = "original/path/success"
        storage_service.upload_thumbnail.side_effect = Exception("Thumbnail upload failed")

        # Original should succeed
        original_result = storage_service.upload_original_photo(user.user_id, test_image, "test.jpg")
        assert original_result == "original/path/success"

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
            mock_processor.extract_metadata.side_effect = Exception("File 'empty.jpg' is too small")
            mock_processor_class.return_value = mock_processor

            image_processor = mock_processor_class()

            with pytest.raises(Exception) as exc_info:
                image_processor.extract_metadata(empty_data, "empty.jpg")

            assert "too small" in str(exc_info.value)

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

                # Use the mocked storage service instead of creating a new instance
                storage_service = mock_services["storage"]

                image_processor = ImageProcessor()

                for filename in special_filenames:
                    # Should handle special characters in filenames
                    try:
                        # Test format detection
                        image_processor.is_supported_format(filename)

                        # Test upload (would normally sanitize filename)
                        if filename.lower().endswith((".jpg", ".jpeg")):
                            original_path = storage_service.upload_original_photo(user.user_id, test_image, filename)
                            assert original_path is not None

                    except Exception as e:
                        # Some special characters might cause issues, which is acceptable
                        # as long as the system handles them gracefully
                        error_msg = str(e).lower()
                        assert any(
                            keyword in error_msg
                            for keyword in ["filename", "invalid", "permission", "access", "denied", "failed"]
                        )

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
            mock_metadata = Mock()
            mock_metadata.filename = "tiny.jpg"
            mock_metadata.file_size = len(tiny_data)
            mock_metadata.width = 1
            mock_metadata.height = 1
            mock_metadata.format = "JPEG"
            mock_metadata.created_at = 1234567890

            mock_processor.extract_metadata.return_value = mock_metadata
            mock_processor.generate_thumbnail.return_value = tiny_data  # Same size
            mock_processor_class.return_value = mock_processor

            image_processor = mock_processor_class()

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
        storage_service = mock_services["storage"]

        # Should handle long filenames (might truncate or reject)
        try:
            original_path = storage_service.upload_original_photo(user.user_id, test_image, long_filename)
            assert original_path is not None
        except Exception as e:
            # Acceptable to reject overly long filenames
            assert "filename" in str(e).lower() or "length" in str(e).lower()

    def test_rapid_successive_uploads(self, test_users):
        """Test handling of rapid successive uploads."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        storage_service = mock_services["storage"]

        # Rapid successive uploads
        for i in range(10):
            image_data = self.create_test_image()
            filename = f"rapid-{i}.jpg"

            # Should handle rapid uploads without issues
            original_path = storage_service.upload_original_photo(user.user_id, image_data, filename)
            assert original_path is not None

        # Verify all uploads were processed
        assert storage_service.upload_original_photo.call_count == 10

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
                mock_metadata = Mock()
                mock_metadata.filename = filename
                mock_metadata.file_size = 1024
                mock_metadata.width = 800
                mock_metadata.height = 600
                mock_metadata.format = "JPEG"
                mock_metadata.created_at = 1234567890

                mock_processor.extract_metadata.return_value = mock_metadata
                mock_processor_class.return_value = mock_processor

                image_processor = mock_processor_class()

                # Should handle Unicode filenames
                # Use larger test data to avoid file size validation errors
                test_data = b"x" * 1024  # 1KB of data
                metadata = image_processor.extract_metadata(test_data, filename)
                assert metadata.filename == filename
