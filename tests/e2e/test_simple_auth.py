"""
Simple authentication tests for E2E testing.
"""

from unittest.mock import patch

from src.imgstream.services.auth import CloudIAPAuthService, UserInfo


class TestSimpleAuthentication:
    """Simple authentication tests."""

    def test_user_info_creation(self):
        """Test UserInfo creation and methods."""
        user_info = UserInfo(user_id="test-user-123", email="test@example.com", name="Test User")

        assert user_info.user_id == "test-user-123"
        assert user_info.email == "test@example.com"
        assert user_info.name == "Test User"

        # Test storage path generation
        storage_path = user_info.get_storage_path_prefix()
        assert "test_at_example_dot_com" in storage_path
        assert storage_path.startswith("photos/")

        # Test database path generation
        db_path = user_info.get_database_path()
        assert "test_at_example_dot_com" in db_path
        assert db_path.startswith("dbs/")
        assert db_path.endswith("metadata.db")

    def test_auth_service_initialization(self):
        """Test CloudIAPAuthService initialization."""
        auth_service = CloudIAPAuthService()

        # Should not be authenticated initially
        assert not auth_service.is_authenticated()

        # Should return None for current user
        assert auth_service.get_current_user() is None

    def test_user_path_isolation(self):
        """Test that different users get different paths."""
        user1 = UserInfo(user_id="user1", email="user1@example.com")
        user2 = UserInfo(user_id="user2", email="user2@example.com")

        path1 = user1.get_storage_path_prefix()
        path2 = user2.get_storage_path_prefix()

        # Paths should be different
        assert path1 != path2

        # Each path should contain the respective user's email
        assert "user1_at_example_dot_com" in path1
        assert "user2_at_example_dot_com" in path2

        # Cross-contamination check
        assert "user2_at_example_dot_com" not in path1
        assert "user1_at_example_dot_com" not in path2

    def test_empty_headers_authentication(self):
        """Test authentication with empty headers."""
        import os

        # Disable development mode for this test
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            auth_service = CloudIAPAuthService()

            # Empty headers should fail authentication
            user_info = auth_service.authenticate_request({})
            assert user_info is None
            assert not auth_service.is_authenticated()

    def test_missing_required_headers(self):
        """Test authentication with missing required headers."""
        import os
        from unittest.mock import patch

        # Disable development mode for this test
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            auth_service = CloudIAPAuthService()

            # Missing IAP JWT header
            headers = {
                "X-Goog-Authenticated-User-Email": "test@example.com",
                "X-Goog-Authenticated-User-ID": "test-user-123",
            }

            user_info = auth_service.authenticate_request(headers)
            # Should fail without proper IAP JWT header
            assert user_info is None
