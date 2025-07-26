"""
Health check page for Streamlit application.

This page provides health check functionality accessible via /_stcore/health
"""

from src.imgstream.health import render_health_page

if __name__ == "__main__":
    render_health_page()
