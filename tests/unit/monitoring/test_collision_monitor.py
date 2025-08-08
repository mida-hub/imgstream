"""Tests for collision monitoring functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from imgstream.monitoring.collision_monitor import (
    CollisionMonitor,
    CollisionEvent,
    OverwriteEvent,
    UserDecisionEvent,
    get_collision_monitor,
    log_collision_detected,
    log_collision_resolved,
    log_overwrite_operation,
    log_user_decision,
    log_batch_collision_detection,
)


class TestCollisionEvent:
    """Test CollisionEvent data class."""

    def test_collision_event_creation(self):
        """Test creating a collision event."""
        event = CollisionEvent(
            user_id="test_user",
            filename="test.jpg",
            event_type="detected",
            existing_photo_id="photo_123",
            processing_time_ms=150.5,
        )

        assert event.user_id == "test_user"
        assert event.filename == "test.jpg"
        assert event.event_type == "detected"
        assert event.existing_photo_id == "photo_123"
        assert event.processing_time_ms == 150.5
        assert isinstance(event.timestamp, datetime)

    def test_collision_event_to_dict(self):
        """Test converting collision event to dictionary."""
        event = CollisionEvent(
            user_id="test_user",
            filename="test.jpg",
            event_type="resolved",
            user_decision="overwrite",
            metadata={"file_size": 1024},
        )

        event_dict = event.to_dict()

        assert event_dict["user_id"] == "test_user"
        assert event_dict["filename"] == "test.jpg"
        assert event_dict["event_type"] == "resolved"
        assert event_dict["user_decision"] == "overwrite"
        assert event_dict["metadata"] == {"file_size": 1024}
        assert "timestamp" in event_dict


class TestOverwriteEvent:
    """Test OverwriteEvent data class."""

    def test_overwrite_event_creation(self):
        """Test creating an overwrite event."""
        event = OverwriteEvent(
            user_id="test_user",
            filename="test.jpg",
            original_photo_id="photo_123",
            operation_type="success",
            processing_time_ms=250.0,
        )

        assert event.user_id == "test_user"
        assert event.filename == "test.jpg"
        assert event.original_photo_id == "photo_123"
        assert event.operation_type == "success"
        assert event.processing_time_ms == 250.0

    def test_overwrite_event_to_dict(self):
        """Test converting overwrite event to dictionary."""
        event = OverwriteEvent(
            user_id="test_user",
            filename="test.jpg",
            original_photo_id="photo_123",
            operation_type="fallback",
            fallback_filename="test_1.jpg",
            error_message="Primary operation failed",
        )

        event_dict = event.to_dict()

        assert event_dict["user_id"] == "test_user"
        assert event_dict["filename"] == "test.jpg"
        assert event_dict["original_photo_id"] == "photo_123"
        assert event_dict["operation_type"] == "fallback"
        assert event_dict["fallback_filename"] == "test_1.jpg"
        assert event_dict["error_message"] == "Primary operation failed"


class TestUserDecisionEvent:
    """Test UserDecisionEvent data class."""

    def test_user_decision_event_creation(self):
        """Test creating a user decision event."""
        event = UserDecisionEvent(
            user_id="test_user",
            filename="test.jpg",
            decision="overwrite",
            decision_time_ms=5000.0,
            collision_context={"existing_photo_id": "photo_123"},
        )

        assert event.user_id == "test_user"
        assert event.filename == "test.jpg"
        assert event.decision == "overwrite"
        assert event.decision_time_ms == 5000.0
        assert event.collision_context == {"existing_photo_id": "photo_123"}

    def test_user_decision_event_to_dict(self):
        """Test converting user decision event to dictionary."""
        event = UserDecisionEvent(
            user_id="test_user",
            filename="test.jpg",
            decision="skip",
            collision_context={"file_size": 2048},
        )

        event_dict = event.to_dict()

        assert event_dict["user_id"] == "test_user"
        assert event_dict["filename"] == "test.jpg"
        assert event_dict["decision"] == "skip"
        assert event_dict["collision_context"] == {"file_size": 2048}


class TestCollisionMonitor:
    """Test CollisionMonitor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = CollisionMonitor()

    @patch("imgstream.monitoring.collision_monitor.logger")
    @patch("imgstream.monitoring.collision_monitor.log_user_action")
    def test_log_collision_detected(self, mock_log_user_action, mock_logger):
        """Test logging collision detection."""
        self.monitor.log_collision_detected(
            user_id="test_user",
            filename="test.jpg",
            existing_photo_id="photo_123",
            processing_time_ms=100.0,
            file_size=1024,
        )

        # Check event was stored
        assert len(self.monitor.collision_events) == 1
        event = self.monitor.collision_events[0]
        assert event.user_id == "test_user"
        assert event.filename == "test.jpg"
        assert event.event_type == "detected"
        assert event.existing_photo_id == "photo_123"
        assert event.processing_time_ms == 100.0

        # Check logging was called
        mock_logger.info.assert_called_once()
        mock_log_user_action.assert_called_once()

    @patch("imgstream.monitoring.collision_monitor.logger")
    @patch("imgstream.monitoring.collision_monitor.log_user_action")
    def test_log_collision_resolved(self, mock_log_user_action, mock_logger):
        """Test logging collision resolution."""
        self.monitor.log_collision_resolved(
            user_id="test_user",
            filename="test.jpg",
            user_decision="overwrite",
            decision_time_ms=3000.0,
        )

        # Check event was stored
        assert len(self.monitor.collision_events) == 1
        event = self.monitor.collision_events[0]
        assert event.user_id == "test_user"
        assert event.filename == "test.jpg"
        assert event.event_type == "resolved"
        assert event.user_decision == "overwrite"
        assert event.processing_time_ms == 3000.0

        # Check logging was called
        mock_logger.info.assert_called_once()
        mock_log_user_action.assert_called_once()

    @patch("imgstream.monitoring.collision_monitor.logger")
    @patch("imgstream.monitoring.collision_monitor.log_user_action")
    def test_log_overwrite_operation(self, mock_log_user_action, mock_logger):
        """Test logging overwrite operation."""
        self.monitor.log_overwrite_operation(
            user_id="test_user",
            filename="test.jpg",
            original_photo_id="photo_123",
            operation_type="success",
            processing_time_ms=500.0,
        )

        # Check event was stored
        assert len(self.monitor.overwrite_events) == 1
        event = self.monitor.overwrite_events[0]
        assert event.user_id == "test_user"
        assert event.filename == "test.jpg"
        assert event.original_photo_id == "photo_123"
        assert event.operation_type == "success"
        assert event.processing_time_ms == 500.0

        # Check logging was called
        mock_logger.info.assert_called_once()
        mock_log_user_action.assert_called_once()

    @patch("imgstream.monitoring.collision_monitor.logger")
    @patch("imgstream.monitoring.collision_monitor.log_user_action")
    def test_log_user_decision(self, mock_log_user_action, mock_logger):
        """Test logging user decision."""
        self.monitor.log_user_decision(
            user_id="test_user",
            filename="test.jpg",
            decision="skip",
            decision_time_ms=2000.0,
            existing_photo_id="photo_123",
        )

        # Check event was stored
        assert len(self.monitor.user_decision_events) == 1
        event = self.monitor.user_decision_events[0]
        assert event.user_id == "test_user"
        assert event.filename == "test.jpg"
        assert event.decision == "skip"
        assert event.decision_time_ms == 2000.0
        assert event.collision_context["existing_photo_id"] == "photo_123"

        # Check logging was called
        mock_logger.info.assert_called_once()
        mock_log_user_action.assert_called_once()

    @patch("imgstream.monitoring.collision_monitor.logger")
    @patch("imgstream.monitoring.collision_monitor.log_user_action")
    def test_log_batch_collision_detection(self, mock_log_user_action, mock_logger):
        """Test logging batch collision detection."""
        filenames = ["test1.jpg", "test2.jpg", "test3.jpg"]
        self.monitor.log_batch_collision_detection(
            user_id="test_user",
            filenames=filenames,
            collisions_found=2,
            processing_time_ms=1500.0,
            cache_hit_rate=0.5,
        )

        # Check logging was called with correct metrics
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[1]
        assert call_args["user_id"] == "test_user"
        assert call_args["total_files"] == 3
        assert call_args["collisions_found"] == 2
        assert call_args["collision_rate"] == 2/3
        assert call_args["processing_time_ms"] == 1500.0
        assert call_args["files_per_second"] == 3 / 1.5
        assert call_args["cache_hit_rate"] == 0.5

        mock_log_user_action.assert_called_once()

    def test_get_collision_statistics(self):
        """Test getting collision statistics."""
        # Add some test events
        self.monitor.log_collision_detected("user1", "test1.jpg", "photo1", 100.0)
        self.monitor.log_collision_resolved("user1", "test1.jpg", "overwrite", 2000.0)
        self.monitor.log_overwrite_operation("user1", "test1.jpg", "photo1", "success", 300.0)
        self.monitor.log_user_decision("user1", "test1.jpg", "overwrite", 2000.0)

        # Add events for different user
        self.monitor.log_collision_detected("user2", "test2.jpg", "photo2", 150.0)
        self.monitor.log_user_decision("user2", "test2.jpg", "skip", 1000.0)

        # Get statistics for user1
        stats = self.monitor.get_collision_statistics("user1")

        assert stats["user_id"] == "user1"
        assert stats["collision_metrics"]["total_detected"] == 1
        assert stats["collision_metrics"]["total_resolved"] == 1
        assert stats["collision_metrics"]["resolution_rate"] == 1.0
        assert stats["user_decision_metrics"]["total_decisions"] == 1
        assert stats["user_decision_metrics"]["overwrite_rate"] == 1.0
        assert stats["overwrite_metrics"]["total_operations"] == 1
        assert stats["overwrite_metrics"]["success_rate"] == 1.0

        # Get statistics for all users
        all_stats = self.monitor.get_collision_statistics()
        assert all_stats["collision_metrics"]["total_detected"] == 2
        assert all_stats["user_decision_metrics"]["total_decisions"] == 2

    def test_get_user_behavior_patterns(self):
        """Test analyzing user behavior patterns."""
        # Add decisions for aggressive overwriter
        for i in range(10):
            self.monitor.log_user_decision("aggressive_user", f"test{i}.jpg", "overwrite", 1000.0)

        # Add decisions for conservative skipper
        for i in range(10):
            self.monitor.log_user_decision("conservative_user", f"test{i}.jpg", "skip", 2000.0)

        # Add mixed decisions for balanced user
        for i in range(5):
            self.monitor.log_user_decision("balanced_user", f"test{i}.jpg", "overwrite", 1500.0)
        for i in range(5, 10):
            self.monitor.log_user_decision("balanced_user", f"test{i}.jpg", "skip", 1500.0)

        # Test aggressive overwriter
        aggressive_pattern = self.monitor.get_user_behavior_patterns("aggressive_user")
        assert aggressive_pattern["pattern"] == "aggressive_overwriter"
        assert aggressive_pattern["statistics"]["overwrite_rate"] == 1.0
        assert "automatic overwrite" in " ".join(aggressive_pattern["recommendations"]).lower()

        # Test conservative skipper
        conservative_pattern = self.monitor.get_user_behavior_patterns("conservative_user")
        assert conservative_pattern["pattern"] == "conservative_skipper"
        assert conservative_pattern["statistics"]["skip_rate"] == 1.0
        assert "filename modification" in " ".join(conservative_pattern["recommendations"]).lower()

        # Test balanced user
        balanced_pattern = self.monitor.get_user_behavior_patterns("balanced_user")
        assert balanced_pattern["pattern"] == "balanced_decision_maker"
        assert abs(balanced_pattern["statistics"]["overwrite_rate"] - 0.5) < 0.1
        assert abs(balanced_pattern["statistics"]["skip_rate"] - 0.5) < 0.1

    def test_export_events(self):
        """Test exporting events."""
        # Add some test events
        self.monitor.log_collision_detected("test_user", "test.jpg", "photo1", 100.0)
        self.monitor.log_user_decision("test_user", "test.jpg", "overwrite", 2000.0)
        self.monitor.log_overwrite_operation("test_user", "test.jpg", "photo1", "success", 300.0)

        # Export events
        exported = self.monitor.export_events(format="json", user_id="test_user")

        # Parse JSON and verify
        import json
        events = json.loads(exported)
        
        assert len(events) == 3
        assert all("event_category" in event for event in events)
        assert any(event["event_category"] == "collision" for event in events)
        assert any(event["event_category"] == "user_decision" for event in events)
        assert any(event["event_category"] == "overwrite" for event in events)

    def test_clear_old_events(self):
        """Test clearing old events."""
        # Add some events
        self.monitor.log_collision_detected("test_user", "test1.jpg", "photo1", 100.0)
        self.monitor.log_user_decision("test_user", "test1.jpg", "overwrite", 2000.0)
        self.monitor.log_overwrite_operation("test_user", "test1.jpg", "photo1", "success", 300.0)

        # Manually set old timestamps
        old_time = datetime.now() - timedelta(days=35)
        self.monitor.collision_events[0].timestamp = old_time
        self.monitor.user_decision_events[0].timestamp = old_time

        # Clear old events
        removed_count = self.monitor.clear_old_events(timedelta(days=30))

        assert removed_count == 2
        assert len(self.monitor.collision_events) == 0
        assert len(self.monitor.user_decision_events) == 0
        assert len(self.monitor.overwrite_events) == 1  # This one should remain


