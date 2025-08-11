"""Home page for imgstream application."""

import streamlit as st

from imgstream.ui.components import render_empty_state, render_info_card


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
        # Authenticated user dashboard
        user_email = st.session_state.user_email or "unknown@example.com"
        # Extract name part from email for greeting (before @)
        display_name = user_email.split("@")[0] if "@" in user_email else "ユーザー"
        st.markdown(f"## おかえりなさい、{display_name}さん！ 👋")

        # Quick stats dashboard
        st.markdown("### 📊 あなたの写真ライブラリ")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("総写真数", "0", help="アップロードされた写真の総数")
        with col2:
            st.metric("使用ストレージ", "0 MB", help="使用している総ストレージ容量")
        with col3:
            st.metric("最近のアップロード", "0", help="今週アップロードされた写真数")
        with col4:
            st.metric("最終活動", "なし", help="最後に写真をアップロードした時刻")

        st.divider()

        # Quick actions section
        st.markdown("### ⚡ クイックアクション")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📤 新しい写真をアップロード", use_container_width=True, type="primary"):
                st.session_state.current_page = "upload"
                st.rerun()

        with col2:
            if st.button("🖼️ ギャラリーを閲覧", use_container_width=True):
                st.session_state.current_page = "gallery"
                st.rerun()

        with col3:
            if st.button("⚙️ 設定を管理", use_container_width=True):
                st.session_state.current_page = "settings"
                st.rerun()

        st.divider()

        # Recent activity section (empty state for now)
        st.markdown("### 📅 最近の活動")
        render_empty_state(
            title="最近の活動はありません",
            description="最近の写真アップロードと活動がここに表示されます。",
            icon="📭",
            action_text="最初の写真をアップロード",
            action_page="upload",
        )
