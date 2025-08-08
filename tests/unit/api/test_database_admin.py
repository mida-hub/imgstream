"""Tests for database administration API."""

import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

from imgstream.api.database_admin import (
    DatabaseAdminError,
    is_development_environment,
    require_development_environment,
    reset_user_database,
    get_database_status,
    validate_all_user_databases,
)


class TestDatabaseAdminEnvironment:
    """Test environment checking functionality."""

    def test_is_development_environment_development(self):
        """Test development environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            assert is_development_environment() is True

    def test_is_development_environment_dev(self):
        """Test dev environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            assert is_development_environment() is True

    def test_is_development_environment_test(self):
        """Test test environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            assert is_development_environment() is True

    def test_is_development_environment_testing(self):
        """Test testing environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "testing"}):
            assert is_development_environment() is True

    def test_is_development_environment_production(self):
        """Test production environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert is_development_environment() is False

    def test_is_development_environment_default(self):
        """Test default environment (production) detection."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_development_environment() is False

    def test_require_development_environment_success(self):
        """Test require_development_environment in dev environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            # Should not raise exception
            require_development_environment()

    def test_require_development_environment_failure(self):
        """Test require_development_environment in production environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(DatabaseAdminError) as exc_info:
                require_development_environment()
            
            assert "only available in development/test environments" in str(exc_info.value)


