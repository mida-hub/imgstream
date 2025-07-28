"""
Enhanced health check functionality for ImgStream application.

This module provides comprehensive health checks for all application components
including database, storage, authentication, external dependencies, and monitoring integration.
"""

import json
import os
import time
from typing import Any

import duckdb
import streamlit as st

try:
    from google.cloud import storage  # type: ignore
except ImportError:
    storage = None

from imgstream.logging_config import get_logger

logger = get_logger(__name__)


def check_database_health() -> dict[str, Any]:
    """Check database connectivity and health."""
    try:
        # Test DuckDB connection
        conn = duckdb.connect(":memory:")
        conn.execute("SELECT 1")
        conn.close()

        return {"status": "healthy", "message": "Database connection successful", "timestamp": time.time()}
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return {"status": "unhealthy", "message": f"Database connection failed: {str(e)}", "timestamp": time.time()}


def check_storage_health() -> dict[str, Any]:
    """Check Google Cloud Storage connectivity."""
    try:
        if storage is None:
            return {"status": "unhealthy", "message": "Google Cloud Storage not available", "timestamp": time.time()}

        # Initialize storage client
        client = storage.Client()

        # Get the bucket name from environment
        bucket_name = os.getenv("GCS_BUCKET")
        if not bucket_name:
            return {
                "status": "unhealthy",
                "message": "GCS_BUCKET environment variable not set",
                "timestamp": time.time(),
            }

        # Try to access the specific bucket
        bucket = client.bucket(bucket_name)
        bucket.exists()  # This will check if the bucket exists and we have access

        return {
            "status": "healthy",
            "message": f"Storage connection successful to bucket: {bucket_name}",
            "timestamp": time.time(),
            "bucket": bucket_name,
        }
    except Exception as e:
        logger.error("storage_health_check_failed", error=str(e))
        return {"status": "unhealthy", "message": f"Storage connection failed: {str(e)}", "timestamp": time.time()}


def check_environment_health() -> dict[str, Any]:
    """Check environment configuration."""
    try:
        required_env_vars = [
            "GOOGLE_CLOUD_PROJECT",
            "ENVIRONMENT",
        ]

        # Additional required vars for production
        if os.getenv("ENVIRONMENT") == "prod":
            required_env_vars.extend(
                [
                    "GCS_BUCKET",
                ]
            )

        missing_vars = []
        env_info = {}

        for var in required_env_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                env_info[var.lower()] = value

        if missing_vars:
            return {
                "status": "unhealthy",
                "message": f"Missing environment variables: {', '.join(missing_vars)}",
                "timestamp": time.time(),
                "missing_vars": missing_vars,
            }

        return {
            "status": "healthy",
            "message": "Environment configuration is valid",
            "timestamp": time.time(),
            "config": env_info,
        }
    except Exception as e:
        logger.error("environment_health_check_failed", error=str(e))
        return {"status": "unhealthy", "message": f"Environment check failed: {str(e)}", "timestamp": time.time()}


def get_application_info() -> dict[str, Any]:
    """Get application information."""
    return {
        "name": "imgstream",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "project_id": os.getenv("GOOGLE_CLOUD_PROJECT", "unknown"),
        "timestamp": time.time(),
        "uptime": time.time() - st.session_state.get("app_start_time", time.time()),
        "python_version": os.sys.version.split()[0] if hasattr(os, "sys") else "unknown",
        "platform": os.name,
    }


def perform_health_check() -> dict[str, Any]:
    """Perform comprehensive health check."""
    logger.info("health_check_started")

    start_time = time.time()

    # Initialize app start time if not set
    if "app_start_time" not in st.session_state:
        st.session_state.app_start_time = time.time()

    # Perform individual health checks
    checks = {
        "database": check_database_health(),
        "storage": check_storage_health(),
        "environment": check_environment_health(),
    }

    # Determine overall health status
    overall_status = "healthy"
    unhealthy_services = []

    for service, check_result in checks.items():
        if check_result["status"] != "healthy":
            overall_status = "unhealthy"
            unhealthy_services.append(service)

    # Compile health check response
    health_response = {
        "status": overall_status,
        "timestamp": time.time(),
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "application": get_application_info(),
        "checks": checks,
    }

    if unhealthy_services:
        health_response["unhealthy_services"] = unhealthy_services

    logger.info(
        "health_check_completed",
        status=overall_status,
        duration_ms=health_response["duration_ms"],
        unhealthy_services=unhealthy_services,
    )

    return health_response


