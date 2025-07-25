"""Home page for imgstream application."""

import streamlit as st

from imgstream.ui.components import render_empty_state, render_info_card


def render_home_page() -> None:
    """Render the home page with improved layout and empty states."""
    if not st.session_state.authenticated:
        # Unauthenticated state
        render_empty_state(
            title="Authentication Required",
            description="Please authenticate with Cloud IAP to access your personal photo collection.",
            icon="🔐",
        )

        # Getting started information
        render_info_card(
            "Getting Started",
            "This app uses Cloud IAP for secure authentication. Upload HEIC and JPEG photos, "
            "browse your gallery in chronological order, and store photos securely in Google Cloud Storage.",
            "🚀",
        )

        # Feature highlights
        col1, col2, col3 = st.columns(3)

        with col1:
            render_info_card(
                "Secure Authentication",
                "Cloud IAP ensures only authorized users can access their photos.",
                "🔒",
            )

        with col2:
            render_info_card(
                "Smart Storage",
                "Automatic lifecycle management optimizes storage costs over time.",
                "💾",
            )

        with col3:
            render_info_card(
                "Fast Browsing",
                "Thumbnail-based interface for quick photo discovery and viewing.",
                "⚡",
            )
    else:
        # Authenticated user dashboard
        user_name = st.session_state.user_name or "User"
        st.markdown(f"## Welcome back, {user_name}! 👋")

        # Quick stats dashboard
        st.markdown("### 📊 Your Photo Library")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Photos", "0", help="Total number of uploaded photos")
        with col2:
            st.metric("Storage Used", "0 MB", help="Total storage space used")
        with col3:
            st.metric("Recent Uploads", "0", help="Photos uploaded this week")
        with col4:
            st.metric("Last Activity", "Never", help="Last time you uploaded photos")

        st.divider()

        # Quick actions section
        st.markdown("### ⚡ Quick Actions")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📤 Upload New Photos", use_container_width=True, type="primary"):
                st.session_state.current_page = "upload"
                st.rerun()

        with col2:
            if st.button("🖼️ Browse Gallery", use_container_width=True):
                st.session_state.current_page = "gallery"
                st.rerun()

        with col3:
            if st.button("⚙️ Manage Settings", use_container_width=True):
                st.session_state.current_page = "settings"
                st.rerun()

        st.divider()

        # Recent activity section (empty state for now)
        st.markdown("### 📅 Recent Activity")
        render_empty_state(
            title="No Recent Activity",
            description="Your recent photo uploads and activities will appear here.",
            icon="📭",
            action_text="Upload Your First Photo",
            action_page="upload",
        )
