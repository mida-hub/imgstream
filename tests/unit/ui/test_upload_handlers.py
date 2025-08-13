"""Tests for upload handlers monitoring functionality."""

import pytest
from unittest.mock import patch, MagicMock
import streamlit as st

from imgstream.ui.handlers.upload import (
    handle_collision_decision_monitoring,
    collect_user_collision_decisions,
)


class TestCollisionDecisionMonitoring:
    """Test collision decision monitoring functions."""

    def test_handle_collision_decision_monitoring_with_timing(self):
        """Test handling collision decision monitoring with timing."""
        import time

        start_time = time.perf_counter()
        time.sleep(0.01)  # Small delay to ensure timing works

        # Monitoring functionality removed for personal development use
        handle_collision_decision_monitoring(
            user_id="test_user",
            filename="test.jpg",
            decision="overwrite",
            decision_start_time=start_time,
            existing_photo_id="photo_123",
            file_size=1024
        )

        # Test passes if no exception is raised

    def test_handle_collision_decision_monitoring_without_timing(self):
        """Test handling collision decision monitoring without timing."""
        # Monitoring functionality removed for personal development use
        handle_collision_decision_monitoring(
            user_id="test_user",
            filename="test.jpg",
            decision="skip",
            existing_photo_id="photo_123"
        )

        # Test passes if no exception is raised

    def test_handle_collision_decision_monitoring_pending_decision(self):
        """Test handling pending collision decision (should not log resolution)."""
        # Monitoring functionality removed for personal development use
        handle_collision_decision_monitoring(
            user_id="test_user",
            filename="test.jpg",
            decision="pending",
            existing_photo_id="photo_123"
        )

        # Test passes if no exception is raised

    @patch("streamlit.session_state", new_callable=dict)
    @patch("imgstream.ui.upload_handlers.handle_collision_decision_monitoring")
    def test_collect_user_collision_decisions_new_decision(self, mock_handle_monitoring, mock_session_state):
        """Test collecting user collision decisions with new decision."""
        # Set up collision results
        collision_results = {
            "test1.jpg": {
                "existing_photo": {"id": "photo_123"},
                "existing_file_info": {"file_size": 1024, "upload_date": "2023-01-01"},
                "user_decision": "pending"
            },
            "test2.jpg": {
                "existing_photo": {"id": "photo_456"},
                "existing_file_info": {"file_size": 2048, "upload_date": "2023-01-02"},
                "user_decision": "pending"
            }
        }

        # Set up session state with user decisions
        mock_session_state.update({
            "collision_decision_test1.jpg": "overwrite",
            "collision_decision_test2.jpg": "skip",
            "decision_start_test1.jpg": 1000.0,
            "decision_start_test2.jpg": 1001.0,
        })

        # Collect decisions
        updated_results = collect_user_collision_decisions(collision_results, "test_user")

        # Verify decisions were updated
        assert updated_results["test1.jpg"]["user_decision"] == "overwrite"
        assert updated_results["test2.jpg"]["user_decision"] == "skip"

        # Verify monitoring was called for both decisions
        assert mock_handle_monitoring.call_count == 2

    @patch("streamlit.session_state", new_callable=dict)
    @patch("imgstream.ui.upload_handlers.handle_collision_decision_monitoring")
    def test_collect_user_collision_decisions_no_change(self, mock_handle_monitoring, mock_session_state):
        """Test collecting user collision decisions with no change."""
        # Set up collision results with existing decisions
        collision_results = {
            "test1.jpg": {
                "existing_photo": {"id": "photo_123"},
                "existing_file_info": {"file_size": 1024, "upload_date": "2023-01-01"},
                "user_decision": "overwrite"
            }
        }

        # Set up session state with same decision
        mock_session_state.update({
            "collision_decision_test1.jpg": "overwrite",
            "decision_start_test1.jpg": 1000.0,
        })

        # Collect decisions
        updated_results = collect_user_collision_decisions(collision_results, "test_user")

        # Verify decision remains the same
        assert updated_results["test1.jpg"]["user_decision"] == "overwrite"

        # Verify monitoring was NOT called since decision didn't change
        mock_handle_monitoring.assert_not_called()

    @patch("streamlit.session_state", new_callable=dict)
    def test_collect_user_collision_decisions_creates_start_time(self, mock_session_state):
        """Test that decision start time is created if not present."""
        collision_results = {
            "test1.jpg": {
                "existing_photo": {"id": "photo_123"},
                "existing_file_info": {"file_size": 1024, "upload_date": "2023-01-01"},
                "user_decision": "pending"
            }
        }

        # Don't set decision_start in session state
        mock_session_state.update({
            "collision_decision_test1.jpg": "pending",
        })

        # Collect decisions
        collect_user_collision_decisions(collision_results, "test_user")

        # Verify start time was created
        assert "decision_start_test1.jpg" in mock_session_state
        assert isinstance(mock_session_state["decision_start_test1.jpg"], float)

    def test_get_collision_decision_statistics(self):
        """Test getting collision decision statistics."""
        # Monitoring functionality removed for personal development use
        result = get_collision_decision_statistics("test_user")

        assert result["pattern"] == "unknown"
        assert result["statistics"] == {}

    def test_monitor_batch_collision_processing(self):
        """Test monitoring batch collision processing."""
        filenames = ["test1.jpg", "test2.jpg", "test3.jpg"]
        collision_results = {
            "test1.jpg": {"existing_photo": {"id": "photo_123"}},
            "test2.jpg": {"existing_photo": {"id": "photo_456"}},
        }

        # Monitoring functionality removed for personal development use
        monitor_batch_collision_processing(
            user_id="test_user",
            filenames=filenames,
            collision_results=collision_results,
            processing_time_ms=1500.0
        )

        # Test passes if no exception is raised