def render_health_page() -> None:
    """Render health check page for Streamlit."""
    st.set_page_config(page_title="Health Check - imgstream", page_icon="🏥", layout="wide")

    st.title("🏥 Health Check")
    st.markdown("---")

    # Perform health check
    with st.spinner("Performing health check..."):
        health_data = perform_health_check()

    # Display overall status
    if health_data["status"] == "healthy":
        st.success(f"✅ Application is healthy (checked in {health_data['duration_ms']}ms)")
    else:
        st.error(f"❌ Application is unhealthy (checked in {health_data['duration_ms']}ms)")
        if "unhealthy_services" in health_data:
            st.warning(f"Unhealthy services: {', '.join(health_data['unhealthy_services'])}")

    # Display application info
    st.subheader("📱 Application Information")
    app_info = health_data["application"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Name", app_info["name"])
    with col2:
        st.metric("Version", app_info["version"])
    with col3:
        st.metric("Environment", app_info["environment"])
    with col4:
        st.metric("Uptime", f"{app_info['uptime']:.1f}s")

    # Display individual check results
    st.subheader("🔍 Service Health Checks")

    for service, check_result in health_data["checks"].items():
        with st.expander(f"{service.title()} Service", expanded=check_result["status"] != "healthy"):
            if check_result["status"] == "healthy":
                st.success(f"✅ {check_result['message']}")
            else:
                st.error(f"❌ {check_result['message']}")

            st.json(check_result)

    # Raw health data
    with st.expander("🔧 Raw Health Data"):
        st.json(health_data)

    # Auto-refresh option
    if st.checkbox("Auto-refresh (10s)"):
        time.sleep(10)
        st.rerun()


def health_check_json() -> str:
    """Return health check as JSON string."""
    health_data = perform_health_check()
    return json.dumps(health_data, indent=2)


def check_readiness() -> dict[str, Any]:
    """Perform readiness check for Kubernetes/Cloud Run."""
    try:
        # Quick checks for readiness
        checks = {
            "database": check_database_health(),
            "environment": check_environment_health(),
        }

        # Only check storage if not in development mode
        if os.getenv("ENVIRONMENT") != "dev":
            checks["storage"] = check_storage_health()

        # Determine readiness
        is_ready = all(check["status"] == "healthy" for check in checks.values())

        return {
            "status": "ready" if is_ready else "not_ready",
            "timestamp": time.time(),
            "checks": checks,
        }
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        return {
            "status": "not_ready",
            "timestamp": time.time(),
            "error": str(e),
        }


def check_liveness() -> dict[str, Any]:
    """Perform liveness check for Kubernetes/Cloud Run."""
    try:
        # Basic liveness check - just ensure the app is running
        return {
            "status": "alive",
            "timestamp": time.time(),
            "uptime": time.time() - st.session_state.get("app_start_time", time.time()),
        }
    except Exception as e:
        logger.error("liveness_check_failed", error=str(e))
        return {
            "status": "dead",
            "timestamp": time.time(),
            "error": str(e),
        }


# For direct access via URL parameters
def main() -> None:
    """Main function for health check page."""
    # Check if this is a JSON request
    query_params = st.experimental_get_query_params()

    # Handle different health check endpoints
    endpoint = query_params.get("endpoint", ["health"])[0]
    format_type = query_params.get("format", ["html"])[0]

    if endpoint == "readiness":
        health_data = check_readiness()
    elif endpoint == "liveness":
        health_data = check_liveness()
    else:
        health_data = perform_health_check()

    if format_type == "json":
        # Return JSON response
        st.text(json.dumps(health_data, indent=2))
    else:
        # Render HTML page
        render_health_page()


if __name__ == "__main__":
    main()
