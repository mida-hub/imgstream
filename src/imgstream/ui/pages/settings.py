"""Settings page for imgstream application."""

import streamlit as st

from imgstream.ui.auth_handlers import require_authentication


def render_settings_page() -> None:
    """Render the settings page with organized sections."""
    if not require_authentication():
        return

    # Development notice
    st.info("🚧 設定機能は後のタスクで実装予定です")

    # Settings sections
    st.markdown("### ⚙️ アプリケーション設定")

    # Account settings
    with st.expander("👤 アカウント設定", expanded=True):
        st.markdown("**プロフィール情報**")

        st.text_input("メールアドレス", value=st.session_state.user_email or "", disabled=True)

        st.markdown("**アカウント操作**")
        col1, col2 = st.columns(2)
        with col1:
            st.button("🔄 プロフィール更新", disabled=True)
        with col2:
            st.button("📧 メール設定更新", disabled=True)

    # Display settings
    with st.expander("🎨 表示設定"):
        st.markdown("**外観**")
        st.selectbox("テーマ", ["ライト", "ダーク", "自動"], disabled=True)
        st.selectbox("言語", ["English", "日本語"], disabled=True)

        st.markdown("**ギャラリー表示**")
        st.slider("ページあたりの写真数", 10, 100, 50, disabled=True)
        st.selectbox("デフォルト並び順", ["新しい順", "古い順"], disabled=True)

    # Notification settings
    with st.expander("🔔 通知設定"):
        st.checkbox("アップロード通知を有効化", disabled=True)
        st.checkbox("ストレージアラートを有効化", disabled=True)
        st.checkbox("週次サマリーを有効化", disabled=True)

    # Privacy and security
    with st.expander("🔒 プライバシー & セキュリティ"):
        st.markdown("**データ管理**")
        st.button("📊 マイデータをダウンロード", disabled=True)
        st.button("🗑️ すべての写真を削除", disabled=True, type="secondary")

        st.markdown("**セキュリティ**")
        st.write("認証: Cloud IAP ✅")
        st.write("データ暗号化: 有効 ✅")
        st.write("アクセスログ: 利用可能 ✅")

    # Storage settings
    with st.expander("💾 ストレージ設定"):
        st.markdown("**ストレージ管理**")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("総使用ストレージ", "0 MB")
            st.metric("写真数", "0")
        with col2:
            st.metric("サムネイルストレージ", "0 MB")
            st.metric("オリジナル写真", "0 MB")

        st.markdown("**ライフサイクル設定**")
        st.info("オリジナル写真は30日後に自動的にColdlineストレージに移動してコストを削減します。")

        st.button("🧹 ストレージを最適化", disabled=True)

    # Advanced settings
    with st.expander("🔧 高度な設定"):
        st.markdown("**デバッグ情報**")
        from ...config import get_config

        config = get_config()
        if config.get("debug", False, bool):
            st.json(
                {
                    "user_id": st.session_state.user_id,
                    "authenticated": st.session_state.authenticated,
                    "current_page": st.session_state.current_page,
                    "session_keys": list(st.session_state.keys()),
                }
            )
        else:
            st.info("デバッグモードは無効です")

        st.markdown("**システム情報**")
        st.write("アプリケーションバージョン: 0.1.0")
        st.write("最終更新: 開発ビルド")
        st.write("リージョン: asia-northeast1")
