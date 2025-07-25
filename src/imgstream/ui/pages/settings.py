"""Settings page for imgstream application."""

import streamlit as st

from imgstream.ui.auth_handlers import require_authentication


def render_settings_page() -> None:
    """Render the settings page with organized sections."""
    if not require_authentication():
        return

    # Development notice
    st.info("🚧 Settings functionality will be implemented in a later task")

    # Settings sections
    st.markdown("### ⚙️ Application Settings")

    # Account settings
    with st.expander("👤 Account Settings", expanded=True):
        st.markdown("**Profile Information**")

        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Display Name", value=st.session_state.user_name or "", disabled=True)
        with col2:
            st.text_input("Email", value=st.session_state.user_email or "", disabled=True)

        st.markdown("**Account Actions**")
        col1, col2 = st.columns(2)
        with col1:
            st.button("🔄 Refresh Profile", disabled=True)
        with col2:
            st.button("📧 Update Email Preferences", disabled=True)

    # Display settings
    with st.expander("🎨 Display Settings"):
        st.markdown("**Appearance**")
        st.selectbox("Theme", ["Light", "Dark", "Auto"], disabled=True)
        st.selectbox("Language", ["English", "日本語"], disabled=True)

        st.markdown("**Gallery View**")
        st.slider("Photos per page", 10, 100, 50, disabled=True)
        st.selectbox("Default sort order", ["Newest First", "Oldest First"], disabled=True)

    # Notification settings
    with st.expander("🔔 Notification Settings"):
        st.checkbox("Enable upload notifications", disabled=True)
        st.checkbox("Enable storage alerts", disabled=True)
        st.checkbox("Enable weekly summary", disabled=True)

    # Privacy and security
    with st.expander("🔒 Privacy & Security"):
        st.markdown("**Data Management**")
        st.button("📊 Download My Data", disabled=True)
        st.button("🗑️ Delete All Photos", disabled=True, type="secondary")

        st.markdown("**Security**")
        st.write("Authentication: Cloud IAP ✅")
        st.write("Data Encryption: Enabled ✅")
        st.write("Access Logs: Available ✅")

    # Storage settings
    with st.expander("💾 Storage Settings"):
        st.markdown("**Storage Management**")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Storage Used", "0 MB")
            st.metric("Number of Photos", "0")
        with col2:
            st.metric("Thumbnail Storage", "0 MB")
            st.metric("Original Photos", "0 MB")

        st.markdown("**Lifecycle Settings**")
        st.info("Original photos automatically move to Coldline storage after 30 days to reduce costs.")

        st.button("🧹 Optimize Storage", disabled=True)

    # Advanced settings
    with st.expander("🔧 Advanced Settings"):
        st.markdown("**Debug Information**")
        if st.secrets.get("debug", False):
            st.json(
                {
                    "user_id": st.session_state.user_id,
                    "authenticated": st.session_state.authenticated,
                    "current_page": st.session_state.current_page,
                    "session_keys": list(st.session_state.keys()),
                }
            )
        else:
            st.info("Debug mode is disabled")

        st.markdown("**System Information**")
        st.write("Application Version: 0.1.0")
        st.write("Last Updated: Development Build")
        st.write("Region: asia-northeast1")
