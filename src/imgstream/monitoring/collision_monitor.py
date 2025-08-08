"""Comprehensive monitoring and logging for collision detection operations."""

import structlog
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import json

from ..logging_config import log_user_action

logger = structlog.get_logger(__name__)


@dataclass
class CollisionEvent:
    """Represents a collision detection event."""
    user_id: str
    filename: str
    event_type: str  # 'detected', 'resolved', 'skipped', 'overwritten'
    timestamp: datetime = field(default_factory=datetime.now)
    existing_photo_id: Optional[str] = None
    user_decision: Optional[str] = None
    processing_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging."""
        return {
            "user_id": self.user_id,
            "filename": self.filename,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "existing_photo_id": self.existing_photo_id,
            "user_decision": self.user_decision,
            "processing_time_ms": self.processing_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class OverwriteEvent:
    """Represents an overwrite operation event."""
    user_id: str
    filename: str
    original_photo_id: str
    operation_type: str  # 'success', 'failure', 'fallback'
    timestamp: datetime = field(default_factory=datetime.now)
    processing_time_ms: Optional[float] = None
    fallback_filename: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging."""
        return {
            "user_id": self.user_id,
            "filename": self.filename,
            "original_photo_id": self.original_photo_id,
            "operation_type": self.operation_type,
            "timestamp": self.timestamp.isoformat(),
            "processing_time_ms": self.processing_time_ms,
            "fallback_filename": self.fallback_filename,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class UserDecisionEvent:
    """Represents a user decision event."""
    user_id: str
    filename: str
    decision: str  # 'overwrite', 'skip', 'pending'
    timestamp: datetime = field(default_factory=datetime.now)
    decision_time_ms: Optional[float] = None
    collision_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging."""
        return {
            "user_id": self.user_id,
            "filename": self.filename,
            "decision": self.decision,
            "timestamp": self.timestamp.isoformat(),
            "decision_time_ms": self.decision_time_ms,
            "collision_context": self.collision_context,
        }


class CollisionMonitor:
    """Comprehensive monitoring system for collision detection."""

    def __init__(self):
        self.collision_events: List[CollisionEvent] = []
        self.overwrite_events: List[OverwriteEvent] = []
        self.user_decision_events: List[UserDecisionEvent] = []
        self._session_start = datetime.now()

    def log_collision_detected(self, user_id: str, filename: str, existing_photo_id: str, 
                             processing_time_ms: float = None, **metadata) -> None:
        """Log a collision detection event."""
        event = CollisionEvent(
            user_id=user_id,
            filename=filename,
            event_type="detected",
            existing_photo_id=existing_photo_id,
            processing_time_ms=processing_time_ms,
            metadata=metadata
        )
        
        self.collision_events.append(event)
        
        logger.info(
            "collision_detected",
            **event.to_dict()
        )
        
        log_user_action(
            user_id,
            "collision_detected",
            filename=filename,
            existing_photo_id=existing_photo_id,
            processing_time_ms=processing_time_ms
        )

    def log_collision_resolved(self, user_id: str, filename: str, user_decision: str,
                             decision_time_ms: float = None, **metadata) -> None:
        """Log a collision resolution event."""
        event = CollisionEvent(
            user_id=user_id,
            filename=filename,
            event_type="resolved",
            user_decision=user_decision,
            processing_time_ms=decision_time_ms,
            metadata=metadata
        )
        
        self.collision_events.append(event)
        
        logger.info(
            "collision_resolved",
            **event.to_dict()
        )
        
        log_user_action(
            user_id,
            "collision_resolved",
            filename=filename,
            decision=user_decision,
            decision_time_ms=decision_time_ms
        )

    def log_overwrite_operation(self, user_id: str, filename: str, original_photo_id: str,
                              operation_type: str, processing_time_ms: float = None,
                              fallback_filename: str = None, error_message: str = None,
                              **metadata) -> None:
        """Log an overwrite operation event."""
        event = OverwriteEvent(
            user_id=user_id,
            filename=filename,
            original_photo_id=original_photo_id,
            operation_type=operation_type,
            processing_time_ms=processing_time_ms,
            fallback_filename=fallback_filename,
            error_message=error_message,
            metadata=metadata
        )
        
        self.overwrite_events.append(event)
        
        logger.info(
            "overwrite_operation",
            **event.to_dict()
        )
        
        log_user_action(
            user_id,
            "overwrite_operation",
            filename=filename,
            original_photo_id=original_photo_id,
            operation_type=operation_type,
            processing_time_ms=processing_time_ms,
            fallback_filename=fallback_filename
        )

    def log_user_decision(self, user_id: str, filename: str, decision: str,
                         decision_time_ms: float = None, **collision_context) -> None:
        """Log a user decision event."""
        event = UserDecisionEvent(
            user_id=user_id,
            filename=filename,
            decision=decision,
            decision_time_ms=decision_time_ms,
            collision_context=collision_context
        )
        
        self.user_decision_events.append(event)
        
        logger.info(
            "user_decision",
            **event.to_dict()
        )
        
        log_user_action(
            user_id,
            "user_decision",
            filename=filename,
            decision=decision,
            decision_time_ms=decision_time_ms
        )

    def log_batch_collision_detection(self, user_id: str, filenames: List[str], 
                                    collisions_found: int, processing_time_ms: float,
                                    cache_hit_rate: float = None, **metadata) -> None:
        """Log batch collision detection metrics."""
        batch_metadata = {
            "total_files": len(filenames),
            "collisions_found": collisions_found,
            "collision_rate": collisions_found / len(filenames) if filenames else 0,
            "processing_time_ms": processing_time_ms,
            "files_per_second": len(filenames) / (processing_time_ms / 1000) if processing_time_ms > 0 else 0,
            "cache_hit_rate": cache_hit_rate,
            **metadata
        }
        
        logger.info(
            "batch_collision_detection",
            user_id=user_id,
            **batch_metadata
        )
        
        log_user_action(
            user_id,
            "batch_collision_detection",
            **batch_metadata
        )

    def get_collision_statistics(self, user_id: str = None, 
                               time_window: timedelta = None) -> Dict[str, Any]:
        """Get collision detection statistics."""
        if time_window is None:
            time_window = timedelta(hours=24)
        
        cutoff_time = datetime.now() - time_window
        
        # Filter events by user and time window
        filtered_collisions = [
            event for event in self.collision_events
            if (user_id is None or event.user_id == user_id) and event.timestamp >= cutoff_time
        ]
        
        filtered_overwrites = [
            event for event in self.overwrite_events
            if (user_id is None or event.user_id == user_id) and event.timestamp >= cutoff_time
        ]
        
        filtered_decisions = [
            event for event in self.user_decision_events
            if (user_id is None or event.user_id == user_id) and event.timestamp >= cutoff_time
        ]
        
        # Calculate statistics
        total_collisions = len([e for e in filtered_collisions if e.event_type == "detected"])
        resolved_collisions = len([e for e in filtered_collisions if e.event_type == "resolved"])
        
        decision_counts = Counter(event.decision for event in filtered_decisions)
        overwrite_counts = Counter(event.operation_type for event in filtered_overwrites)
        
        # Calculate average processing times
        collision_times = [e.processing_time_ms for e in filtered_collisions if e.processing_time_ms]
        overwrite_times = [e.processing_time_ms for e in filtered_overwrites if e.processing_time_ms]
        decision_times = [e.decision_time_ms for e in filtered_decisions if e.decision_time_ms]
        
        return {
            "time_window_hours": time_window.total_seconds() / 3600,
            "user_id": user_id,
            "collision_metrics": {
                "total_detected": total_collisions,
                "total_resolved": resolved_collisions,
                "resolution_rate": resolved_collisions / total_collisions if total_collisions > 0 else 0,
                "avg_detection_time_ms": sum(collision_times) / len(collision_times) if collision_times else 0,
            },
            "user_decision_metrics": {
                "total_decisions": len(filtered_decisions),
                "decision_breakdown": dict(decision_counts),
                "overwrite_rate": decision_counts.get("overwrite", 0) / len(filtered_decisions) if filtered_decisions else 0,
                "skip_rate": decision_counts.get("skip", 0) / len(filtered_decisions) if filtered_decisions else 0,
                "avg_decision_time_ms": sum(decision_times) / len(decision_times) if decision_times else 0,
            },
            "overwrite_metrics": {
                "total_operations": len(filtered_overwrites),
                "operation_breakdown": dict(overwrite_counts),
                "success_rate": overwrite_counts.get("success", 0) / len(filtered_overwrites) if filtered_overwrites else 0,
                "fallback_rate": overwrite_counts.get("fallback", 0) / len(filtered_overwrites) if filtered_overwrites else 0,
                "avg_processing_time_ms": sum(overwrite_times) / len(overwrite_times) if overwrite_times else 0,
            },
        }

    def get_user_behavior_patterns(self, user_id: str, time_window: timedelta = None) -> Dict[str, Any]:
        """Analyze user behavior patterns for collision handling."""
        if time_window is None:
            time_window = timedelta(days=7)
        
        cutoff_time = datetime.now() - time_window
        
        user_decisions = [
            event for event in self.user_decision_events
            if event.user_id == user_id and event.timestamp >= cutoff_time
        ]
        
        if not user_decisions:
            return {"user_id": user_id, "pattern": "no_data", "recommendations": []}
        
        # Analyze decision patterns
        decisions = [event.decision for event in user_decisions]
        decision_counts = Counter(decisions)
        total_decisions = len(decisions)
        
        # Calculate decision percentages
        overwrite_rate = decision_counts.get("overwrite", 0) / total_decisions
        skip_rate = decision_counts.get("skip", 0) / total_decisions
        
        # Determine user pattern
        if overwrite_rate > 0.8:
            pattern = "aggressive_overwriter"
            recommendations = [
                "Consider enabling automatic overwrite for this user",
                "Provide bulk overwrite options",
                "Show simplified collision dialogs"
            ]
        elif skip_rate > 0.8:
            pattern = "conservative_skipper"
            recommendations = [
                "Suggest filename modification options",
                "Provide duplicate detection before upload",
                "Show file comparison tools"
            ]
        elif abs(overwrite_rate - skip_rate) < 0.2:
            pattern = "balanced_decision_maker"
            recommendations = [
                "Current collision handling is appropriate",
                "Consider showing file preview comparisons",
                "Maintain current decision options"
            ]
        else:
            pattern = "inconsistent"
            recommendations = [
                "Provide clearer collision information",
                "Show file differences more prominently",
                "Consider decision history hints"
            ]
        
        # Calculate average decision time
        decision_times = [e.decision_time_ms for e in user_decisions if e.decision_time_ms]
        avg_decision_time = sum(decision_times) / len(decision_times) if decision_times else 0
        
        return {
            "user_id": user_id,
            "time_window_days": time_window.days,
            "pattern": pattern,
            "statistics": {
                "total_decisions": total_decisions,
                "overwrite_rate": overwrite_rate,
                "skip_rate": skip_rate,
                "avg_decision_time_ms": avg_decision_time,
                "decision_breakdown": dict(decision_counts),
            },
            "recommendations": recommendations,
        }

    def export_events(self, format: str = "json", user_id: str = None, 
                     time_window: timedelta = None) -> str:
        """Export events in specified format."""
        if time_window is None:
            time_window = timedelta(hours=24)
        
        cutoff_time = datetime.now() - time_window
        
        # Filter and collect all events
        all_events = []
        
        for event in self.collision_events:
            if (user_id is None or event.user_id == user_id) and event.timestamp >= cutoff_time:
                event_dict = event.to_dict()
                event_dict["event_category"] = "collision"
                all_events.append(event_dict)
        
        for event in self.overwrite_events:
            if (user_id is None or event.user_id == user_id) and event.timestamp >= cutoff_time:
                event_dict = event.to_dict()
                event_dict["event_category"] = "overwrite"
                all_events.append(event_dict)
        
        for event in self.user_decision_events:
            if (user_id is None or event.user_id == user_id) and event.timestamp >= cutoff_time:
                event_dict = event.to_dict()
                event_dict["event_category"] = "user_decision"
                all_events.append(event_dict)
        
        # Sort by timestamp
        all_events.sort(key=lambda x: x["timestamp"])
        
        if format.lower() == "json":
            return json.dumps(all_events, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def clear_old_events(self, retention_period: timedelta = None) -> int:
        """Clear old events beyond retention period."""
        if retention_period is None:
            retention_period = timedelta(days=30)
        
        cutoff_time = datetime.now() - retention_period
        
        # Count events to be removed
        old_collision_events = len([e for e in self.collision_events if e.timestamp < cutoff_time])
        old_overwrite_events = len([e for e in self.overwrite_events if e.timestamp < cutoff_time])
        old_decision_events = len([e for e in self.user_decision_events if e.timestamp < cutoff_time])
        
        total_removed = old_collision_events + old_overwrite_events + old_decision_events
        
        # Remove old events
        self.collision_events = [e for e in self.collision_events if e.timestamp >= cutoff_time]
        self.overwrite_events = [e for e in self.overwrite_events if e.timestamp >= cutoff_time]
        self.user_decision_events = [e for e in self.user_decision_events if e.timestamp >= cutoff_time]
        
        logger.info(
            "old_events_cleared",
            retention_period_days=retention_period.days,
            collision_events_removed=old_collision_events,
            overwrite_events_removed=old_overwrite_events,
            decision_events_removed=old_decision_events,
            total_removed=total_removed
        )
        
        return total_removed


# Global monitor instance
_collision_monitor = CollisionMonitor()


def get_collision_monitor() -> CollisionMonitor:
    """Get the global collision monitor instance."""
    return _collision_monitor


# Convenience functions for common logging operations
def log_collision_detected(user_id: str, filename: str, existing_photo_id: str, 
                         processing_time_ms: float = None, **metadata) -> None:
    """Log a collision detection event."""
    _collision_monitor.log_collision_detected(user_id, filename, existing_photo_id, 
                                            processing_time_ms, **metadata)


def log_collision_resolved(user_id: str, filename: str, user_decision: str,
                         decision_time_ms: float = None, **metadata) -> None:
    """Log a collision resolution event."""
    _collision_monitor.log_collision_resolved(user_id, filename, user_decision, 
                                            decision_time_ms, **metadata)


def log_overwrite_operation(user_id: str, filename: str, original_photo_id: str,
                          operation_type: str, processing_time_ms: float = None,
                          fallback_filename: str = None, error_message: str = None,
                          **metadata) -> None:
    """Log an overwrite operation event."""
    _collision_monitor.log_overwrite_operation(user_id, filename, original_photo_id,
                                             operation_type, processing_time_ms,
                                             fallback_filename, error_message, **metadata)


def log_user_decision(user_id: str, filename: str, decision: str,
                     decision_time_ms: float = None, **collision_context) -> None:
    """Log a user decision event."""
    _collision_monitor.log_user_decision(user_id, filename, decision, 
                                       decision_time_ms, **collision_context)


def log_batch_collision_detection(user_id: str, filenames: List[str], 
                                collisions_found: int, processing_time_ms: float,
                                cache_hit_rate: float = None, **metadata) -> None:
    """Log batch collision detection metrics."""
    _collision_monitor.log_batch_collision_detection(user_id, filenames, collisions_found,
                                                   processing_time_ms, cache_hit_rate, **metadata)
