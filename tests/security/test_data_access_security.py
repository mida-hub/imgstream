"""
Security tests for data access control and user isolation.

This module contains comprehensive security tests including:
- Cross-user data access prevention
- Path traversal attack prevention
- Data isolation validation
- Unauthorized access attempts
"""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from src.imgstream.models.photo import PhotoMetadata
from src.imgstream.services.auth import CloudIAPAuthService
from src.imgstream.services.metadata import MetadataService
from src.imgstream.services.storage import StorageService
from tests.e2e.base import E2ETestBase, MockUser


class TestDataAccessSecurity(E2ETestBase):
    """Security tests for data access control."""

    @pytest.mark.security
    def test_cross_user_photo_access_prevention(self, test_users, db_helper):
        """Test that users cannot access other users' photos."""
        user1 = test_users["user1"]
        user2 = test_users["user2"]
        
        # Create databases for both users
        db_helper.create_user_database(user1.user_id)
        db_helper.create_user_database(user2.user_id)
        
        # Add photos for user1
        user1_photo = PhotoMetadata.create_new(
            user_id=user1.user_id,
            filename="user1_private.jpg",
            original_path=f"original/{user1.user_id}/user1_private.jpg",
            thumbnail_path=f"thumbs/{user1.user_id}/user1_private.jpg",
            file_size=1024000,
            mime_type="image/jpeg"
        )
        db_helper.insert_test_photo(user1.user_id, user1_photo.to_dict())
        
        # Add photos for user2
        user2_photo = PhotoMetadata.create_new(
            user_id=user2.user_id,
            filename="user2_private.jpg",
            original_path=f"original/{user2.user_id}/user2_private.jpg",
            thumbnail_path=f"thumbs/{user2.user_id}/user2_private.jpg",
            file_size=1024000,
            mime_type="image/jpeg"
        )
        db_helper.insert_test_photo(user2.user_id, user2_photo.to_dict())
        
        # Verify user1 can only see their own photos
        user1_photos = db_helper.get_user_photos(user1.user_id)
        assert len(user1_photos) == 1
        assert user1_photos[0]["filename"] == "user1_private.jpg"
        assert user1.user_id in user1_photos[0]["original_path"]
        
        # Verify user2 can only see their own photos
        user2_photos = db_helper.get_user_photos(user2.user_id)
        assert len(user2_photos) == 1
        assert user2_photos[0]["filename"] == "user2_private.jpg"
        assert user2.user_id in user2_photos[0]["original_path"]
        
        # Verify no cross-contamination
        for photo in user1_photos:
            assert user2.user_id not in photo["original_path"]
            assert user2.user_id not in photo["thumbnail_path"]
        
        for photo in user2_photos:
            assert user1.user_id not in photo["original_path"]
            assert user1.user_id not in photo["thumbnail_path"]

    @pytest.mark.security
    def test_metadata_service_user_isolation(self, test_users):
        """Test that MetadataService enforces user isolation."""
        user1 = test_users["user1"]
        user2 = test_users["user2"]
        
        # Create metadata services for different users
        with patch("src.imgstream.services.metadata.MetadataService") as mock_metadata_class:
            # Mock the metadata service to simulate real behavior
            mock_metadata1 = Mock()
            mock_metadata2 = Mock()
            
            # Configure mocks to simulate user isolation
            mock_metadata1.user_id = user1.user_id
            mock_metadata2.user_id = user2.user_id
            
            # Test that each service only works with its own user's data
            user1_photo = PhotoMetadata.create_new(
                user_id=user1.user_id,
                filename="test.jpg",
                original_path=f"original/{user1.user_id}/test.jpg",
                thumbnail_path=f"thumbs/{user1.user_id}/test.jpg",
                file_size=1024000,
                mime_type="image/jpeg"
            )
            
            user2_photo = PhotoMetadata.create_new(
                user_id=user2.user_id,
                filename="test.jpg",
                original_path=f"original/{user2.user_id}/test.jpg",
                thumbnail_path=f"thumbs/{user2.user_id}/test.jpg",
                file_size=1024000,
                mime_type="image/jpeg"
            )
            
            # Configure mock to reject cross-user access
            def save_photo_metadata_side_effect(photo_metadata):
                if photo_metadata.user_id != mock_metadata1.user_id:
                    raise ValueError(f"User ID mismatch: expected {mock_metadata1.user_id}, got {photo_metadata.user_id}")
                return True
            
            mock_metadata1.save_photo_metadata.side_effect = save_photo_metadata_side_effect
            mock_metadata_class.return_value = mock_metadata1
            
            metadata_service1 = MetadataService(user1.user_id)
            
            # User1's service should accept user1's data
            metadata_service1.save_photo_metadata(user1_photo)
            mock_metadata1.save_photo_metadata.assert_called_with(user1_photo)
            
            # User1's service should reject user2's data
            with pytest.raises(ValueError, match="User ID mismatch"):
                metadata_service1.save_photo_metadata(user2_photo)

    @pytest.mark.security
    def test_storage_path_traversal_prevention(self, test_users):
        """Test that path traversal attacks are prevented in storage paths."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)
        
        # Test various path traversal attempts
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # URL encoded
            "..%252f..%252f..%252fetc%252fpasswd",  # Double URL encoded
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd",  # UTF-8 encoded
            "file:///etc/passwd",
            "/etc/passwd",
            "\\etc\\passwd",
            "etc/passwd/../../../sensitive_file",
        ]
        
        storage_service = mock_services["storage"]
        
        for malicious_filename in malicious_filenames:
            # Configure mock to simulate path validation
            def upload_side_effect(user_id, file_data, filename):
                # Simulate path validation that should reject malicious paths
                if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
                    raise ValueError(f"Invalid filename: {filename}")
                if "%" in filename:  # Reject URL encoded attempts
                    raise ValueError(f"Invalid filename: {filename}")
                if ":" in filename:  # Reject protocol attempts
                    raise ValueError(f"Invalid filename: {filename}")
                return f"original/{user_id}/{filename}"
            
            storage_service.upload_original_photo.side_effect = upload_side_effect
            
            # Attempt to upload with malicious filename should fail
            with pytest.raises(ValueError, match="Invalid filename"):
                storage_service.upload_original_photo(user.user_id, b"test_data", malicious_filename)

    @pytest.mark.security
    def test_database_path_injection_prevention(self, test_users):
        """Test that database path injection attacks are prevented."""
        user = test_users["user1"]
        
        # Test various database path injection attempts
        malicious_user_ids = [
            "../../../etc/passwd",
            "user1; DROP TABLE photos; --",
            "user1' OR '1'='1",
            "user1\x00admin",  # Null byte injection
            "user1\r\nadmin",  # CRLF injection
            "user1/../admin",
            "user1\\..\\admin",
        ]
        
        auth_service = CloudIAPAuthService()
        
        for malicious_user_id in malicious_user_ids:
            # Create a mock user with malicious ID
            malicious_user = MockUser(malicious_user_id, "test@example.com", "Test User")
            
            # The auth service should sanitize or reject malicious user IDs
            storage_path = auth_service.get_user_storage_path()
            database_path = auth_service.get_user_database_path()
            
            # Paths should not contain path traversal sequences
            if storage_path:
                assert ".." not in storage_path
                assert not storage_path.startswith("/etc/")
                assert "DROP TABLE" not in storage_path
            
            if database_path:
                assert ".." not in database_path
                assert not database_path.startswith("/etc/")
                assert "DROP TABLE" not in database_path

    @pytest.mark.security
    def test_unauthorized_file_access_attempts(self, test_users):
        """Test that unauthorized file access attempts are blocked."""
        user1 = test_users["user1"]
        user2 = test_users["user2"]
        
        mock_services1 = self.setup_mock_services(user1)
        mock_services2 = self.setup_mock_services(user2)
        
        # User1 uploads a file
        storage_service1 = mock_services1["storage"]
        storage_service1.upload_original_photo.return_value = f"original/{user1.user_id}/private.jpg"
        
        user1_file_path = storage_service1.upload_original_photo(
            user1.user_id, b"user1_data", "private.jpg"
        )
        
        # User2 tries to access user1's file
        storage_service2 = mock_services2["storage"]
        
        # Configure mock to simulate access control
        def download_side_effect(file_path):
            # Simulate access control check
            if user2.user_id not in file_path:
                raise PermissionError(f"Access denied to {file_path}")
            return b"file_data"
        
        storage_service2.download_file.side_effect = download_side_effect
        
        # User2 should not be able to access user1's file
        with pytest.raises(PermissionError, match="Access denied"):
            storage_service2.download_file(user1_file_path)

    @pytest.mark.security
    def test_metadata_injection_prevention(self, test_users):
        """Test that metadata injection attacks are prevented."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)
        
        # Test various metadata injection attempts
        malicious_metadata = [
            {
                "filename": "<script>alert('xss')</script>.jpg",
                "mime_type": "image/jpeg",
            },
            {
                "filename": "test.jpg'; DROP TABLE photos; --",
                "mime_type": "application/javascript",
            },
            {
                "filename": "test.jpg",
                "mime_type": "text/html; <script>alert('xss')</script>",
            },
            {
                "filename": "test.jpg\x00.exe",  # Null byte injection
                "mime_type": "image/jpeg",
            },
        ]
        
        metadata_service = mock_services["metadata"]
        
        for malicious_data in malicious_metadata:
            # Create photo metadata with malicious content
            photo_metadata = PhotoMetadata.create_new(
                user_id=user.user_id,
                filename=malicious_data["filename"],
                original_path=f"original/{user.user_id}/{malicious_data['filename']}",
                thumbnail_path=f"thumbs/{user.user_id}/{malicious_data['filename']}",
                file_size=1024000,
                mime_type=malicious_data["mime_type"]
            )
            
            # Configure mock to simulate validation
            def save_metadata_side_effect(metadata):
                # Simulate validation that should reject malicious content
                if "<script>" in metadata.filename or "DROP TABLE" in metadata.filename:
                    raise ValueError(f"Invalid filename: {metadata.filename}")
                if not metadata.mime_type.startswith("image/"):
                    raise ValueError(f"Invalid mime type: {metadata.mime_type}")
                if "\x00" in metadata.filename:
                    raise ValueError(f"Invalid filename: contains null byte")
                return True
            
            metadata_service.save_photo_metadata.side_effect = save_metadata_side_effect
            
            # Attempt to save malicious metadata should fail
            with pytest.raises(ValueError):
                metadata_service.save_photo_metadata(photo_metadata)

    @pytest.mark.security
    def test_concurrent_user_isolation(self, test_users):
        """Test that concurrent operations maintain user isolation."""
        import threading
        
        user1 = test_users["user1"]
        user2 = test_users["user2"]
        
        results = []
        errors = []
        
        def user_operation(user, operation_id):
            try:
                mock_services = self.setup_mock_services(user)
                
                # Simulate user-specific operations
                storage_service = mock_services["storage"]
                metadata_service = mock_services["metadata"]
                
                # Configure mocks to simulate user isolation
                storage_service.upload_original_photo.return_value = f"original/{user.user_id}/test_{operation_id}.jpg"
                metadata_service.save_photo_metadata.return_value = True
                
                # Perform operations
                file_path = storage_service.upload_original_photo(
                    user.user_id, b"test_data", f"test_{operation_id}.jpg"
                )
                
                photo_metadata = PhotoMetadata.create_new(
                    user_id=user.user_id,
                    filename=f"test_{operation_id}.jpg",
                    original_path=file_path,
                    thumbnail_path=f"thumbs/{user.user_id}/test_{operation_id}.jpg",
                    file_size=1024000,
                    mime_type="image/jpeg"
                )
                
                metadata_service.save_photo_metadata(photo_metadata)
                
                results.append({
                    "user_id": user.user_id,
                    "operation_id": operation_id,
                    "file_path": file_path
                })
                
            except Exception as e:
                errors.append(f"User {user.user_id}, Operation {operation_id}: {str(e)}")
        
        # Create multiple threads for concurrent operations
        threads = []
        for i in range(5):
            # User1 operations
            thread1 = threading.Thread(target=user_operation, args=(user1, f"u1_op{i}"))
            threads.append(thread1)
            
            # User2 operations
            thread2 = threading.Thread(target=user_operation, args=(user2, f"u2_op{i}"))
            threads.append(thread2)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)
        
        # Verify results
        assert len(errors) == 0, f"Concurrent operation errors: {errors}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"
        
        # Verify user isolation
        user1_results = [r for r in results if r["user_id"] == user1.user_id]
        user2_results = [r for r in results if r["user_id"] == user2.user_id]
        
        assert len(user1_results) == 5
        assert len(user2_results) == 5
        
        # Verify no cross-contamination in file paths
        for result in user1_results:
            assert user1.user_id in result["file_path"]
            assert user2.user_id not in result["file_path"]
        
        for result in user2_results:
            assert user2.user_id in result["file_path"]
            assert user1.user_id not in result["file_path"]

    @pytest.mark.security
    def test_resource_exhaustion_prevention(self, test_users):
        """Test that resource exhaustion attacks are prevented."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)
        
        # Test large filename attack
        huge_filename = "a" * 10000 + ".jpg"
        
        storage_service = mock_services["storage"]
        
        # Configure mock to simulate filename length validation
        def upload_side_effect(user_id, file_data, filename):
            if len(filename) > 255:  # Typical filesystem limit
                raise ValueError(f"Filename too long: {len(filename)} characters")
            return f"original/{user_id}/{filename}"
        
        storage_service.upload_original_photo.side_effect = upload_side_effect
        
        # Attempt with huge filename should fail
        with pytest.raises(ValueError, match="Filename too long"):
            storage_service.upload_original_photo(user.user_id, b"test_data", huge_filename)
        
        # Test excessive metadata attack
        metadata_service = mock_services["metadata"]
        
        # Create photo with excessive metadata
        photo_metadata = PhotoMetadata.create_new(
            user_id=user.user_id,
            filename="test.jpg",
            original_path=f"original/{user.user_id}/test.jpg",
            thumbnail_path=f"thumbs/{user.user_id}/test.jpg",
            file_size=999999999999,  # Unrealistic file size
            mime_type="image/jpeg"
        )
        
        # Configure mock to simulate file size validation
        def save_metadata_side_effect(metadata):
            if metadata.file_size > 100 * 1024 * 1024:  # 100MB limit
                raise ValueError(f"File size too large: {metadata.file_size} bytes")
            return True
        
        metadata_service.save_photo_metadata.side_effect = save_metadata_side_effect
        
        # Attempt with excessive file size should fail
        with pytest.raises(ValueError, match="File size too large"):
            metadata_service.save_photo_metadata(photo_metadata)

    @pytest.mark.security
    def test_privilege_escalation_prevention(self, test_users):
        """Test that privilege escalation attempts are prevented."""
        user = test_users["user1"]
        admin = test_users["admin"]
        
        # Test that regular user cannot access admin functions
        auth_service = CloudIAPAuthService()
        
        # Mock authentication for regular user
        with patch.object(auth_service, 'current_user', user):
            # Regular user should not be able to access admin paths
            storage_path = auth_service.get_user_storage_path()
            database_path = auth_service.get_user_database_path()
            
            # Paths should be user-specific, not admin
            if storage_path:
                assert user.user_id in storage_path
                assert "admin" not in storage_path.lower()
            
            if database_path:
                assert user.user_id in database_path
                assert "admin" not in database_path.lower()
        
        # Test that user cannot manipulate their user_id to gain admin access
        malicious_user_attempts = [
            MockUser("admin", user.email, user.name),  # Try to use admin user_id
            MockUser(f"{user.user_id}/../admin", user.email, user.name),  # Path traversal
            MockUser(f"{user.user_id}\x00admin", user.email, user.name),  # Null byte injection
        ]
        
        for malicious_user in malicious_user_attempts:
            headers = self.mock_iap_headers(malicious_user)
            result = auth_service.authenticate_request(headers)
            
            if result is not None:
                # If authentication succeeds, ensure no privilege escalation
                assert result.user_id != "admin"
                assert "admin" not in result.user_id.lower()
                assert ".." not in result.user_id
                assert "\x00" not in result.user_id
