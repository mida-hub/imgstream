"""
Performance monitoring utilities for load testing.

This module provides utilities to monitor system resources during performance tests.
"""

import os
import threading
import time
from dataclasses import dataclass

import psutil


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    timestamp: float
    memory_usage_mb: float
    cpu_percent: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_io_sent_mb: float
    network_io_recv_mb: float


class PerformanceMonitor:
    """Monitor system performance during tests."""

    def __init__(self, interval: float = 0.1):
        """
        Initialize performance monitor.

        Args:
            interval: Monitoring interval in seconds
        """
        self.interval = interval
        self.monitoring = False
        self.metrics: list[PerformanceMetrics] = []
        self.monitor_thread: threading.Thread | None = None
        self.process = psutil.Process(os.getpid())

        # Initial values for delta calculations
        self.initial_disk_io = psutil.disk_io_counters()
        self.initial_network_io = psutil.net_io_counters()

    def start_monitoring(self):
        """Start performance monitoring in a separate thread."""
        if self.monitoring:
            return

        self.monitoring = True
        self.metrics.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                # Get current metrics
                current_time = time.time()

                # Memory metrics
                memory_info = self.process.memory_info()
                memory_usage_mb = memory_info.rss / (1024 * 1024)
                memory_percent = self.process.memory_percent()

                # CPU metrics
                cpu_percent = self.process.cpu_percent()

                # Disk I/O metrics
                disk_io = psutil.disk_io_counters()
                if disk_io and self.initial_disk_io:
                    disk_read_mb = (disk_io.read_bytes - self.initial_disk_io.read_bytes) / (1024 * 1024)
                    disk_write_mb = (disk_io.write_bytes - self.initial_disk_io.write_bytes) / (1024 * 1024)
                else:
                    disk_read_mb = disk_write_mb = 0.0

                # Network I/O metrics
                network_io = psutil.net_io_counters()
                if network_io and self.initial_network_io:
                    network_sent_mb = (network_io.bytes_sent - self.initial_network_io.bytes_sent) / (1024 * 1024)
                    network_recv_mb = (network_io.bytes_recv - self.initial_network_io.bytes_recv) / (1024 * 1024)
                else:
                    network_sent_mb = network_recv_mb = 0.0

                # Store metrics
                metrics = PerformanceMetrics(
                    timestamp=current_time,
                    memory_usage_mb=memory_usage_mb,
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    disk_io_read_mb=disk_read_mb,
                    disk_io_write_mb=disk_write_mb,
                    network_io_sent_mb=network_sent_mb,
                    network_io_recv_mb=network_recv_mb,
                )

                self.metrics.append(metrics)

            except Exception as e:
                # Continue monitoring even if individual measurements fail
                print(f"Warning: Failed to collect metrics: {e}")

            time.sleep(self.interval)

    def get_summary(self) -> dict[str, float]:
        """
        Get performance summary statistics.

        Returns:
            Dictionary with performance statistics
        """
        if not self.metrics:
            return {}

        # Calculate statistics
        memory_values = [m.memory_usage_mb for m in self.metrics]
        cpu_values = [m.cpu_percent for m in self.metrics]
        memory_percent_values = [m.memory_percent for m in self.metrics]

        return {
            "duration_seconds": self.metrics[-1].timestamp - self.metrics[0].timestamp,
            "memory_usage_avg_mb": sum(memory_values) / len(memory_values),
            "memory_usage_max_mb": max(memory_values),
            "memory_usage_min_mb": min(memory_values),
            "cpu_percent_avg": sum(cpu_values) / len(cpu_values),
            "cpu_percent_max": max(cpu_values),
            "memory_percent_avg": sum(memory_percent_values) / len(memory_percent_values),
            "memory_percent_max": max(memory_percent_values),
            "disk_io_read_total_mb": self.metrics[-1].disk_io_read_mb,
            "disk_io_write_total_mb": self.metrics[-1].disk_io_write_mb,
            "network_io_sent_total_mb": self.metrics[-1].network_io_sent_mb,
            "network_io_recv_total_mb": self.metrics[-1].network_io_recv_mb,
            "sample_count": len(self.metrics),
        }

    def get_peak_memory_usage(self) -> float:
        """Get peak memory usage in MB."""
        if not self.metrics:
            return 0.0
        return max(m.memory_usage_mb for m in self.metrics)

    def get_average_cpu_usage(self) -> float:
        """Get average CPU usage percentage."""
        if not self.metrics:
            return 0.0
        cpu_values = [m.cpu_percent for m in self.metrics if m.cpu_percent > 0]
        return sum(cpu_values) / len(cpu_values) if cpu_values else 0.0

    def check_memory_leak(self, threshold_mb: float = 50.0) -> bool:
        """
        Check for potential memory leaks.

        Args:
            threshold_mb: Memory increase threshold in MB

        Returns:
            True if potential memory leak detected
        """
        if len(self.metrics) < 10:
            return False

        # Compare first 10% and last 10% of measurements
        early_count = max(1, len(self.metrics) // 10)
        late_count = max(1, len(self.metrics) // 10)

        early_avg = sum(m.memory_usage_mb for m in self.metrics[:early_count]) / early_count
        late_avg = sum(m.memory_usage_mb for m in self.metrics[-late_count:]) / late_count

        return (late_avg - early_avg) > threshold_mb

    def export_metrics_csv(self, filename: str):
        """Export metrics to CSV file for analysis."""
        import csv

        with open(filename, "w", newline="") as csvfile:
            fieldnames = [
                "timestamp",
                "memory_usage_mb",
                "cpu_percent",
                "memory_percent",
                "disk_io_read_mb",
                "disk_io_write_mb",
                "network_io_sent_mb",
                "network_io_recv_mb",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for metric in self.metrics:
                writer.writerow(
                    {
                        "timestamp": metric.timestamp,
                        "memory_usage_mb": metric.memory_usage_mb,
                        "cpu_percent": metric.cpu_percent,
                        "memory_percent": metric.memory_percent,
                        "disk_io_read_mb": metric.disk_io_read_mb,
                        "disk_io_write_mb": metric.disk_io_write_mb,
                        "network_io_sent_mb": metric.network_io_sent_mb,
                        "network_io_recv_mb": metric.network_io_recv_mb,
                    }
                )


class LoadTestRunner:
    """Helper class to run load tests with performance monitoring."""

    def __init__(self, monitor_interval: float = 0.1):
        """
        Initialize load test runner.

        Args:
            monitor_interval: Performance monitoring interval in seconds
        """
        self.monitor = PerformanceMonitor(monitor_interval)
        self.test_results: dict[str, any] = {}

    def run_test(self, test_name: str, test_function, *args, **kwargs):
        """
        Run a test function with performance monitoring.

        Args:
            test_name: Name of the test
            test_function: Function to execute
            *args: Arguments for test function
            **kwargs: Keyword arguments for test function

        Returns:
            Test result and performance metrics
        """
        print(f"Starting load test: {test_name}")

        # Start monitoring
        self.monitor.start_monitoring()
        start_time = time.time()

        try:
            # Run the test
            result = test_function(*args, **kwargs)
            success = True
            error = None

        except Exception as e:
            result = None
            success = False
            error = str(e)

        finally:
            # Stop monitoring
            end_time = time.time()
            self.monitor.stop_monitoring()

        # Collect results
        performance_summary = self.monitor.get_summary()
        test_result = {
            "test_name": test_name,
            "success": success,
            "error": error,
            "result": result,
            "execution_time": end_time - start_time,
            "performance": performance_summary,
        }

        self.test_results[test_name] = test_result

        # Print summary
        if success:
            print(f"✓ {test_name} completed successfully")
        else:
            print(f"✗ {test_name} failed: {error}")

        print(f"  Execution time: {test_result['execution_time']:.2f}s")
        print(f"  Peak memory: {performance_summary.get('memory_usage_max_mb', 0):.1f}MB")
        print(f"  Avg CPU: {performance_summary.get('cpu_percent_avg', 0):.1f}%")

        return test_result

    def generate_report(self) -> str:
        """Generate a comprehensive performance report."""
        if not self.test_results:
            return "No test results available."

        report_lines = ["=" * 60, "PERFORMANCE TEST REPORT", "=" * 60, ""]

        # Summary statistics
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results.values() if r["success"])
        failed_tests = total_tests - successful_tests

        report_lines.extend(
            [f"Total tests: {total_tests}", f"Successful: {successful_tests}", f"Failed: {failed_tests}", ""]
        )

        # Individual test results
        for test_name, result in self.test_results.items():
            status = "PASS" if result["success"] else "FAIL"
            report_lines.extend([f"{test_name}: {status}", f"  Execution time: {result['execution_time']:.2f}s"])

            if result["performance"]:
                perf = result["performance"]
                report_lines.extend(
                    [
                        f"  Peak memory: {perf.get('memory_usage_max_mb', 0):.1f}MB",
                        f"  Avg memory: {perf.get('memory_usage_avg_mb', 0):.1f}MB",
                        f"  Max CPU: {perf.get('cpu_percent_max', 0):.1f}%",
                        f"  Avg CPU: {perf.get('cpu_percent_avg', 0):.1f}%",
                    ]
                )

            if not result["success"]:
                report_lines.append(f"  Error: {result['error']}")

            report_lines.append("")

        return "\n".join(report_lines)

    def save_report(self, filename: str):
        """Save performance report to file."""
        with open(filename, "w") as f:
            f.write(self.generate_report())