class TestDatabaseAdminOperations:
    """Test database administration operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = "admin_test_user"

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    @patch('imgstream.api.database_admin.get_metadata_service')
    def test_reset_user_database_success(self, mock_get_metadata_service):
        """Test successful user database reset."""
        # Mock metadata service
        mock_service = MagicMock()
        mock_service.force_reload_from_gcs.return_value = {
            "success": True,
            "operation": "database_reset",
            "user_id": self.user_id,
            "local_db_deleted": True,
            "gcs_database_exists": True,
            "download_successful": True,
            "reset_duration_seconds": 1.5,
        }
        mock_get_metadata_service.return_value = mock_service
        
        # Perform reset
        result = reset_user_database(self.user_id, confirm_reset=True)
        
        # Verify result
        assert result["success"] is True
        assert result["admin_operation"] is True
        assert result["environment"] == "development"
        assert "reset_timestamp" in result
        
        # Verify service was called correctly
        mock_service.force_reload_from_gcs.assert_called_once_with(confirm_reset=True)

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_reset_user_database_production_environment(self):
        """Test database reset fails in production environment."""
        with pytest.raises(DatabaseAdminError) as exc_info:
            reset_user_database(self.user_id, confirm_reset=True)
        
        assert "only available in development/test environments" in str(exc_info.value)

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_reset_user_database_no_confirmation(self):
        """Test database reset fails without confirmation."""
        with pytest.raises(DatabaseAdminError) as exc_info:
            reset_user_database(self.user_id, confirm_reset=False)
        
        assert "requires explicit confirmation" in str(exc_info.value)

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    @patch('imgstream.api.database_admin.get_metadata_service')
    def test_reset_user_database_service_failure(self, mock_get_metadata_service):
        """Test database reset when service fails."""
        # Mock metadata service to fail
        mock_service = MagicMock()
        mock_service.force_reload_from_gcs.side_effect = Exception("Service failed")
        mock_get_metadata_service.return_value = mock_service
        
        with pytest.raises(DatabaseAdminError) as exc_info:
            reset_user_database(self.user_id, confirm_reset=True)
        
        assert "Database reset failed" in str(exc_info.value)

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    @patch('imgstream.api.database_admin.get_metadata_service')
    def test_get_database_status_success(self, mock_get_metadata_service):
        """Test successful database status retrieval."""
        # Mock metadata service
        mock_service = MagicMock()
        mock_service.get_database_info.return_value = {
            "user_id": self.user_id,
            "local_db_exists": True,
            "photo_count": 10,
        }
        mock_service.validate_database_integrity.return_value = {
            "valid": True,
            "issues": [],
        }
        mock_get_metadata_service.return_value = mock_service
        
        # Get status
        status = get_database_status(self.user_id)
        
        # Verify result
        assert status["user_id"] == self.user_id
        assert status["environment"] == "development"
        assert "database_info" in status
        assert "integrity_validation" in status
        assert "status_timestamp" in status
        
        # Verify service methods were called
        mock_service.get_database_info.assert_called_once()
        mock_service.validate_database_integrity.assert_called_once()

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_get_database_status_production_environment(self):
        """Test database status fails in production environment."""
        with pytest.raises(DatabaseAdminError) as exc_info:
            get_database_status(self.user_id)
        
        assert "only available in development/test environments" in str(exc_info.value)

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    @patch('imgstream.api.database_admin.get_metadata_service')
    def test_get_database_status_service_failure(self, mock_get_metadata_service):
        """Test database status when service fails."""
        # Mock metadata service to fail
        mock_service = MagicMock()
        mock_service.get_database_info.side_effect = Exception("Service failed")
        mock_get_metadata_service.return_value = mock_service
        
        with pytest.raises(DatabaseAdminError) as exc_info:
            get_database_status(self.user_id)
        
        assert "Failed to get database status" in str(exc_info.value)

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_validate_all_user_databases_success(self):
        """Test bulk database validation."""
        result = validate_all_user_databases()
        
        # Verify result structure
        assert result["operation"] == "validate_all_databases"
        assert result["environment"] == "development"
        assert "validation_timestamp" in result
        assert result["total_users"] == 0  # Placeholder implementation
        assert "Bulk validation not implemented" in result["message"]

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_validate_all_user_databases_production_environment(self):
        """Test bulk validation fails in production environment."""
        with pytest.raises(DatabaseAdminError) as exc_info:
            validate_all_user_databases()
        
        assert "only available in development/test environments" in str(exc_info.value)


class TestDatabaseAdminIntegration:
    """Integration tests for database admin functionality."""

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    @patch('imgstream.api.database_admin.get_metadata_service')
    def test_complete_admin_workflow(self, mock_get_metadata_service):
        """Test complete admin workflow: status -> reset -> status."""
        user_id = "workflow_test_user"
        
        # Mock metadata service
        mock_service = MagicMock()
        
        # Initial status
        mock_service.get_database_info.return_value = {
            "user_id": user_id,
            "local_db_exists": True,
            "photo_count": 5,
        }
        mock_service.validate_database_integrity.return_value = {
            "valid": True,
            "issues": [],
        }
        
        # Reset operation
        mock_service.force_reload_from_gcs.return_value = {
            "success": True,
            "operation": "database_reset",
            "user_id": user_id,
            "reset_duration_seconds": 2.0,
        }
        
        mock_get_metadata_service.return_value = mock_service
        
        # Step 1: Get initial status
        initial_status = get_database_status(user_id)
        assert initial_status["user_id"] == user_id
        assert initial_status["database_info"]["photo_count"] == 5
        
        # Step 2: Reset database
        reset_result = reset_user_database(user_id, confirm_reset=True)
        assert reset_result["success"] is True
        assert reset_result["admin_operation"] is True
        
        # Step 3: Get status after reset
        # Update mock for post-reset status
        mock_service.get_database_info.return_value = {
            "user_id": user_id,
            "local_db_exists": True,
            "photo_count": 0,  # Reset database should have no photos
        }
        
        final_status = get_database_status(user_id)
        assert final_status["user_id"] == user_id
        assert final_status["database_info"]["photo_count"] == 0
        
        # Verify all service methods were called
        assert mock_service.get_database_info.call_count == 2
        assert mock_service.validate_database_integrity.call_count == 2
        mock_service.force_reload_from_gcs.assert_called_once_with(confirm_reset=True)

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    @patch('imgstream.api.database_admin.get_metadata_service')
    def test_admin_operations_with_integrity_issues(self, mock_get_metadata_service):
        """Test admin operations when database has integrity issues."""
        user_id = "integrity_test_user"
        
        # Mock metadata service with integrity issues
        mock_service = MagicMock()
        mock_service.get_database_info.return_value = {
            "user_id": user_id,
            "local_db_exists": True,
            "photo_count": 10,
        }
        mock_service.validate_database_integrity.return_value = {
            "valid": False,
            "issues": [
                "Found 2 orphaned records without user_id",
                "Found duplicate filenames: test.jpg (3 copies)",
            ],
        }
        mock_service.force_reload_from_gcs.return_value = {
            "success": True,
            "operation": "database_reset",
            "user_id": user_id,
        }
        
        mock_get_metadata_service.return_value = mock_service
        
        # Get status - should show integrity issues
        status = get_database_status(user_id)
        integrity = status["integrity_validation"]
        assert integrity["valid"] is False
        assert len(integrity["issues"]) == 2
        
        # Reset should still work despite integrity issues
        reset_result = reset_user_database(user_id, confirm_reset=True)
        assert reset_result["success"] is True

    @patch.dict(os.environ, {"ENVIRONMENT": "test"})
    def test_admin_operations_in_test_environment(self):
        """Test that admin operations work in test environment."""
        # Should not raise exception
        require_development_environment()
        
        # Bulk validation should work
        result = validate_all_user_databases()
        assert result["environment"] == "test"

    def test_admin_error_inheritance(self):
        """Test DatabaseAdminError is properly defined."""
        error = DatabaseAdminError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
