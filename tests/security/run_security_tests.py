#!/usr/bin/env python3
"""
Security test runner script.

This script runs comprehensive security tests and generates detailed security reports.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def run_authentication_security_tests():
    """Run authentication security tests."""
    print("Running authentication security tests...")

    import subprocess

    # Run authentication security tests
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/security/test_authentication_security.py",
            "-v",
            "--tb=short",
            "-m",
            "security",
        ],
        capture_output=True,
        text=True,
    )

    return {
        "test_type": "Authentication Security",
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0,
    }


def run_data_access_security_tests():
    """Run data access security tests."""
    print("Running data access security tests...")

    import subprocess

    # Run data access security tests
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/security/test_data_access_security.py",
            "-v",
            "--tb=short",
            "-m",
            "security",
        ],
        capture_output=True,
        text=True,
    )

    return {
        "test_type": "Data Access Security",
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0,
    }


def run_signed_url_security_tests():
    """Run signed URL security tests."""
    print("Running signed URL security tests...")

    import subprocess

    # Run signed URL security tests
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/security/test_signed_url_security.py",
            "-v",
            "--tb=short",
            "-m",
            "security",
        ],
        capture_output=True,
        text=True,
    )

    return {
        "test_type": "Signed URL Security",
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0,
    }


def analyze_security_test_results(results):
    """Analyze security test results and identify potential vulnerabilities."""
    analysis = {"total_tests": 0, "passed_tests": 0, "failed_tests": 0, "vulnerabilities": [], "recommendations": []}

    for result in results:
        if result["success"]:
            # Count passed tests from stdout
            if "passed" in result["stdout"]:
                try:
                    # Extract test count from pytest output
                    lines = result["stdout"].split("\n")
                    for line in lines:
                        if "passed" in line and "failed" not in line:
                            # Parse line like "15 passed in 2.34s"
                            parts = line.split()
                            if len(parts) > 0 and parts[0].isdigit():
                                analysis["passed_tests"] += int(parts[0])
                                analysis["total_tests"] += int(parts[0])
                except ValueError:
                    pass
        else:
            # Count failed tests and identify vulnerabilities
            if "failed" in result["stdout"] or "FAILED" in result["stdout"]:
                try:
                    lines = result["stdout"].split("\n")
                    for line in lines:
                        if "failed" in line:
                            parts = line.split()
                            if len(parts) > 0 and parts[0].isdigit():
                                failed_count = int(parts[0])
                                analysis["failed_tests"] += failed_count
                                analysis["total_tests"] += failed_count

                                # Add vulnerability based on test type
                                analysis["vulnerabilities"].append(
                                    {
                                        "category": result["test_type"],
                                        "severity": "HIGH",
                                        "description": f"{failed_count} security tests failed in {result['test_type']}",
                                        "details": result["stderr"],
                                    }
                                )
                except ValueError:
                    pass

    # Generate recommendations based on results
    if analysis["failed_tests"] > 0:
        analysis["recommendations"].extend(
            [
                "Review failed security tests and fix identified vulnerabilities",
                "Implement additional security controls based on test failures",
                "Consider security code review for affected components",
            ]
        )

    if analysis["total_tests"] == 0:
        analysis["recommendations"].append("No security tests were executed - verify test configuration")

    # Add general security recommendations
    analysis["recommendations"].extend(
        [
            "Regularly run security tests as part of CI/CD pipeline",
            "Implement security monitoring and alerting",
            "Conduct periodic security audits and penetration testing",
            "Keep dependencies updated to address security vulnerabilities",
        ]
    )

    return analysis


def generate_security_report(results, analysis, output_dir):
    """Generate a comprehensive security report."""
    report_lines = [
        "=" * 80,
        "COMPREHENSIVE SECURITY TEST REPORT",
        "=" * 80,
        f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "EXECUTIVE SUMMARY",
        "-" * 40,
        f"Total security tests executed: {analysis['total_tests']}",
        f"Tests passed: {analysis['passed_tests']}",
        f"Tests failed: {analysis['failed_tests']}",
        f"Success rate: {(analysis['passed_tests'] / max(analysis['total_tests'], 1) * 100):.1f}%",
        "",
    ]

    # Vulnerability summary
    if analysis["vulnerabilities"]:
        report_lines.extend(
            [
                "SECURITY VULNERABILITIES DETECTED",
                "-" * 40,
            ]
        )

        for vuln in analysis["vulnerabilities"]:
            report_lines.extend(
                [
                    f"Category: {vuln['category']}",
                    f"Severity: {vuln['severity']}",
                    f"Description: {vuln['description']}",
                    (
                        f"Details: {vuln['details'][:200]}..."
                        if len(vuln["details"]) > 200
                        else f"Details: {vuln['details']}"
                    ),
                    "",
                ]
            )
    else:
        report_lines.extend(
            [
                "SECURITY STATUS: NO CRITICAL VULNERABILITIES DETECTED",
                "-" * 40,
                "All security tests passed successfully.",
                "",
            ]
        )

    # Detailed test results
    report_lines.extend(
        [
            "DETAILED TEST RESULTS",
            "-" * 40,
        ]
    )

    for result in results:
        status = "PASS" if result["success"] else "FAIL"
        report_lines.extend(
            [
                f"{result['test_type']}: {status}",
                f"Return code: {result['return_code']}",
            ]
        )

        if result["success"]:
            # Extract summary from successful test output
            lines = result["stdout"].split("\n")
            for line in lines:
                if "passed" in line and "failed" not in line:
                    report_lines.append(f"Result: {line.strip()}")
                    break
        else:
            # Show error details for failed tests
            report_lines.append("Errors:")
            error_lines = result["stderr"].split("\n")[:5]  # First 5 lines of errors
            for error_line in error_lines:
                if error_line.strip():
                    report_lines.append(f"  {error_line.strip()}")

        report_lines.append("")

    # Security recommendations
    report_lines.extend(
        [
            "SECURITY RECOMMENDATIONS",
            "-" * 40,
        ]
    )

    for i, recommendation in enumerate(analysis["recommendations"], 1):
        report_lines.append(f"{i}. {recommendation}")

    report_lines.extend(["", "=" * 80])

    # Save report
    report_content = "\n".join(report_lines)
    report_file = os.path.join(output_dir, "security_report.txt")

    with open(report_file, "w") as f:
        f.write(report_content)

    return report_content, report_file


def save_detailed_results(results, output_dir):
    """Save detailed test results to separate files."""
    for result in results:
        # Create filename from test type
        filename = result["test_type"].lower().replace(" ", "_") + "_results.txt"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w") as f:
            f.write(f"Test Type: {result['test_type']}\n")
            f.write(f"Return Code: {result['return_code']}\n")
            f.write(f"Success: {result['success']}\n")
            f.write("\n" + "=" * 50 + "\n")
            f.write("STDOUT:\n")
            f.write(result["stdout"])
            f.write("\n" + "=" * 50 + "\n")
            f.write("STDERR:\n")
            f.write(result["stderr"])


def main():
    """Main function to run security tests."""
    parser = argparse.ArgumentParser(description="Run security tests for imgstream application")
    parser.add_argument("--output-dir", default="./security_results", help="Directory to save security test results")
    parser.add_argument("--skip-auth-tests", action="store_true", help="Skip authentication security tests")
    parser.add_argument("--skip-data-tests", action="store_true", help="Skip data access security tests")
    parser.add_argument("--skip-url-tests", action="store_true", help="Skip signed URL security tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Create output directory
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    print("Starting comprehensive security tests...")
    print(f"Results will be saved to: {output_dir}")
    print("-" * 60)

    results = []

    try:
        # Run authentication security tests
        if not args.skip_auth_tests:
            auth_result = run_authentication_security_tests()
            results.append(auth_result)
            status = "✓" if auth_result["success"] else "✗"
            print(f"{status} Authentication security tests completed")

        # Run data access security tests
        if not args.skip_data_tests:
            data_result = run_data_access_security_tests()
            results.append(data_result)
            status = "✓" if data_result["success"] else "✗"
            print(f"{status} Data access security tests completed")

        # Run signed URL security tests
        if not args.skip_url_tests:
            url_result = run_signed_url_security_tests()
            results.append(url_result)
            status = "✓" if url_result["success"] else "✗"
            print(f"{status} Signed URL security tests completed")

        # Analyze results
        analysis = analyze_security_test_results(results)

        # Generate comprehensive report
        report_content, report_file = generate_security_report(results, analysis, output_dir)

        print(f"\n✓ Security report generated: {report_file}")

        # Save detailed results
        save_detailed_results(results, output_dir)
        print(f"✓ Detailed results saved to: {output_dir}")

        if args.verbose:
            print("\nSecurity Report Summary:")
            print(report_content)

        print("\n" + "=" * 60)

        # Print security status
        if analysis["failed_tests"] > 0:
            print("⚠️  SECURITY ISSUES DETECTED!")
            print(f"   {analysis['failed_tests']} security tests failed")
            print("   Review the security report for details")
            return_code = 1
        else:
            print("✅ SECURITY TESTS PASSED!")
            print("   No critical security vulnerabilities detected")
            return_code = 0

        print(f"   Total tests: {analysis['total_tests']}")
        print(f"   Success rate: {(analysis['passed_tests'] / max(analysis['total_tests'], 1) * 100):.1f}%")

        return return_code

    except Exception as e:
        print(f"\n✗ Security testing failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
