"""Home page for imgstream application."""

import streamlit as st

from imgstream.ui.components import render_empty_state, render_info_card


def render_home_page() -> None:
    """Render the home page with improved layout and empty states."""
    if not st.session_state.authenticated:
        # Unauthenticated state
        render_empty_state(
            title="認証が必要です",
            description="個人の写真コレクションにアクセスするには、Cloud IAPで認証してください。",
            icon="🔐",
        )

        # Getting started information
        render_info_card(
            "はじめに",
            "このアプリはセキュアな認証にCloud IAPを使用しています。HEICやJPEG写真をアップロードし、"
            "時系列でギャラリーを閲覧し、Google Cloud Storageに安全に保存できます。",
            "🚀",
        )

        # Feature highlights
        col1, col2, col3 = st.columns(3)

        with col1:
            render_info_card(
                "セキュアな認証",
                "Cloud IAPにより、認証されたユーザーのみが写真にアクセスできます。",
                "🔒",
            )

        with col2:
            render_info_card(
                "スマートストレージ",
                "自動ライフサイクル管理により、時間の経過とともにストレージコストを最適化します。",
                "💾",
            )

        with col3:
            render_info_card(
                "高速ブラウジング",
                "サムネイルベースのインターフェースで、写真の素早い発見と閲覧が可能です。",
                "⚡",
            )
    else:
        # Authenticated user dashboard
        user_name = st.session_state.user_name or "ユーザー"
        st.markdown(f"## おかえりなさい、{user_name}さん！ 👋")

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
