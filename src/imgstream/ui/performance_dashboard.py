"""Performance monitoring dashboard for collision detection."""

import streamlit as st
from datetime import datetime, timedelta
from typing import Any

from ..utils.collision_detection import get_collision_cache_stats, clear_collision_cache
from ..logging_config import get_performance_metrics


def render_performance_dashboard() -> None:
    """
    Render performance monitoring dashboard for collision detection.
    """
    st.title("🚀 Collision Detection Performance Dashboard")
    
    # Cache Statistics Section
    st.header("📊 Cache Statistics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        cache_stats = get_collision_cache_stats()
        
        st.metric(
            "Total Cache Entries",
            cache_stats.get("total_entries", 0),
            help="Total number of cached collision detection results"
        )
        
        st.metric(
            "Valid Entries",
            cache_stats.get("valid_entries", 0),
            help="Number of cache entries that are still valid (not expired)"
        )
        
        st.metric(
            "Expired Entries",
            cache_stats.get("expired_entries", 0),
            help="Number of cache entries that have expired"
        )
        
        st.metric(
            "Cache TTL",
            f"{cache_stats.get('ttl_seconds', 0)}s",
            help="Time-to-live for cache entries in seconds"
        )
    
    with col2:
        # Cache hit rate calculation
        total_entries = cache_stats.get("total_entries", 0)
        valid_entries = cache_stats.get("valid_entries", 0)
        
        if total_entries > 0:
            hit_rate = (valid_entries / total_entries) * 100
            st.metric(
                "Cache Hit Rate",
                f"{hit_rate:.1f}%",
                help="Percentage of cache entries that are still valid"
            )
        else:
            st.metric("Cache Hit Rate", "N/A", help="No cache data available")
        
        # Cache management buttons
        st.subheader("Cache Management")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("🗑️ Clear All Cache", help="Clear all cached collision detection results"):
                clear_collision_cache()
                st.success("All cache cleared successfully!")
                st.rerun()
        
        with col_b:
            user_id = st.text_input("User ID", placeholder="Enter user ID to clear specific cache")
            if st.button("🗑️ Clear User Cache", disabled=not user_id):
                if user_id:
                    clear_collision_cache(user_id)
                    st.success(f"Cache cleared for user: {user_id}")
                    st.rerun()
    
    st.divider()
    
    # Performance Metrics Section
    st.header("⚡ Performance Metrics")
    
    # Mock performance data (in a real implementation, this would come from actual metrics)
    performance_data = _get_mock_performance_data()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Avg Response Time",
            f"{performance_data['avg_response_time']:.3f}s",
            delta=f"{performance_data['response_time_delta']:.3f}s",
            help="Average response time for collision detection"
        )
    
    with col2:
        st.metric(
            "Files/Second",
            f"{performance_data['files_per_second']:.1f}",
            delta=f"{performance_data['throughput_delta']:.1f}",
            help="Average number of files processed per second"
        )
    
    with col3:
        st.metric(
            "Success Rate",
            f"{performance_data['success_rate']:.1f}%",
            delta=f"{performance_data['success_rate_delta']:.1f}%",
            help="Percentage of successful collision detection operations"
        )
    
    # Performance Chart
    st.subheader("📈 Performance Trends")
    
    # Mock chart data
    chart_data = _get_mock_chart_data()
    
    tab1, tab2, tab3 = st.tabs(["Response Time", "Throughput", "Error Rate"])
    
    with tab1:
        st.line_chart(
            chart_data["response_time"],
            use_container_width=True,
            height=300
        )
        st.caption("Response time trend over the last 24 hours")
    
    with tab2:
        st.line_chart(
            chart_data["throughput"],
            use_container_width=True,
            height=300
        )
        st.caption("Files processed per second over the last 24 hours")
    
    with tab3:
        st.line_chart(
            chart_data["error_rate"],
            use_container_width=True,
            height=300
        )
        st.caption("Error rate percentage over the last 24 hours")
    
    st.divider()
    
    # Optimization Recommendations
    st.header("💡 Optimization Recommendations")
    
    recommendations = _get_optimization_recommendations(cache_stats, performance_data)
    
    for recommendation in recommendations:
        if recommendation["type"] == "warning":
            st.warning(f"⚠️ {recommendation['title']}: {recommendation['description']}")
        elif recommendation["type"] == "info":
            st.info(f"💡 {recommendation['title']}: {recommendation['description']}")
        elif recommendation["type"] == "success":
            st.success(f"✅ {recommendation['title']}: {recommendation['description']}")
    
    # System Information
    st.header("🔧 System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Cache Configuration")
        st.code(f"""
Cache TTL: {cache_stats.get('ttl_seconds', 0)} seconds
Max Batch Size: 100 files
Optimization Threshold: 20 files
Fallback Enabled: Yes
        """)
    
    with col2:
        st.subheader("Performance Settings")
        st.code(f"""
Monitoring Enabled: Yes
Performance Logging: Enabled
Cache Enabled: Yes
Batch Processing: Enabled
        """)