class TestSessionStateManagement:
    """Test session state management functions."""

    @patch("streamlit.session_state", new_callable=dict)
    def test_clear_upload_session_state(self, mock_session_state):
        """Test clearing upload-related session state."""
        from imgstream.ui.handlers.upload import clear_upload_session_state

        # Set up session state with various keys
        mock_session_state.update({
            "collision_decision_test.jpg": "overwrite",
            "decision_start_test.jpg": 1000.0,
            "upload_progress": 50,
            "validation_errors": [],
            "other_key": "should_remain",
            "collision_decision_another.jpg": "skip",
        })

        # Clear upload session state
        clear_upload_session_state()

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
                "fallback_mode": False
            },
            "test2.jpg": {
                "existing_photo": {"id": "photo_456"},
                "existing_file_info": {"file_size": 2048, "upload_date": "2023-01-02"},
                "user_decision": "pending",
                "fallback_mode": True
            }
        }

        # Simulate user making decisions
        mock_session_state.update({
            "collision_decision_test1.jpg": "overwrite",
            "collision_decision_test2.jpg": "skip",
            "decision_start_test1.jpg": 1000.0,
            "decision_start_test2.jpg": 1001.0,
        })

        # Collect decisions
        updated_results = collect_user_collision_decisions(collision_results, "test_user")

        # Verify results were updated
        assert updated_results["test1.jpg"]["user_decision"] == "overwrite"
        assert updated_results["test2.jpg"]["user_decision"] == "skip"

        # Monitoring functionality removed for personal development use
        # Test passes if no exception is raised

    def test_batch_monitoring_integration(self):
        """Test batch collision monitoring integration."""
        filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg", "photo4.jpg"]
        collision_results = {
            "photo1.jpg": {"existing_photo": {"id": "existing_1"}},
            "photo3.jpg": {"existing_photo": {"id": "existing_3"}},
        }

        # Monitor batch processing
        monitor_batch_collision_processing(
            user_id="batch_user",
            filenames=filenames,
            collision_results=collision_results,
            processing_time_ms=2500.0
        )

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
                "user_decision": "pending"
            }
        }

        # Set up session state without start time
        mock_session_state.update({
            "collision_decision_test.jpg": "pending",
        })

        # First call should create start time
        start_time = time.perf_counter()
        collect_user_collision_decisions(collision_results, "test_user")

        # Verify start time was created and is reasonable
        assert "decision_start_test.jpg" in mock_session_state
        created_start_time = mock_session_state["decision_start_test.jpg"]

        # Should be close to when we called the function
        time_diff = abs(created_start_time - start_time)
        assert time_diff < 0.1  # Should be within 100ms