class TestGlobalFunctions:
    """Test global convenience functions."""

    @patch("imgstream.monitoring.collision_monitor._collision_monitor")
    def test_get_collision_monitor(self, mock_monitor):
        """Test getting global collision monitor."""
        result = get_collision_monitor()
        assert result == mock_monitor

    @patch("imgstream.monitoring.collision_monitor._collision_monitor")
    def test_log_collision_detected_global(self, mock_monitor):
        """Test global log_collision_detected function."""
        log_collision_detected("test_user", "test.jpg", "photo1", 100.0, file_size=1024)
        
        mock_monitor.log_collision_detected.assert_called_once_with(
            "test_user", "test.jpg", "photo1", 100.0, file_size=1024
        )

    @patch("imgstream.monitoring.collision_monitor._collision_monitor")
    def test_log_collision_resolved_global(self, mock_monitor):
        """Test global log_collision_resolved function."""
        log_collision_resolved("test_user", "test.jpg", "overwrite", 2000.0, context="test")
        
        mock_monitor.log_collision_resolved.assert_called_once_with(
            "test_user", "test.jpg", "overwrite", 2000.0, context="test"
        )

    @patch("imgstream.monitoring.collision_monitor._collision_monitor")
    def test_log_overwrite_operation_global(self, mock_monitor):
        """Test global log_overwrite_operation function."""
        log_overwrite_operation("test_user", "test.jpg", "photo1", "success", 300.0)
        
        mock_monitor.log_overwrite_operation.assert_called_once_with(
            "test_user", "test.jpg", "photo1", "success", 300.0, None, None
        )

    @patch("imgstream.monitoring.collision_monitor._collision_monitor")
    def test_log_user_decision_global(self, mock_monitor):
        """Test global log_user_decision function."""
        log_user_decision("test_user", "test.jpg", "skip", 1500.0, context="test")
        
        mock_monitor.log_user_decision.assert_called_once_with(
            "test_user", "test.jpg", "skip", 1500.0, context="test"
        )

    @patch("imgstream.monitoring.collision_monitor._collision_monitor")
    def test_log_batch_collision_detection_global(self, mock_monitor):
        """Test global log_batch_collision_detection function."""
        filenames = ["test1.jpg", "test2.jpg"]
        log_batch_collision_detection("test_user", filenames, 1, 1000.0, 0.5, extra="data")
        
        mock_monitor.log_batch_collision_detection.assert_called_once_with(
            "test_user", filenames, 1, 1000.0, 0.5, extra="data"
        )


