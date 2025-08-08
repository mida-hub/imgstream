"""Comprehensive logging and monitoring for collision detection operations."""

import structlog
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading
import time

from ..logging_config import log_user_action, log_error

logger = structlog.get_logger(__name__)


@dataclass
class CollisionEvent:
    """Represents a collision detection event."""
    timestamp: datetime
    user_id: str
    event_type: str  # 'collision_detected', 'collision_resolved', 'batch_processed', etc.
    filename: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OverwriteMetrics:
    """Metrics for overwrite operations."""
    timestamp: datetime
    user_id: str
    filename: str
    operation_type: str  # 'overwrite', 'skip', 'new_upload'
    success: bool
    duration_ms: float
    file_size: int
    error_message: Optional[str] = None


@dataclass
class UserDecisionPattern:
    """Tracks user decision patterns for collision resolution."""
    user_id: str
    total_collisions: int = 0
    overwrite_decisions: int = 0
    skip_decisions: int = 0
    pending_decisions: int = 0
    avg_decision_time_seconds: float = 0.0
    last_activity: Optional[datetime] = None


class CollisionMetricsCollector:
    """Collects and manages collision detection metrics."""
    
    def __init__(self, max_events: int = 10000, retention_hours: int = 24):
        self.max_events = max_events
        self.retention_hours = retention_hours
        self._lock = threading.Lock()
        
        # Event storage
        self.collision_events: deque = deque(maxlen=max_events)
        self.overwrite_metrics: deque = deque(maxlen=max_events)
        
        # User decision patterns
        self.user_patterns: Dict[str, UserDecisionPattern] = {}
        
        # Performance metrics
        self.performance_metrics = {
            'total_collision_checks': 0,
            'total_batch_operations': 0,
            'total_cache_hits': 0,
            'total_cache_misses': 0,
            'avg_response_time_ms': 0.0,
            'error_count': 0,
        }
        
        # Hourly aggregates
        self.hourly_stats = defaultdict(lambda: {
            'collision_count': 0,
            'overwrite_count': 0,
            'skip_count': 0,
            'error_count': 0,
            'unique_users': set(),
            'avg_response_time': 0.0,
            'total_files_processed': 0,
        })
    
    def log_collision_event(
        self, 
        user_id: str, 
        event_type: str, 
        filename: str, 
        **details
    ) -> None:
        """Log a collision detection event."""
        event = CollisionEvent(
            timestamp=datetime.now(),
            user_id=user_id,
            event_type=event_type,
            filename=filename,
            details=details
        )
        
        with self._lock:
            self.collision_events.append(event)
            
            # Update hourly stats
            hour_key = event.timestamp.replace(minute=0, second=0, microsecond=0)
            self.hourly_stats[hour_key]['collision_count'] += 1
            self.hourly_stats[hour_key]['unique_users'].add(user_id)
            
            # Update performance metrics
            self.performance_metrics['total_collision_checks'] += 1
        
        # Log to structured logger
        logger.info(
            "collision_event_recorded",
            user_id=user_id,
            event_type=event_type,
            filename=filename,
            timestamp=event.timestamp.isoformat(),
            **details
        )
        
        # Log user action
        log_user_action(
            user_id,
            f"collision_{event_type}",
            filename=filename,
            **details
        )
    
    def log_overwrite_metrics(
        self,
        user_id: str,
        filename: str,
        operation_type: str,
        success: bool,
        duration_ms: float,
        file_size: int,
        error_message: Optional[str] = None
    ) -> None:
        """Log overwrite operation metrics."""
        metrics = OverwriteMetrics(
            timestamp=datetime.now(),
            user_id=user_id,
            filename=filename,
            operation_type=operation_type,
            success=success,
            duration_ms=duration_ms,
            file_size=file_size,
            error_message=error_message
        )
        
        with self._lock:
            self.overwrite_metrics.append(metrics)
            
            # Update hourly stats
            hour_key = metrics.timestamp.replace(minute=0, second=0, microsecond=0)
            if operation_type == 'overwrite':
                self.hourly_stats[hour_key]['overwrite_count'] += 1
            elif operation_type == 'skip':
                self.hourly_stats[hour_key]['skip_count'] += 1
            
            if not success:
                self.hourly_stats[hour_key]['error_count'] += 1
                self.performance_metrics['error_count'] += 1
            
            self.hourly_stats[hour_key]['unique_users'].add(user_id)
            self.hourly_stats[hour_key]['total_files_processed'] += 1
        
        # Log to structured logger
        logger.info(
            "overwrite_metrics_recorded",
            user_id=user_id,
            filename=filename,
            operation_type=operation_type,
            success=success,
            duration_ms=duration_ms,
            file_size=file_size,
            error_message=error_message,
            timestamp=metrics.timestamp.isoformat()
        )
        
        # Log user action
        log_user_action(
            user_id,
            f"overwrite_{operation_type}",
            filename=filename,
            success=success,
            duration_ms=duration_ms,
            file_size=file_size
        )
    
    def track_user_decision(
        self,
        user_id: str,
        decision: str,  # 'overwrite', 'skip', 'pending'
        decision_time_seconds: float = 0.0
    ) -> None:
        """Track user decision patterns."""
        with self._lock:
            if user_id not in self.user_patterns:
                self.user_patterns[user_id] = UserDecisionPattern(user_id=user_id)
            
            pattern = self.user_patterns[user_id]
            pattern.total_collisions += 1
            pattern.last_activity = datetime.now()
            
            if decision == 'overwrite':
                pattern.overwrite_decisions += 1
            elif decision == 'skip':
                pattern.skip_decisions += 1
            elif decision == 'pending':
                pattern.pending_decisions += 1
            
            # Update average decision time
            if decision_time_seconds > 0:
                total_decisions = pattern.overwrite_decisions + pattern.skip_decisions
                if total_decisions > 0:
                    current_avg = pattern.avg_decision_time_seconds
                    pattern.avg_decision_time_seconds = (
                        (current_avg * (total_decisions - 1) + decision_time_seconds) / total_decisions
                    )
        
        # Log decision pattern
        logger.info(
            "user_decision_tracked",
            user_id=user_id,
            decision=decision,
            decision_time_seconds=decision_time_seconds,
            total_collisions=pattern.total_collisions,
            overwrite_rate=pattern.overwrite_decisions / pattern.total_collisions if pattern.total_collisions > 0 else 0,
        )
    
    def log_performance_metrics(
        self,
        operation: str,
        duration_ms: float,
        file_count: int,
        cache_hit: bool = False,
        success: bool = True,
        **additional_metrics
    ) -> None:
        """Log performance metrics for collision detection operations."""
        with self._lock:
            # Update performance counters
            if operation == 'batch_collision_check':
                self.performance_metrics['total_batch_operations'] += 1
            
            if cache_hit:
                self.performance_metrics['total_cache_hits'] += 1
            else:
                self.performance_metrics['total_cache_misses'] += 1
            
            # Update average response time
            current_avg = self.performance_metrics['avg_response_time_ms']
            total_ops = self.performance_metrics['total_collision_checks']
            if total_ops > 0:
                self.performance_metrics['avg_response_time_ms'] = (
                    (current_avg * (total_ops - 1) + duration_ms) / total_ops
                )
            
            # Update hourly performance stats
            hour_key = datetime.now().replace(minute=0, second=0, microsecond=0)
            hourly_stat = self.hourly_stats[hour_key]
            
            if hourly_stat['avg_response_time'] == 0:
                hourly_stat['avg_response_time'] = duration_ms
            else:
                # Simple moving average
                hourly_stat['avg_response_time'] = (
                    hourly_stat['avg_response_time'] + duration_ms
                ) / 2
        
        # Log performance data
        logger.info(
            "performance_metrics_recorded",
            operation=operation,
            duration_ms=duration_ms,
            file_count=file_count,
            files_per_second=file_count / (duration_ms / 1000) if duration_ms > 0 else 0,
            cache_hit=cache_hit,
            success=success,
            **additional_metrics
        )
    
    def get_collision_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get collision detection statistics for the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            # Filter recent events
            recent_events = [
                event for event in self.collision_events 
                if event.timestamp >= cutoff_time
            ]
            
            recent_overwrites = [
                metric for metric in self.overwrite_metrics
                if metric.timestamp >= cutoff_time
            ]
            
            # Calculate statistics
            total_collisions = len(recent_events)
            total_overwrites = len([m for m in recent_overwrites if m.operation_type == 'overwrite'])
            total_skips = len([m for m in recent_overwrites if m.operation_type == 'skip'])
            successful_operations = len([m for m in recent_overwrites if m.success])
            
            # User statistics
            unique_users = len(set(event.user_id for event in recent_events))
            
            # Performance statistics
            if recent_overwrites:
                avg_duration = sum(m.duration_ms for m in recent_overwrites) / len(recent_overwrites)
                avg_file_size = sum(m.file_size for m in recent_overwrites) / len(recent_overwrites)
            else:
                avg_duration = 0
                avg_file_size = 0
            
            return {
                'time_period_hours': hours,
                'total_collisions': total_collisions,
                'total_overwrites': total_overwrites,
                'total_skips': total_skips,
                'success_rate': successful_operations / len(recent_overwrites) if recent_overwrites else 1.0,
                'unique_users': unique_users,
                'avg_operation_duration_ms': avg_duration,
                'avg_file_size_bytes': avg_file_size,
                'overwrite_rate': total_overwrites / total_collisions if total_collisions > 0 else 0,
                'skip_rate': total_skips / total_collisions if total_collisions > 0 else 0,
                'performance_metrics': self.performance_metrics.copy(),
            }
    
    def get_user_decision_patterns(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get user decision patterns."""
        with self._lock:
            if user_id:
                pattern = self.user_patterns.get(user_id)
                if pattern:
                    return {
                        'user_id': pattern.user_id,
                        'total_collisions': pattern.total_collisions,
                        'overwrite_decisions': pattern.overwrite_decisions,
                        'skip_decisions': pattern.skip_decisions,
                        'pending_decisions': pattern.pending_decisions,
                        'overwrite_rate': pattern.overwrite_decisions / pattern.total_collisions if pattern.total_collisions > 0 else 0,
                        'skip_rate': pattern.skip_decisions / pattern.total_collisions if pattern.total_collisions > 0 else 0,
                        'avg_decision_time_seconds': pattern.avg_decision_time_seconds,
                        'last_activity': pattern.last_activity.isoformat() if pattern.last_activity else None,
                    }
                return {}
            else:
                # Return aggregated patterns for all users
                all_patterns = []
                for pattern in self.user_patterns.values():
                    all_patterns.append({
                        'user_id': pattern.user_id,
                        'total_collisions': pattern.total_collisions,
                        'overwrite_rate': pattern.overwrite_decisions / pattern.total_collisions if pattern.total_collisions > 0 else 0,
                        'skip_rate': pattern.skip_decisions / pattern.total_collisions if pattern.total_collisions > 0 else 0,
                        'avg_decision_time_seconds': pattern.avg_decision_time_seconds,
                        'last_activity': pattern.last_activity.isoformat() if pattern.last_activity else None,
                    })
                
                return {
                    'total_users': len(all_patterns),
                    'user_patterns': all_patterns,
                    'aggregate_stats': self._calculate_aggregate_user_stats(),
                }
    
    def get_hourly_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get hourly trend data."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            # Filter recent hourly stats
            recent_stats = {
                hour: stats for hour, stats in self.hourly_stats.items()
                if hour >= cutoff_time
            }
            
            # Convert to time series format
            hourly_data = []
            for hour in sorted(recent_stats.keys()):
                stats = recent_stats[hour]
                hourly_data.append({
                    'hour': hour.isoformat(),
                    'collision_count': stats['collision_count'],
                    'overwrite_count': stats['overwrite_count'],
                    'skip_count': stats['skip_count'],
                    'error_count': stats['error_count'],
                    'unique_users': len(stats['unique_users']),
                    'avg_response_time_ms': stats['avg_response_time'],
                    'total_files_processed': stats['total_files_processed'],
                })
            
            return {
                'time_period_hours': hours,
                'hourly_data': hourly_data,
                'summary': {
                    'total_hours': len(hourly_data),
                    'peak_collision_hour': max(hourly_data, key=lambda x: x['collision_count']) if hourly_data else None,
                    'peak_user_hour': max(hourly_data, key=lambda x: x['unique_users']) if hourly_data else None,
                }
            }
    
    def _calculate_aggregate_user_stats(self) -> Dict[str, Any]:
        """Calculate aggregate statistics across all users."""
        if not self.user_patterns:
            return {}
        
        patterns = list(self.user_patterns.values())
        total_collisions = sum(p.total_collisions for p in patterns)
        total_overwrites = sum(p.overwrite_decisions for p in patterns)
        total_skips = sum(p.skip_decisions for p in patterns)
        
        # Calculate averages
        avg_decision_time = sum(p.avg_decision_time_seconds for p in patterns) / len(patterns)
        
        return {
            'total_collisions': total_collisions,
            'total_overwrites': total_overwrites,
            'total_skips': total_skips,
            'overall_overwrite_rate': total_overwrites / total_collisions if total_collisions > 0 else 0,
            'overall_skip_rate': total_skips / total_collisions if total_collisions > 0 else 0,
            'avg_decision_time_seconds': avg_decision_time,
            'active_users_last_24h': len([
                p for p in patterns 
                if p.last_activity and p.last_activity >= datetime.now() - timedelta(hours=24)
            ]),
        }
    
    def cleanup_old_data(self) -> None:
        """Clean up old data beyond retention period."""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        
        with self._lock:
            # Clean up hourly stats
            old_hours = [hour for hour in self.hourly_stats.keys() if hour < cutoff_time]
            for hour in old_hours:
                del self.hourly_stats[hour]
            
            logger.info(
                "metrics_cleanup_completed",
                cleaned_hours=len(old_hours),
                retention_hours=self.retention_hours,
                remaining_events=len(self.collision_events),
                remaining_metrics=len(self.overwrite_metrics),
            )


# Global metrics collector instance
_metrics_collector = CollisionMetricsCollector()


def get_metrics_collector() -> CollisionMetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics_collector


def log_collision_detected(user_id: str, filename: str, **details) -> None:
    """Log a collision detection event."""
    _metrics_collector.log_collision_event(user_id, 'detected', filename, **details)


def log_collision_resolved(user_id: str, filename: str, decision: str, **details) -> None:
    """Log a collision resolution event."""
    _metrics_collector.log_collision_event(user_id, 'resolved', filename, decision=decision, **details)
    _metrics_collector.track_user_decision(user_id, decision, details.get('decision_time_seconds', 0))


def log_batch_collision_check(user_id: str, file_count: int, collisions_found: int, duration_ms: float, **details) -> None:
    """Log a batch collision check event."""
    _metrics_collector.log_collision_event(
        user_id, 'batch_processed', f"{file_count}_files", 
        file_count=file_count, collisions_found=collisions_found, duration_ms=duration_ms, **details
    )
    _metrics_collector.log_performance_metrics(
        'batch_collision_check', duration_ms, file_count, **details
    )


def log_overwrite_operation(
    user_id: str, filename: str, operation_type: str, success: bool, 
    duration_ms: float, file_size: int, error_message: str = None
) -> None:
    """Log an overwrite operation."""
    _metrics_collector.log_overwrite_metrics(
        user_id, filename, operation_type, success, duration_ms, file_size, error_message
    )
