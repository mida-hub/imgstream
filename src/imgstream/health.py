"""
Health check endpoints for imgstream application.

This module provides health check functionality for monitoring and deployment.
"""

import json
import os
import time
from typing import Dict, Any

import streamlit as st
from google.cloud import storage
import duckdb

from imgstream.logging_config import get_logger

logger = get_logger(__name__)


def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and health."""
    try:
        # Test DuckDB connection
        conn = duckdb.connect(":memory:")
        conn.execute("SELECT 1")
        conn.close()
        
        return {
            "status": "healthy",
            "message": "Database connection successful",
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
            "timestamp": time.time()
        }


def check_storage_health() -> Dict[str, Any]:
    """Check Google Cloud Storage connectivity."""
    try:
        # Initialize storage client
        client = storage.Client()
        
        # Try to list buckets (minimal operation)
        list(client.list_buckets(max_results=1))
        
        return {
            "status": "healthy",
            "message": "Storage connection successful",
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error("storage_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "message": f"Storage connection failed: {str(e)}",
            "timestamp": time.time()
        }


def check_environment_health() -> Dict[str, Any]:
    """Check environment configuration."""
    try:
        required_env_vars = [
            "GOOGLE_CLOUD_PROJECT",
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            return {
                "status": "unhealthy",
                "message": f"Missing environment variables: {', '.join(missing_vars)}",
                "timestamp": time.time()
            }
        
        return {
            "status": "healthy",
            "message": "Environment configuration is valid",
            "timestamp": time.time(),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "project_id": os.getenv("GOOGLE_CLOUD_PROJECT", "unknown")
        }
    except Exception as e:
        logger.error("environment_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "message": f"Environment check failed: {str(e)}",
            "timestamp": time.time()
        }


def get_application_info() -> Dict[str, Any]:
    """Get application information."""
    return {
        "name": "imgstream",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "project_id": os.getenv("GOOGLE_CLOUD_PROJECT", "unknown"),
        "timestamp": time.time(),
        "uptime": time.time() - st.session_state.get("app_start_time", time.time())
    }


def perform_health_check() -> Dict[str, Any]:
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
        "environment": check_environment_health()
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
        "checks": checks
    }
    
    if unhealthy_services:
        health_response["unhealthy_services"] = unhealthy_services
    
    logger.info(
        "health_check_completed",
        status=overall_status,
        duration_ms=health_response["duration_ms"],
        unhealthy_services=unhealthy_services
    )
    
    return health_response


def render_health_page() -> None:
    """Render health check page for Streamlit."""
    st.set_page_config(
        page_title="Health Check - imgstream",
        page_icon="🏥",
        layout="wide"
    )
    
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


# For direct access via URL parameters
def main():
    """Main function for health check page."""
    # Check if this is a JSON request
    query_params = st.experimental_get_query_params()
    
    if query_params.get("format") == ["json"]:
        # Return JSON response
        st.text(health_check_json())
    else:
        # Render HTML page
        render_health_page()


if __name__ == "__main__":
    main()