def _get_mock_performance_data() -> dict[str, Any]:
    """
    Get mock performance data for demonstration.
    In a real implementation, this would fetch actual metrics.
    """
    import random
    
    return {
        "avg_response_time": 0.045 + random.uniform(-0.01, 0.01),
        "response_time_delta": random.uniform(-0.005, 0.005),
        "files_per_second": 22.5 + random.uniform(-2, 2),
        "throughput_delta": random.uniform(-1, 1),
        "success_rate": 98.5 + random.uniform(-1, 1),
        "success_rate_delta": random.uniform(-0.5, 0.5),
    }


def _get_mock_chart_data() -> dict[str, Any]:
    """
    Get mock chart data for demonstration.
    In a real implementation, this would fetch actual time series data.
    """
    import pandas as pd
    import random
    
    # Generate 24 hours of mock data
    hours = list(range(24))
    
    response_times = [0.045 + random.uniform(-0.01, 0.01) for _ in hours]
    throughput = [22 + random.uniform(-3, 3) for _ in hours]
    error_rates = [1.5 + random.uniform(-0.5, 0.5) for _ in hours]
    
    return {
        "response_time": pd.DataFrame({
            "Response Time (s)": response_times
        }, index=hours),
        "throughput": pd.DataFrame({
            "Files/Second": throughput
        }, index=hours),
        "error_rate": pd.DataFrame({
            "Error Rate (%)": error_rates
        }, index=hours),
    }


def _get_optimization_recommendations(cache_stats: dict, performance_data: dict) -> list[dict]:
    """
    Generate optimization recommendations based on current metrics.
    """
    recommendations = []
    
    # Cache-based recommendations
    total_entries = cache_stats.get("total_entries", 0)
    valid_entries = cache_stats.get("valid_entries", 0)
    expired_entries = cache_stats.get("expired_entries", 0)
    
    if total_entries == 0:
        recommendations.append({
            "type": "info",
            "title": "Cache Not Utilized",
            "description": "Consider enabling caching to improve performance for repeated collision checks."
        })
    elif expired_entries > valid_entries:
        recommendations.append({
            "type": "warning",
            "title": "High Cache Expiration Rate",
            "description": "Consider increasing cache TTL to improve hit rate and reduce database queries."
        })
    elif valid_entries > 100:
        recommendations.append({
            "type": "success",
            "title": "Cache Working Effectively",
            "description": "Cache is being utilized well with good hit rates."
        })
    
    # Performance-based recommendations
    avg_response_time = performance_data.get("avg_response_time", 0)
    files_per_second = performance_data.get("files_per_second", 0)
    success_rate = performance_data.get("success_rate", 100)
    
    if avg_response_time > 0.1:
        recommendations.append({
            "type": "warning",
            "title": "High Response Time",
            "description": "Consider optimizing database queries or increasing batch sizes for better performance."
        })
    elif avg_response_time < 0.05:
        recommendations.append({
            "type": "success",
            "title": "Excellent Response Time",
            "description": "Collision detection is performing very well with low latency."
        })
    
    if files_per_second < 10:
        recommendations.append({
            "type": "warning",
            "title": "Low Throughput",
            "description": "Consider enabling batch processing or optimizing database connections."
        })
    elif files_per_second > 20:
        recommendations.append({
            "type": "success",
            "title": "High Throughput",
            "description": "System is processing files efficiently with good throughput."
        })
    
    if success_rate < 95:
        recommendations.append({
            "type": "warning",
            "title": "Low Success Rate",
            "description": "Investigate error patterns and consider implementing additional error recovery mechanisms."
        })
    elif success_rate > 99:
        recommendations.append({
            "type": "success",
            "title": "Excellent Reliability",
            "description": "Collision detection is highly reliable with minimal errors."
        })
    
    # Default recommendation if no specific issues found
    if not recommendations:
        recommendations.append({
            "type": "info",
            "title": "System Operating Normally",
            "description": "All metrics are within normal ranges. Continue monitoring for any changes."
        })
    
    return recommendations


def render_performance_summary_widget() -> None:
    """
    Render a compact performance summary widget for inclusion in other pages.
    """
    st.sidebar.subheader("🚀 Performance")
    
    cache_stats = get_collision_cache_stats()
    performance_data = _get_mock_performance_data()
    
    # Compact metrics
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        st.metric(
            "Cache Entries",
            cache_stats.get("valid_entries", 0),
            help="Active cache entries"
        )
    
    with col2:
        st.metric(
            "Avg Time",
            f"{performance_data['avg_response_time']:.3f}s",
            help="Average response time"
        )
    
    # Quick actions
    if st.sidebar.button("📊 Full Dashboard", help="Open performance dashboard"):
        st.session_state.show_performance_dashboard = True
    
    if st.sidebar.button("🗑️ Clear Cache", help="Clear collision detection cache"):
        clear_collision_cache()
        st.sidebar.success("Cache cleared!")
