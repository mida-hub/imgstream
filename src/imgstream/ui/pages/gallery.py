"""Gallery page for imgstream application."""

import streamlit as st

from imgstream.ui.auth_handlers import require_authentication
from imgstream.ui.components import render_empty_state


def render_gallery_page() -> None:
    """Render the gallery page with empty state and layout."""
    if not require_authentication():
        return

    # Gallery controls
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown("### 🖼️ Your Photo Collection")

    with col2:
        st.selectbox("View", ["Grid", "List"], disabled=True)

    with col3:
        st.selectbox("Sort by", ["Newest First", "Oldest First"], disabled=True)

    st.divider()

    # Development notice
    st.info("🚧 Gallery functionality will be implemented in a later task")

    # Empty state for photos
    render_empty_state(
        title="No Photos Yet",
        description="Your photo collection is empty. Upload some photos to get started!",
        icon="📷",
        action_text="Upload Photos",
        action_page="upload",
    )

    # Placeholder for future gallery features
    with st.expander("🔮 Coming Soon"):
        st.markdown(
            """
        **Gallery Features in Development:**

        - 📅 **Chronological View**: Photos sorted by creation date
        - 🔍 **Search & Filter**: Find photos by date, name, or metadata
        - 🖼️ **Thumbnail Grid**: Fast browsing with optimized thumbnails
        - 🔍 **Full-Size Preview**: Click to view original images
        - 📱 **Responsive Layout**: Works on desktop and mobile
        - 🏷️ **Smart Organization**: Automatic grouping by date and location
        """
        )
