"""Home page for imgstream application."""

import streamlit as st

from imgstream.ui.components.ui_components import render_empty_state, render_info_card


def render_home_page() -> None:
    """Render the home page with improved layout and empty states."""
    if not st.session_state.authenticated:
        # Unauthenticated state
        render_empty_state(
            title="認証が必要です",
            description="未認証状態のため認証してください",
            icon="🔐",
        )

        # Getting started information
        render_info_card(
            "はじめに",
            "このアプリはセキュアな認証で保護されています。写真をアップロードすると、"
            "時系列でギャラリーを閲覧することができます。画像はクラウドに安全に保存されます。",
            "🚀",
        )

    else:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📤 新しい写真をアップロード", use_container_width=True, type="primary"):
                st.session_state.current_page = "upload"
                st.rerun()

        with col2:
            if st.button("🖼️ ギャラリーを閲覧", use_container_width=True):
                st.session_state.current_page = "gallery"
                st.rerun()
