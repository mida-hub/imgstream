"""Monitoring and metrics collection for ImgStream application.

This module provides comprehensive monitoring capabilities including:
- Custom metrics collection
- Performance monitoring
- Error tracking
- Resource utilization monitoring
- Business metrics tracking
"""

# mypy: ignore-errors

import functools
import logging
import queue
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    from google.cloud import monitoring_v3  # type: ignore

    CLOUD_MONITORING_AVAILABLE = True
except ImportError:
    CLOUD_MONITORING_AVAILABLE = False

from .config import get_config

logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """Data structure for metric information."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime | None = None
    unit: str = "1"
    description: str = ""


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""

    request_count: int = 0
    error_count: int = 0
    total_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = float("inf")
    active_requests: int = 0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0


class MetricsCollector:
    """Collects and manages application metrics."""

    def __init__(self) -> None:
        self.config = get_config()
        self.metrics_enabled = self.config.get("METRICS_ENABLED", True, bool)
        self.performance_metrics = PerformanceMetrics()
        self._metrics_queue: queue.Queue[MetricData] = queue.Queue()
        self._lock = threading.Lock()

        # Initialize Cloud Monitoring client if available
        self.monitoring_client = None
        if CLOUD_MONITORING_AVAILABLE and self.metrics_enabled:
            try:
                self.monitoring_client = monitoring_v3.MetricServiceClient()
                self.project_name = f"projects/{self.config.get_required('GOOGLE_CLOUD_PROJECT')}"
                logger.info("Cloud Monitoring client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Cloud Monitoring client: {e}")

        # Start metrics processing thread
        if self.metrics_enabled:
            self._start_metrics_processor()

    def _start_metrics_processor(self):
        """Start background thread for processing metrics."""

        def process_metrics():
            while True:
                try:
                    metric = self._metrics_queue.get(timeout=1)
                    if metric is None:  # Shutdown signal
                        break
                    self._send_metric_to_cloud_monitoring(metric)
                    self._metrics_queue.task_done()
                except queue.Empty:
                    pass  # Continue the loop  # type: ignore[unreachable]
                except Exception as e:
                    logger.error(f"Error processing metric: {e}")

        thread = threading.Thread(target=process_metrics, daemon=True)
        thread.start()
        logger.info("Metrics processor thread started")

    def record_metric(
        self, name: str, value: float, labels: dict[str, str] | None = None, unit: str = "1", description: str = ""
    ):
        """Record a custom metric."""
        if not self.metrics_enabled:
            return

        metric = MetricData(
            name=name, value=value, labels=labels or {}, timestamp=datetime.utcnow(), unit=unit, description=description
        )

        try:
            self._metrics_queue.put_nowait(metric)
        except queue.Full:
            logger.warning("Metrics queue is full, dropping metric")

    def _send_metric_to_cloud_monitoring(self, metric: MetricData):
        """Send metric to Google Cloud Monitoring."""
        if not self.monitoring_client:
            return

        try:
            # Create metric descriptor if it doesn't exist
            metric_type = f"custom.googleapis.com/imgstream/{metric.name}"

            # Create time series data
            series = monitoring_v3.TimeSeries()
            series.metric.type = metric_type
            series.resource.type = "cloud_run_revision"
            series.resource.labels["service_name"] = f"imgstream-{self.config.get('ENVIRONMENT', 'development')}"
            series.resource.labels["revision_name"] = "latest"
            series.resource.labels["location"] = "us-central1"

            # Add custom labels
            for key, value in metric.labels.items():
                series.metric.labels[key] = str(value)

            # Create data point
            point = monitoring_v3.Point()
            point.value.double_value = metric.value
            point.interval.end_time.seconds = int(time.time())
            series.points = [point]

            # Send to Cloud Monitoring
            self.monitoring_client.create_time_series(name=self.project_name, time_series=[series])

        except Exception as e:
            logger.error(f"Failed to send metric to Cloud Monitoring: {e}")

    def increment_counter(self, name: str, labels: dict[str, str] | None = None, value: float = 1.0):
        """Increment a counter metric."""
        self.record_metric(f"{name}_total", value, labels, "1", f"Total count of {name}")

    def record_histogram(self, name: str, value: float, labels: dict[str, str] | None = None, unit: str = "s"):
        """Record a histogram metric (typically for latencies)."""
        self.record_metric(f"{name}_histogram", value, labels, unit, f"Histogram of {name}")

    def record_gauge(self, name: str, value: float, labels: dict[str, str] | None = None, unit: str = "1"):
        """Record a gauge metric (current value)."""
        self.record_metric(f"{name}_gauge", value, labels, unit, f"Current value of {name}")

    @contextmanager
    def time_operation(self, operation_name: str, labels: dict[str, str] | None = None):
        """Context manager to time operations."""
        start_time = time.time()
        with self._lock:
            self.performance_metrics.active_requests += 1

        try:
            yield
        finally:
            duration = time.time() - start_time

            with self._lock:
                self.performance_metrics.active_requests -= 1
                self.performance_metrics.request_count += 1
                self.performance_metrics.total_response_time += duration
                self.performance_metrics.max_response_time = max(self.performance_metrics.max_response_time, duration)
                self.performance_metrics.min_response_time = min(self.performance_metrics.min_response_time, duration)

            # Record metrics
            self.record_histogram("request_duration", duration, labels, "s")
            self.increment_counter("requests", labels)

    def record_error(self, error_type: str, labels: dict[str, str] | None = None):
        """Record an error occurrence."""
        with self._lock:
            self.performance_metrics.error_count += 1

        error_labels = {"error_type": error_type}
        if labels:
            error_labels.update(labels)

        self.increment_counter("errors", error_labels)

    def record_business_metric(self, metric_name: str, value: float, labels: dict[str, str] | None = None):
        """Record business-specific metrics."""
        business_labels = {"metric_type": "business"}
        if labels:
            business_labels.update(labels)

        self.record_gauge(f"business_{metric_name}", value, business_labels)

    def get_performance_summary(self) -> dict[str, Any]:
        """Get current performance metrics summary."""
        with self._lock:
            avg_response_time = self.performance_metrics.total_response_time / max(
                self.performance_metrics.request_count, 1
            )

            return {
                "request_count": self.performance_metrics.request_count,
                "error_count": self.performance_metrics.error_count,
                "error_rate": (self.performance_metrics.error_count / max(self.performance_metrics.request_count, 1)),
                "avg_response_time": avg_response_time,
                "max_response_time": self.performance_metrics.max_response_time,
                "min_response_time": (
                    self.performance_metrics.min_response_time
                    if self.performance_metrics.min_response_time != float("inf")
                    else 0
                ),
                "active_requests": self.performance_metrics.active_requests,
                "memory_usage": self.performance_metrics.memory_usage,
                "cpu_usage": self.performance_metrics.cpu_usage,
            }


class HealthChecker:
    """Health check functionality with monitoring integration."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.config = get_config()
        self.metrics = metrics_collector
        self.last_health_check = None
        self.health_status = {"status": "unknown"}

    def check_health(self) -> dict[str, Any]:
        """Perform comprehensive health check."""
        start_time = time.time()
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": self.config.get("ENVIRONMENT", "development"),
            "checks": {},
        }

        # Database health check
        try:
            db_status = self._check_database()
            health_status["checks"]["database"] = db_status
            if not db_status["healthy"]:
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["database"] = {"healthy": False, "error": str(e)}
            health_status["status"] = "unhealthy"

        # Storage health check
        try:
            storage_status = self._check_storage()
            health_status["checks"]["storage"] = storage_status
            if not storage_status["healthy"]:
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["storage"] = {"healthy": False, "error": str(e)}
            health_status["status"] = "unhealthy"

        # Configuration health check
        try:
            config_status = self._check_configuration()
            health_status["checks"]["configuration"] = config_status
            if not config_status["healthy"]:
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["configuration"] = {"healthy": False, "error": str(e)}
            health_status["status"] = "unhealthy"

        # Record health check metrics
        check_duration = time.time() - start_time
        self.metrics.record_histogram("health_check_duration", check_duration)
        self.metrics.record_gauge("health_status", 1 if health_status["status"] == "healthy" else 0)

        # Record individual check results
        for check_name, check_result in health_status["checks"].items():
            self.metrics.record_gauge("health_check_status", 1 if check_result["healthy"] else 0, {"check": check_name})

        self.last_health_check = datetime.utcnow()  # type: ignore[assignment]
        self.health_status = health_status

        return health_status

    def _check_database(self) -> dict[str, Any]:
        """Check database connectivity."""
        try:
            # Import here to avoid circular imports
            from .database import get_database

            db = get_database()
            # Simple query to test connectivity
            result = db.execute("SELECT 1").fetchone()

            return {
                "healthy": result is not None,
                "response_time_ms": 0,  # Could measure actual response time
                "details": "Database connection successful",
            }
        except Exception as e:
            return {"healthy": False, "error": str(e), "details": "Database connection failed"}

    def _check_storage(self) -> dict[str, Any]:
        """Check storage connectivity."""
        try:
            # Import here to avoid circular imports
            from .services.storage import get_storage_service

            storage = get_storage_service()
            # Test bucket accessibility
            bucket_exists = storage.check_bucket_exists()
            database_bucket = self.config.get("GCS_DATABASE_BUCKET", "unknown")

            return {
                "healthy": bucket_exists,
                "storage_type": "gcs",
                "bucket": database_bucket,
                "details": "GCS bucket accessible" if bucket_exists else "GCS bucket not accessible",
            }
        except Exception as e:
            return {"healthy": False, "error": str(e), "details": "Storage check failed"}

    def _check_configuration(self) -> dict[str, Any]:
        """Check configuration validity."""
        try:
            # Validate configuration
            from .config import validate_config

            validate_config()

            return {
                "healthy": True,
                "environment": self.config.get("ENVIRONMENT", "development"),
                "details": "Configuration is valid",
            }
        except Exception as e:
            return {"healthy": False, "error": str(e), "details": "Configuration validation failed"}


# Global instances
_metrics_collector = None
_health_checker = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(get_metrics_collector())
    return _health_checker


def monitor_function(operation_name: str | None = None, labels: dict[str, str] | None = None):
    """Decorator to monitor function execution."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics_collector()
            op_name = operation_name or func.__name__

            with metrics.time_operation(op_name, labels):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    metrics.record_error(type(e).__name__, labels)
                    raise

        return wrapper

    return decorator


def record_business_event(event_name: str, value: float = 1.0, labels: dict[str, str] | None = None):
    """Record a business event metric."""
    metrics = get_metrics_collector()
    metrics.record_business_metric(event_name, value, labels)


# Example usage decorators for common operations
def monitor_upload(func: Callable[..., Any]) -> Callable[..., Any]:
    """Monitor file upload operations."""
    return monitor_function("file_upload", {"operation": "upload"})(func)  # type: ignore[no-any-return]


def monitor_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    """Monitor authentication operations."""
    return monitor_function("authentication", {"operation": "auth"})(func)  # type: ignore[no-any-return]


def monitor_database(func: Callable[..., Any]) -> Callable[..., Any]:
    """Monitor database operations."""
    return monitor_function("database_operation", {"operation": "db"})(func)  # type: ignore[no-any-return]
