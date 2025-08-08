"""Tests for upload handlers monitoring functionality."""

import pytest
from unittest.mock import patch, MagicMock
import streamlit as st

from imgstream.ui.upload_handlers import (
    handle_collision_decision_monitoring,
    collect_user_collision_decisions,
    get_collision_decision_statistics,
    monitor_batch_collision_processing,
)


class TestCollisionDecisionMonitoring:
    """Test collision decision monitoring functions."""

    @patch("imgstream.ui.upload_handlers.log_user_decision")
    @patch("imgstream.ui.upload_handlers.log_collision_resolved")
    def test_handle_collision_decision_monitoring_with_timing(self, mock_log_resolved, mock_log_decision):
        """Test handling collision decision monitoring with timing."""
        import time
        
        start_time = time.perf_counter()
        time.sleep(0.01)  # Small delay to ensure timing works
        
        handle_collision_decision_monitoring(
            user_id="test_user",
            filename="test.jpg",
            decision="overwrite",
            decision_start_time=start_time,
            existing_photo_id="photo_123",
            file_size=1024
        )
        
        # Verify user decision was logged
        mock_log_decision.assert_called_once()
        call_args = mock_log_decision.call_args[1]
        assert call_args["user_id"] == "test_user"
        assert call_args["filename"] == "test.jpg"
        assert call_args["decision"] == "overwrite"
        assert call_args["decision_time_ms"] > 0  # Should have some timing
        assert call_args["existing_photo_id"] == "photo_123"
        assert call_args["file_size"] == 1024
        
        # Verify collision resolution was logged
        mock_log_resolved.assert_called_once()
        resolved_args = mock_log_resolved.call_args[1]
        assert resolved_args["user_id"] == "test_user"
        assert resolved_args["filename"] == "test.jpg"
        assert resolved_args["user_decision"] == "overwrite"

    @patch("imgstream.ui.upload_handlers.log_user_decision")
    @patch("imgstream.ui.upload_handlers.log_collision_resolved")
    def test_handle_collision_decision_monitoring_without_timing(self, mock_log_resolved, mock_log_decision):
        """Test handling collision decision monitoring without timing."""
        handle_collision_decision_monitoring(
            user_id="test_user",
            filename="test.jpg",
            decision="skip",
            existing_photo_id="photo_123"
        )
        
        # Verify user decision was logged
        mock_log_decision.assert_called_once()
        call_args = mock_log_decision.call_args[1]
        assert call_args["user_id"] == "test_user"
        assert call_args["filename"] == "test.jpg"
        assert call_args["decision"] == "skip"
        assert call_args["decision_time_ms"] is None
        
        # Verify collision resolution was logged
        mock_log_resolved.assert_called_once()

    @patch("imgstream.ui.upload_handlers.log_user_decision")
    @patch("imgstream.ui.upload_handlers.log_collision_resolved")
    def test_handle_collision_decision_monitoring_pending_decision(self, mock_log_resolved, mock_log_decision):
        """Test handling pending collision decision (should not log resolution)."""
        handle_collision_decision_monitoring(
            user_id="test_user",
            filename="test.jpg",
            decision="pending",
            existing_photo_id="photo_123"
        )
        
        # Verify user decision was logged
        mock_log_decision.assert_called_once()
        
        # Verify collision resolution was NOT logged for pending decision
        mock_log_resolved.assert_not_called()

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

    @patch("imgstream.ui.upload_handlers.get_collision_monitor")
    def test_get_collision_decision_statistics(self, mock_get_monitor):
        """Test getting collision decision statistics."""
        mock_monitor = MagicMock()
        mock_monitor.get_user_behavior_patterns.return_value = {
            "pattern": "aggressive_overwriter",
            "statistics": {"overwrite_rate": 0.9}
        }
        mock_get_monitor.return_value = mock_monitor
        
        result = get_collision_decision_statistics("test_user")
        
        mock_monitor.get_user_behavior_patterns.assert_called_once_with("test_user")
        assert result["pattern"] == "aggressive_overwriter"
        assert result["statistics"]["overwrite_rate"] == 0.9

    @patch("imgstream.ui.upload_handlers.log_batch_collision_detection")
    def test_monitor_batch_collision_processing(self, mock_log_batch):
        """Test monitoring batch collision processing."""
        filenames = ["test1.jpg", "test2.jpg", "test3.jpg"]
        collision_results = {
            "test1.jpg": {"existing_photo": {"id": "photo_123"}},
            "test2.jpg": {"existing_photo": {"id": "photo_456"}},
        }
        
        monitor_batch_collision_processing(
            user_id="test_user",
            filenames=filenames,
            collision_results=collision_results,
            processing_time_ms=1500.0
        )
        
        mock_log_batch.assert_called_once_with(
            user_id="test_user",
            filenames=filenames,
            collisions_found=2,
            processing_time_ms=1500.0,
            total_files=3,
            collision_rate=2/3
        )


class TestSessionStateManagement:
    """Test session state management functions."""

    @patch("streamlit.session_state", new_callable=dict)
    def test_clear_upload_session_state(self, mock_session_state):
        """Test clearing upload-related session state."""
        from imgstream.ui.upload_handlers import clear_upload_session_state
        
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
    @patch("imgstream.ui.upload_handlers.log_user_decision")
    @patch("imgstream.ui.upload_handlers.log_collision_resolved")
    def test_complete_decision_workflow(self, mock_log_resolved, mock_log_decision, mock_session_state):
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
        
        # Verify monitoring was called for both decisions
        assert mock_log_decision.call_count == 2
        assert mock_log_resolved.call_count == 2
        
        # Verify first decision call
        first_decision_call = mock_log_decision.call_args_list[0][1]
        assert first_decision_call["user_id"] == "test_user"
        assert first_decision_call["filename"] == "test1.jpg"
        assert first_decision_call["decision"] == "overwrite"
        assert first_decision_call["existing_photo_id"] == "photo_123"
        assert first_decision_call["fallback_mode"] is False
        
        # Verify second decision call
        second_decision_call = mock_log_decision.call_args_list[1][1]
        assert second_decision_call["user_id"] == "test_user"
        assert second_decision_call["filename"] == "test2.jpg"
        assert second_decision_call["decision"] == "skip"
        assert second_decision_call["existing_photo_id"] == "photo_456"
        assert second_decision_call["fallback_mode"] is True

    @patch("imgstream.ui.upload_handlers.log_batch_collision_detection")
    def test_batch_monitoring_integration(self, mock_log_batch):
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
        
        # Verify batch monitoring was called with correct metrics
        mock_log_batch.assert_called_once()
        call_args = mock_log_batch.call_args[1]
        
        assert call_args["user_id"] == "batch_user"
        assert call_args["filenames"] == filenames
        assert call_args["collisions_found"] == 2
        assert call_args["processing_time_ms"] == 2500.0
        assert call_args["total_files"] == 4
        assert call_args["collision_rate"] == 0.5  # 2 collisions out of 4 files

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