class TestIntegration:
    """Integration tests for collision monitoring."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = CollisionMonitor()

    def test_complete_collision_workflow(self):
        """Test complete collision detection and resolution workflow."""
        user_id = "test_user"
        filename = "test.jpg"
        photo_id = "photo_123"

        # 1. Collision detected
        self.monitor.log_collision_detected(user_id, filename, photo_id, 150.0)

        # 2. User makes decision
        self.monitor.log_user_decision(user_id, filename, "overwrite", 3000.0, 
                                     existing_photo_id=photo_id)

        # 3. Collision resolved
        self.monitor.log_collision_resolved(user_id, filename, "overwrite", 3000.0)

        # 4. Overwrite operation performed
        self.monitor.log_overwrite_operation(user_id, filename, photo_id, "success", 500.0)

        # Verify all events were recorded
        assert len(self.monitor.collision_events) == 2  # detected + resolved
        assert len(self.monitor.user_decision_events) == 1
        assert len(self.monitor.overwrite_events) == 1

        # Verify statistics
        stats = self.monitor.get_collision_statistics(user_id)
        assert stats["collision_metrics"]["total_detected"] == 1
        assert stats["collision_metrics"]["total_resolved"] == 1
        assert stats["user_decision_metrics"]["overwrite_rate"] == 1.0
        assert stats["overwrite_metrics"]["success_rate"] == 1.0

    def test_batch_processing_workflow(self):
        """Test batch collision processing workflow."""
        user_id = "test_user"
        filenames = ["test1.jpg", "test2.jpg", "test3.jpg"]

        # Log batch collision detection
        self.monitor.log_batch_collision_detection(user_id, filenames, 2, 1200.0)

        # Log individual collisions
        self.monitor.log_collision_detected(user_id, "test1.jpg", "photo1", 100.0)
        self.monitor.log_collision_detected(user_id, "test2.jpg", "photo2", 120.0)

        # Log user decisions
        self.monitor.log_user_decision(user_id, "test1.jpg", "overwrite", 2000.0)
        self.monitor.log_user_decision(user_id, "test2.jpg", "skip", 1000.0)

        # Log resolutions
        self.monitor.log_collision_resolved(user_id, "test1.jpg", "overwrite", 2000.0)
        self.monitor.log_collision_resolved(user_id, "test2.jpg", "skip", 1000.0)

        # Log overwrite for the one that was overwritten
        self.monitor.log_overwrite_operation(user_id, "test1.jpg", "photo1", "success", 400.0)

        # Verify statistics
        stats = self.monitor.get_collision_statistics(user_id)
        assert stats["collision_metrics"]["total_detected"] == 2
        assert stats["collision_metrics"]["total_resolved"] == 2
        assert stats["user_decision_metrics"]["total_decisions"] == 2
        assert stats["user_decision_metrics"]["overwrite_rate"] == 0.5
        assert stats["user_decision_metrics"]["skip_rate"] == 0.5
        assert stats["overwrite_metrics"]["total_operations"] == 1
