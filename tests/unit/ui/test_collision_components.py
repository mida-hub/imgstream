"""Unit tests for collision warning UI components."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import streamlit as st

from src.imgstream.ui.components.collision_components import (
    render_collision_warnings,
    render_collision_status_indicator,
    render_collision_help_section,
    clear_collision_decisions,
    get_collision_decisions_from_session,
    validate_collision_decisions,
)
from src.imgstream.models.photo import PhotoMetadata


class TestCollisionUIComponents:
    """Test collision warning UI components."""

    @pytest.fixture
    def sample_collision_results(self):
        """Create sample collision results for testing."""
        photo_metadata1 = PhotoMetadata(
            id="photo_123",
            user_id="test_user_123",
            filename="photo1.jpg",
            original_path="photos/test_user_123/original/photo1.jpg",
            thumbnail_path="photos/test_user_123/thumbs/photo1_thumb.jpg",
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            uploaded_at=datetime(2024, 1, 15, 11, 0, 0),
            file_size=1024000,
            mime_type="image/jpeg",
        )

        photo_metadata2 = PhotoMetadata(
            id="photo_456",
            user_id="test_user_123",
            filename="photo2.jpg",
            original_path="photos/test_user_123/original/photo2.jpg",
            thumbnail_path="photos/test_user_123/thumbs/photo2_thumb.jpg",
            created_at=datetime(2024, 1, 16, 14, 20, 0),
            uploaded_at=datetime(2024, 1, 16, 15, 0, 0),
            file_size=2048000,
            mime_type="image/jpeg",
        )

        return {
            "photo1.jpg": {
                "existing_photo": photo_metadata1,
                "existing_file_info": {
                    "upload_date": photo_metadata1.uploaded_at,
                    "file_size": photo_metadata1.file_size,
                    "creation_date": photo_metadata1.created_at,
                    "photo_id": photo_metadata1.id,
                },
                "user_decision": "pending",
                "warning_shown": False,
            },
            "photo2.jpg": {
                "existing_photo": photo_metadata2,
                "existing_file_info": {
                    "upload_date": photo_metadata2.uploaded_at,
                    "file_size": photo_metadata2.file_size,
                    "creation_date": photo_metadata2.created_at,
                    "photo_id": photo_metadata2.id,
                },
                "user_decision": "pending",
                "warning_shown": False,
            },
        }

    @patch("streamlit.session_state", {})
    @patch("streamlit.markdown")
    @patch("streamlit.expander")
    @patch("streamlit.divider")
    @patch("streamlit.container")
    @patch("streamlit.columns")
    @patch("streamlit.metric")
    @patch("streamlit.button")
    @patch("streamlit.success")
    @patch("streamlit.error")
    @patch("streamlit.warning")
    @patch("streamlit.info")
    def test_render_collision_warnings_empty_results(self, *mock_streamlit_functions):
        """Test render_collision_warnings with empty collision results."""
        result = render_collision_warnings({})
        assert result == {}

    @patch("streamlit.session_state", {})
    @patch("streamlit.markdown")
    @patch("streamlit.expander")
    @patch("streamlit.divider")
    @patch("streamlit.container")
    @patch("streamlit.columns")
    @patch("streamlit.metric")
    @patch("streamlit.button")
    @patch("streamlit.success")
    @patch("streamlit.error")
    @patch("streamlit.warning")
    @patch("streamlit.info")
    @patch("streamlit.write")
    @patch("streamlit.rerun")
    def test_render_collision_warnings_with_results(
        self, mock_rerun, mock_write, sample_collision_results, *mock_streamlit_functions
    ):
        """Test render_collision_warnings with collision results."""
        # Mock streamlit components
        mock_container = MagicMock()
        mock_container.__enter__ = Mock(return_value=mock_container)
        mock_container.__exit__ = Mock(return_value=None)

        mock_expander = MagicMock()
        mock_expander.__enter__ = Mock(return_value=mock_expander)
        mock_expander.__exit__ = Mock(return_value=None)

        # Find the container and expander mocks
        for mock_func in mock_streamlit_functions:
            if hasattr(mock_func, "_mock_name"):
                if "container" in str(mock_func._mock_name):
                    mock_func.return_value = mock_container
                elif "expander" in str(mock_func._mock_name):
                    mock_func.return_value = mock_expander
                elif "columns" in str(mock_func._mock_name):
                    mock_func.return_value = [MagicMock(), MagicMock(), MagicMock()]
                elif "button" in str(mock_func._mock_name):
                    mock_func.return_value = False

        result = render_collision_warnings(sample_collision_results)

        # Should return empty dict when no buttons are clicked
        assert isinstance(result, dict)

    @patch("streamlit.session_state", {"decision_photo1.jpg": "overwrite"})
    def test_get_collision_decisions_from_session(self, sample_collision_results):
        """Test retrieving collision decisions from session state."""
        decisions = get_collision_decisions_from_session(sample_collision_results)

        assert "photo1.jpg" in decisions
        assert decisions["photo1.jpg"] == "overwrite"
        assert "photo2.jpg" not in decisions

    @patch("streamlit.session_state", {"decision_photo1.jpg": "overwrite", "decision_photo2.jpg": "skip"})
    def test_clear_collision_decisions(self, sample_collision_results):
        """Test clearing collision decisions from session state."""
        # Verify initial state
        assert "decision_photo1.jpg" in st.session_state
        assert "decision_photo2.jpg" in st.session_state

        clear_collision_decisions(sample_collision_results)

        # Verify decisions are cleared
        assert "decision_photo1.jpg" not in st.session_state
        assert "decision_photo2.jpg" not in st.session_state

    def test_validate_collision_decisions_all_complete(self, sample_collision_results):
        """Test validation when all decisions are made."""
        user_decisions = {"photo1.jpg": "overwrite", "photo2.jpg": "skip"}

        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)

        assert all_complete is True
        assert pending_files == []

    def test_validate_collision_decisions_incomplete(self, sample_collision_results):
        """Test validation when some decisions are missing."""
        user_decisions = {
            "photo1.jpg": "overwrite"
            # photo2.jpg decision is missing
        }

        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)

        assert all_complete is False
        assert "photo2.jpg" in pending_files
        assert len(pending_files) == 1

    def test_validate_collision_decisions_pending_status(self, sample_collision_results):
        """Test validation when decisions are explicitly pending."""
        user_decisions = {"photo1.jpg": "overwrite", "photo2.jpg": "pending"}

        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)

        assert all_complete is False
        assert "photo2.jpg" in pending_files
        assert len(pending_files) == 1

    def test_validate_collision_decisions_empty_results(self):
        """Test validation with empty collision results."""
        all_complete, pending_files = validate_collision_decisions({}, {})

        assert all_complete is True
        assert pending_files == []

    @patch("streamlit.success")
    @patch("streamlit.info")
    @patch("streamlit.warning")
    @patch("streamlit.progress")
    def test_render_collision_status_indicator_complete(
        self, mock_progress, mock_warning, mock_info, mock_success, sample_collision_results
    ):
        """Test status indicator when all decisions are complete."""
        user_decisions = {"photo1.jpg": "overwrite", "photo2.jpg": "skip"}

        render_collision_status_indicator(sample_collision_results, user_decisions)

        # Should show success message
        mock_success.assert_called_once()
        mock_progress.assert_called_once_with(1.0, text="決定進捗: 2/2")

    @patch("streamlit.success")
    @patch("streamlit.info")
    @patch("streamlit.warning")
    @patch("streamlit.progress")
    def test_render_collision_status_indicator_partial(
        self, mock_progress, mock_warning, mock_info, mock_success, sample_collision_results
    ):
        """Test status indicator when some decisions are made."""
        user_decisions = {"photo1.jpg": "overwrite"}

        render_collision_status_indicator(sample_collision_results, user_decisions)

        # Should show info message
        mock_info.assert_called_once()
        mock_progress.assert_called_once_with(0.5, text="決定進捗: 1/2")

    @patch("streamlit.success")
    @patch("streamlit.info")
    @patch("streamlit.warning")
    @patch("streamlit.progress")
    def test_render_collision_status_indicator_none(
        self, mock_progress, mock_warning, mock_info, mock_success, sample_collision_results
    ):
        """Test status indicator when no decisions are made."""
        user_decisions = {}

        render_collision_status_indicator(sample_collision_results, user_decisions)

        # Should show warning message
        mock_warning.assert_called_once()
        mock_progress.assert_called_once_with(0.0, text="決定進捗: 0/2")

    @patch("streamlit.success")
    @patch("streamlit.info")
    @patch("streamlit.warning")
    @patch("streamlit.progress")
    def test_render_collision_status_indicator_empty_results(
        self, mock_progress, mock_warning, mock_info, mock_success
    ):
        """Test status indicator with empty collision results."""
        render_collision_status_indicator({}, {})

        # Should not call any streamlit functions
        mock_success.assert_not_called()
        mock_info.assert_not_called()
        mock_warning.assert_not_called()
        mock_progress.assert_not_called()

    @patch("streamlit.expander")
    @patch("streamlit.markdown")
    def test_render_collision_help_section(self, mock_markdown, mock_expander):
        """Test rendering of collision help section."""
        # Mock expander context manager
        mock_expander_context = MagicMock()
        mock_expander_context.__enter__ = Mock(return_value=mock_expander_context)
        mock_expander_context.__exit__ = Mock(return_value=None)
        mock_expander.return_value = mock_expander_context

        render_collision_help_section()

        # Should create expander and call markdown
        mock_expander.assert_called_once()
        mock_markdown.assert_called()

    def test_validate_collision_decisions_mixed_scenarios(self, sample_collision_results):
        """Test validation with various decision combinations."""
        # Test case 1: All overwrite
        user_decisions = {"photo1.jpg": "overwrite", "photo2.jpg": "overwrite"}
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)
        assert all_complete is True
        assert pending_files == []

        # Test case 2: All skip
        user_decisions = {"photo1.jpg": "skip", "photo2.jpg": "skip"}
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)
        assert all_complete is True
        assert pending_files == []

        # Test case 3: Mixed decisions
        user_decisions = {"photo1.jpg": "overwrite", "photo2.jpg": "skip"}
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)
        assert all_complete is True
        assert pending_files == []

        # Test case 4: No decisions
        user_decisions = {}
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)
        assert all_complete is False
        assert len(pending_files) == 2
        assert "photo1.jpg" in pending_files
        assert "photo2.jpg" in pending_files


class TestCollisionUIComponentsIntegration:
    """Integration tests for collision UI components."""

    @pytest.fixture
    def sample_collision_results(self):
        """Create sample collision results for integration testing."""
        photo_metadata = PhotoMetadata(
            id="photo_123",
            user_id="test_user_123",
            filename="test_photo.jpg",
            original_path="photos/test_user_123/original/test_photo.jpg",
            thumbnail_path="photos/test_user_123/thumbs/test_photo_thumb.jpg",
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            uploaded_at=datetime(2024, 1, 15, 11, 0, 0),
            file_size=1024000,
            mime_type="image/jpeg",
        )

        return {
            "test_photo.jpg": {
                "existing_photo": photo_metadata,
                "existing_file_info": {
                    "upload_date": photo_metadata.uploaded_at,
                    "file_size": photo_metadata.file_size,
                    "creation_date": photo_metadata.created_at,
                    "photo_id": photo_metadata.id,
                },
                "user_decision": "pending",
                "warning_shown": False,
            }
        }

    @patch("streamlit.session_state", {})
    def test_collision_workflow_integration(self, sample_collision_results):
        """Test complete collision handling workflow."""
        # Step 1: Get initial decisions (should be empty)
        initial_decisions = get_collision_decisions_from_session(sample_collision_results)
        assert initial_decisions == {}

        # Step 2: Validate decisions (should be incomplete)
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, initial_decisions)
        assert all_complete is False
        assert "test_photo.jpg" in pending_files

        # Step 3: Simulate user making a decision
        st.session_state["decision_test_photo.jpg"] = "overwrite"

        # Step 4: Get updated decisions
        updated_decisions = get_collision_decisions_from_session(sample_collision_results)
        assert updated_decisions["test_photo.jpg"] == "overwrite"

        # Step 5: Validate updated decisions (should be complete)
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, updated_decisions)
        assert all_complete is True
        assert pending_files == []

        # Step 6: Clear decisions
        clear_collision_decisions(sample_collision_results)

        # Step 7: Verify decisions are cleared
        final_decisions = get_collision_decisions_from_session(sample_collision_results)
        assert final_decisions == {}

    def test_decision_persistence_across_calls(self, sample_collision_results):
        """Test that decisions persist across multiple function calls."""
        with patch("streamlit.session_state", {}) as mock_session:
            # Make initial decision
            mock_session["decision_test_photo.jpg"] = "skip"

            # First call
            decisions1 = get_collision_decisions_from_session(sample_collision_results)
            assert decisions1["test_photo.jpg"] == "skip"

            # Second call should return same result
            decisions2 = get_collision_decisions_from_session(sample_collision_results)
            assert decisions2["test_photo.jpg"] == "skip"
            assert decisions1 == decisions2

    def test_validation_with_changing_decisions(self, sample_collision_results):
        """Test validation as decisions change over time."""
        # Start with no decisions
        user_decisions = {}
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)
        assert all_complete is False
        assert len(pending_files) == 1

        # Add a pending decision (should still be incomplete)
        user_decisions["test_photo.jpg"] = "pending"
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)
        assert all_complete is False
        assert len(pending_files) == 1

        # Make actual decision (should be complete)
        user_decisions["test_photo.jpg"] = "overwrite"
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)
        assert all_complete is True
        assert len(pending_files) == 0

        # Change decision (should still be complete)
        user_decisions["test_photo.jpg"] = "skip"
        all_complete, pending_files = validate_collision_decisions(sample_collision_results, user_decisions)
        assert all_complete is True
        assert len(pending_files) == 0
