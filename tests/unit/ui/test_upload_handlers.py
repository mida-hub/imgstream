"""Tests for upload handlers monitoring functionality."""

from unittest.mock import patch, MagicMock

from imgstream.ui.handlers.upload import (
    collect_user_collision_decisions,
)


class TestCollisionDecisionMonitoring:
    """Test collision decision monitoring functions."""

    @patch("streamlit.session_state", new_callable=dict)
    def test_collect_user_collision_decisions_creates_start_time(self, mock_session_state):
        """Test that decision start time is created if not present."""
        collision_results = {
            "test1.jpg": {
                "existing_photo": {"id": "photo_123"},
                "existing_file_info": {"file_size": 1024, "upload_date": "2023-01-01"},
                "user_decision": "pending",
            }
        }

        # Don't set decision_start in session state
        mock_session_state.update(
            {
                "collision_decision_test1.jpg": "pending",
            }
        )

        # Collect decisions
        collect_user_collision_decisions(mock_session_state, collision_results, "test_user")

        # Verify start time was created
        assert "decision_start_test1.jpg" in mock_session_state
        assert isinstance(mock_session_state["decision_start_test1.jpg"], float)


class TestSessionStateManagement:
    """Test session state management functions."""

    @patch("streamlit.session_state", new_callable=dict)
    def test_clear_upload_session_state(self, mock_session_state):
        """Test clearing upload-related session state."""
        from imgstream.ui.handlers.upload import clear_upload_session_state

        # Set up session state with various keys
        mock_session_state.update(
            {
                "collision_decision_test.jpg": "overwrite",
                "decision_start_test.jpg": 1000.0,
                "upload_progress": 50,
                "validation_errors": [],
                "other_key": "should_remain",
                "collision_decision_another.jpg": "skip",
            }
        )

        # Clear upload session state
        clear_upload_session_state(mock_session_state)

        # Verify upload-related keys were cleared
        assert "collision_decision_test.jpg" not in mock_session_state
        assert "decision_start_test.jpg" not in mock_session_state
        assert "upload_progress" not in mock_session_state
        assert "validation_errors" not in mock_session_state
        assert "collision_decision_another.jpg" not in mock_session_state

        # Verify other keys remain
        assert "other_key" in mock_session_state
        assert mock_session_state["other_key"] == "should_remain"


class TestIntegration:
    """Integration tests for upload handlers monitoring."""

    @patch("streamlit.session_state", new_callable=dict)
    def test_complete_decision_workflow(self, mock_session_state):
        """Test complete collision decision workflow."""
        # Set up initial collision results
        collision_results = {
            "test1.jpg": {
                "existing_photo": {"id": "photo_123"},
                "existing_file_info": {"file_size": 1024, "upload_date": "2023-01-01"},
                "user_decision": "pending",
                "fallback_mode": False,
            },
            "test2.jpg": {
                "existing_photo": {"id": "photo_456"},
                "existing_file_info": {"file_size": 2048, "upload_date": "2023-01-02"},
                "user_decision": "pending",
                "fallback_mode": True,
            },
        }

        # Simulate user making decisions
        mock_session_state.clear()
        mock_session_state.update(
            {
                "collision_decision_test1.jpg": "overwrite",
                "collision_decision_test2.jpg": "skip",
                "decision_start_test1.jpg": 1000.0,
                "decision_start_test2.jpg": 1001.0,
            }
        )

        # Collect decisions
        updated_results = collect_user_collision_decisions(mock_session_state, collision_results, "test_user")

        # Verify results were updated
        assert updated_results["test1.jpg"]["user_decision"] == "overwrite"
        assert updated_results["test2.jpg"]["user_decision"] == "skip"

        # Monitoring functionality removed for personal development use
        # Test passes if no exception is raised

    @patch("streamlit.session_state", new_callable=dict)
    def test_session_state_timing_accuracy(self, mock_session_state):
        """Test that timing measurements are reasonably accurate."""
        import time

        collision_results = {
            "test.jpg": {
                "existing_photo": {"id": "photo_123"},
                "existing_file_info": {"file_size": 1024, "upload_date": "2023-01-01"},
                "user_decision": "pending",
            }
        }

        # Set up session state without start time
        mock_session_state.clear()
        mock_session_state.update(
            {
                "collision_decision_test.jpg": "pending",
            }
        )

        # First call should create start time
        start_time = time.perf_counter()
        collect_user_collision_decisions(mock_session_state, collision_results, "test_user")

        # Verify start time was created and is reasonable
        assert "decision_start_test.jpg" in mock_session_state
        created_start_time = mock_session_state["decision_start_test.jpg"]

        # Should be close to when we called the function
        time_diff = abs(created_start_time - start_time)
        assert time_diff < 0.1  # Should be within 100ms  # Should be within 100ms
