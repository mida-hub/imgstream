#!/usr/bin/env python3
"""
Performance test runner script.

This script runs comprehensive performance tests and generates detailed reports.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.performance.performance_monitor import LoadTestRunner, PerformanceMonitor


def run_image_processing_performance_tests():
    """Run image processing performance tests."""
    print("Running image processing performance tests...")

    # Import here to avoid circular imports
    from tests.performance.test_image_processing_performance import TestImageProcessingPerformance

    test_instance = TestImageProcessingPerformance()

    # Create test data
    import io
    from PIL import Image

    # Sample image
    image = Image.new("RGB", (2000, 1500), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    sample_image_data = buffer.getvalue()

    # Large image
    large_image = Image.new("RGB", (4000, 3000), color="blue")
    large_buffer = io.BytesIO()
    large_image.save(large_buffer, format="JPEG", quality=95)
    large_image_data = large_buffer.getvalue()

    # Get image processor
    from src.imgstream.services.image_processor import ImageProcessor

    image_processor = ImageProcessor()

    results = {}

    # Test metadata extraction
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    start_time = time.time()

    for i in range(10):
        result = image_processor.extract_metadata(sample_image_data, f"test_{i}.jpg")
        assert result is not None

    end_time = time.time()
    monitor.stop_monitoring()

    results["metadata_extraction"] = {
        "duration": end_time - start_time,
        "iterations": 10,
        "avg_time_per_operation": (end_time - start_time) / 10,
        "performance": monitor.get_summary(),
    }

    # Test thumbnail generation
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    start_time = time.time()

    for i in range(10):
        thumbnail = image_processor.generate_thumbnail(sample_image_data)
        assert thumbnail is not None

    end_time = time.time()
    monitor.stop_monitoring()

    results["thumbnail_generation"] = {
        "duration": end_time - start_time,
        "iterations": 10,
        "avg_time_per_operation": (end_time - start_time) / 10,
        "performance": monitor.get_summary(),
    }

    # Test large image processing
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    start_time = time.time()

    for i in range(5):
        thumbnail = image_processor.generate_thumbnail(large_image_data)
        assert thumbnail is not None

    end_time = time.time()
    monitor.stop_monitoring()

    results["large_image_processing"] = {
        "duration": end_time - start_time,
        "iterations": 5,
        "avg_time_per_operation": (end_time - start_time) / 5,
        "performance": monitor.get_summary(),
    }

    return results


def run_load_performance_tests():
    """Run load and stress performance tests."""
    print("Running load performance tests...")

    # Import test dependencies
    from tests.e2e.base import E2ETestBase
    from tests.performance.test_load_performance import TestLoadPerformance

    # Create test instance
    test_instance = TestLoadPerformance()
    test_instance.setup_test_environment()

    # Create test users
    from tests.e2e.base import MockUser

    test_users = {
        "user1": MockUser("test-user-1", "user1@example.com", "Test User 1"),
        "user2": MockUser("test-user-2", "user2@example.com", "Test User 2"),
        "admin": MockUser("admin-user", "admin@example.com", "Admin User"),
    }

    runner = LoadTestRunner()

    # Run individual performance tests
    results = {}

    # Test 1: Large file upload performance
    def large_file_test():
        return test_instance.test_large_file_upload_performance(test_users, lambda func: func())

    results["large_file_upload"] = runner.run_test("Large File Upload", large_file_test)

    # Test 2: Multiple file upload performance
    def multiple_file_test():
        return test_instance.test_multiple_file_upload_performance(test_users)

    results["multiple_file_upload"] = runner.run_test("Multiple File Upload", multiple_file_test)

    # Test 3: Concurrent upload performance
    def concurrent_upload_test():
        return test_instance.test_concurrent_upload_performance(test_users)

    results["concurrent_upload"] = runner.run_test("Concurrent Upload", concurrent_upload_test)

    # Test 4: Memory usage test
    def memory_usage_test():
        return test_instance.test_memory_usage_during_bulk_operations(test_users)

    results["memory_usage"] = runner.run_test("Memory Usage", memory_usage_test)

    # Test 5: Response time under load
    def response_time_test():
        return test_instance.test_response_time_under_load(test_users)

    results["response_time"] = runner.run_test("Response Time Under Load", response_time_test)

    return runner, results


def generate_comprehensive_report(image_results, load_runner, load_results, output_dir):
    """Generate a comprehensive performance report."""
    report_lines = [
        "=" * 80,
        "COMPREHENSIVE PERFORMANCE TEST REPORT",
        "=" * 80,
        f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "EXECUTIVE SUMMARY",
        "-" * 40,
    ]

    # Overall statistics
    total_tests = len(image_results) + len(load_results)
    failed_tests = sum(1 for r in load_results.values() if not r["success"])

    report_lines.extend(
        [
            f"Total performance tests executed: {total_tests}",
            f"Failed tests: {failed_tests}",
            f"Success rate: {((total_tests - failed_tests) / total_tests * 100):.1f}%",
            "",
        ]
    )

    # Image processing performance
    report_lines.extend(
        [
            "IMAGE PROCESSING PERFORMANCE",
            "-" * 40,
        ]
    )

    for test_name, result in image_results.items():
        report_lines.extend(
            [
                f"{test_name.replace('_', ' ').title()}:",
                f"  Total duration: {result['duration']:.2f}s",
                f"  Iterations: {result['iterations']}",
                f"  Avg time per operation: {result['avg_time_per_operation']:.3f}s",
                f"  Peak memory: {result['performance'].get('memory_usage_max_mb', 0):.1f}MB",
                f"  Avg CPU: {result['performance'].get('cpu_percent_avg', 0):.1f}%",
                "",
            ]
        )

    # Load test performance
    report_lines.extend(
        [
            "LOAD TEST PERFORMANCE",
            "-" * 40,
        ]
    )

    for test_name, result in load_results.items():
        status = "PASS" if result["success"] else "FAIL"
        report_lines.extend(
            [
                f"{test_name.replace('_', ' ').title()}: {status}",
                f"  Execution time: {result['execution_time']:.2f}s",
            ]
        )

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

    # Performance recommendations
    report_lines.extend(
        [
            "PERFORMANCE RECOMMENDATIONS",
            "-" * 40,
        ]
    )

    recommendations = []

    # Check for high memory usage
    max_memory = max(
        (r["performance"].get("memory_usage_max_mb", 0) for r in load_results.values() if r["performance"]), default=0
    )

    if max_memory > 500:
        recommendations.append("• High memory usage detected. Consider implementing memory optimization strategies.")

    # Check for slow operations
    slow_operations = [
        name for name, result in load_results.items() if result["success"] and result["execution_time"] > 30
    ]

    if slow_operations:
        recommendations.append(f"• Slow operations detected: {', '.join(slow_operations)}. Consider optimization.")

    # Check CPU usage
    max_cpu = max(
        (r["performance"].get("cpu_percent_max", 0) for r in load_results.values() if r["performance"]), default=0
    )

    if max_cpu > 80:
        recommendations.append("• High CPU usage detected. Consider implementing CPU optimization strategies.")

    if not recommendations:
        recommendations.append("• All performance metrics are within acceptable ranges.")

    report_lines.extend(recommendations)
    report_lines.extend(["", "=" * 80])

    # Save report
    report_content = "\n".join(report_lines)
    report_file = os.path.join(output_dir, "performance_report.txt")

    with open(report_file, "w") as f:
        f.write(report_content)

    return report_content, report_file


def main():
    """Main function to run performance tests."""
    parser = argparse.ArgumentParser(description="Run performance tests for imgstream application")
    parser.add_argument("--output-dir", default="./performance_results", help="Directory to save performance results")
    parser.add_argument("--skip-image-tests", action="store_true", help="Skip image processing performance tests")
    parser.add_argument("--skip-load-tests", action="store_true", help="Skip load performance tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Create output directory
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    print("Starting comprehensive performance tests...")
    print(f"Results will be saved to: {output_dir}")
    print("-" * 60)

    image_results = {}
    load_runner = None
    load_results = {}

    try:
        # Run image processing tests
        if not args.skip_image_tests:
            image_results = run_image_processing_performance_tests()
            print("✓ Image processing performance tests completed")

        # Run load tests
        if not args.skip_load_tests:
            load_runner, load_results = run_load_performance_tests()
            print("✓ Load performance tests completed")

        # Generate comprehensive report
        report_content, report_file = generate_comprehensive_report(
            image_results, load_runner, load_results, output_dir
        )

        print(f"\n✓ Performance report generated: {report_file}")

        if args.verbose:
            print("\nReport content:")
            print(report_content)

        # Save detailed load test report if available
        if load_runner:
            load_report_file = os.path.join(output_dir, "load_test_report.txt")
            load_runner.save_report(load_report_file)
            print(f"✓ Detailed load test report saved: {load_report_file}")

        print("\n" + "=" * 60)
        print("Performance testing completed successfully!")

        # Return exit code based on test results
        failed_tests = sum(1 for r in load_results.values() if not r["success"])
        return 1 if failed_tests > 0 else 0

    except Exception as e:
        print(f"\n✗ Performance testing failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
