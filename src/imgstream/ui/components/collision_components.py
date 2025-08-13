"""UI components for handling filename collision warnings and user decisions."""

from datetime import datetime
from typing import Any

import streamlit as st
import structlog

from imgstream.ui.components.ui_components import format_file_size

logger = structlog.get_logger()


def render_collision_warnings(collision_results: dict[str, dict[str, Any]]) -> dict[str, str]:
    """
    Render collision warnings and collect user decisions.

    Args:
        collision_results: Dictionary mapping filename to collision info

    Returns:
        dict: Dictionary mapping filename to user decision ("overwrite", "skip", or "pending")
    """
    if not collision_results:
        return {}

    logger.info("rendering_collision_warnings", collision_count=len(collision_results))

    user_decisions = {}

    # Header section
    st.markdown("### ⚠️ ファイル名の衝突が検出されました")
    st.markdown(
        "以下のファイルは既にアップロード済みです。各ファイルについて、上書きするかスキップするかを選択してください。"
    )

    # Summary information
    with st.expander("📊 衝突の概要", expanded=False):
        st.info(f"合計 {len(collision_results)} 件のファイル名衝突が検出されました。")

        # Show list of conflicting files
        st.markdown("**衝突ファイル一覧:**")
        for filename in collision_results.keys():
            st.write(f"• {filename}")

    st.divider()

    # Individual collision handling
    for i, (filename, collision_info) in enumerate(collision_results.items(), 1):
        existing_file_info = collision_info["existing_file_info"]

        # Create a container for each collision with better styling
        with st.container():
            # File header with number
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"#### {i}. 📷 {filename}")
            with col2:
                # Show current decision status
                current_decision = collision_info.get("user_decision", "pending")
                if current_decision == "overwrite":
                    st.success("✅ 上書き")
                elif current_decision == "skip":
                    st.error("❌ スキップ")
                else:
                    st.warning("⏳ 決定待ち")

            # Existing file information in a nice layout
            st.markdown("**既存ファイルの情報:**")

            info_col1, info_col2, info_col3 = st.columns(3)

            with info_col1:
                st.metric(
                    "ファイルサイズ", format_file_size(existing_file_info["file_size"]), help="既存ファイルのサイズ"
                )

            with info_col2:
                upload_date = existing_file_info["upload_date"]
                if isinstance(upload_date, datetime):
                    date_str = upload_date.strftime("%Y-%m-%d")
                    time_str = upload_date.strftime("%H:%M")
                else:
                    date_str = str(upload_date)
                    time_str = ""

                st.metric(
                    "アップロード日",
                    date_str,
                    delta=time_str if time_str else None,
                    help="既存ファイルがアップロードされた日時",
                )

            with info_col3:
                creation_date = existing_file_info.get("creation_date")
                if creation_date and isinstance(creation_date, datetime):
                    creation_str = creation_date.strftime("%Y-%m-%d")
                    st.metric("作成日", creation_str, help="写真が撮影された日付")
                else:
                    st.metric("作成日", "不明", help="写真の撮影日が不明です")

            # Decision selection with better UX
            st.markdown("**選択してください:**")

            decision_col1, decision_col2, decision_col3 = st.columns([1, 1, 2])

            decision_key = f"collision_decision_{filename}_{i}"

            with decision_col1:
                if st.button(
                    "🔄 上書きする",
                    key=f"overwrite_{decision_key}",
                    help="既存ファイルを新しいファイルで置き換えます",
                    use_container_width=True,
                    type="primary" if current_decision == "overwrite" else "secondary",
                ):
                    user_decisions[filename] = "overwrite"
                    # Update session state to persist decision
                    st.session_state[f"decision_{filename}"] = "overwrite"
                    st.rerun()

            with decision_col2:
                if st.button(
                    "⏭️ スキップする",
                    key=f"skip_{decision_key}",
                    help="このファイルをアップロードせず、既存ファイルを保持します",
                    use_container_width=True,
                    type="primary" if current_decision == "skip" else "secondary",
                ):
                    user_decisions[filename] = "skip"
                    # Update session state to persist decision
                    st.session_state[f"decision_{filename}"] = "skip"
                    st.rerun()

            with decision_col3:
                # Show additional information based on decision
                if current_decision == "overwrite":
                    st.warning("⚠️ 既存ファイルは完全に置き換えられます")
                elif current_decision == "skip":
                    st.info("ℹ️ このファイルはアップロードされません")
                else:
                    st.info("👆 上記のボタンから選択してください")

            # Check session state for persisted decisions
            session_decision = st.session_state.get(f"decision_{filename}")
            if session_decision:
                user_decisions[filename] = session_decision

            st.divider()

    # Summary of decisions
    if user_decisions:
        _render_decision_summary(user_decisions, collision_results)

    logger.info("collision_warnings_rendered", decisions_made=len(user_decisions))
    return user_decisions


def _render_decision_summary(user_decisions: dict[str, str], collision_results: dict[str, dict[str, Any]]) -> None:
    """
    Render a summary of user decisions.

    Args:
        user_decisions: Dictionary mapping filename to user decision
        collision_results: Original collision results
    """
    st.markdown("### 📋 決定の概要")

    overwrite_count = sum(1 for decision in user_decisions.values() if decision == "overwrite")
    skip_count = sum(1 for decision in user_decisions.values() if decision == "skip")
    pending_count = len(collision_results) - len(user_decisions)

    summary_col1, summary_col2, summary_col3 = st.columns(3)

    with summary_col1:
        st.metric(
            "上書き",
            overwrite_count,
            delta=f"{overwrite_count}/{len(collision_results)}" if overwrite_count > 0 else None,
            help="上書きを選択したファイル数",
        )

    with summary_col2:
        st.metric(
            "スキップ",
            skip_count,
            delta=f"{skip_count}/{len(collision_results)}" if skip_count > 0 else None,
            help="スキップを選択したファイル数",
        )

    with summary_col3:
        st.metric(
            "決定待ち",
            pending_count,
            delta="要決定" if pending_count > 0 else "完了",
            help="まだ決定していないファイル数",
        )

    # Show detailed list if there are decisions
    if user_decisions:
        with st.expander("📝 決定の詳細", expanded=False):
            for filename, decision in user_decisions.items():
                decision_icon = "🔄" if decision == "overwrite" else "⏭️"
                decision_text = "上書き" if decision == "overwrite" else "スキップ"
                st.write(f"{decision_icon} **{filename}** → {decision_text}")


def render_collision_status_indicator(
    collision_results: dict[str, dict[str, Any]], user_decisions: dict[str, str]
) -> None:
    """
    Render a status indicator showing the current state of collision resolution.

    Args:
        collision_results: Dictionary mapping filename to collision info
        user_decisions: Dictionary mapping filename to user decision
    """
    if not collision_results:
        return

    total_collisions = len(collision_results)
    decisions_made = len(user_decisions)
    pending_decisions = total_collisions - decisions_made

    # Create status indicator
    if pending_decisions == 0:
        st.success(f"✅ すべての衝突について決定が完了しました ({total_collisions}/{total_collisions})")
    elif decisions_made > 0:
        st.info(f"⏳ 進行中: {decisions_made}/{total_collisions} 件の決定が完了")
    else:
        st.warning(f"⚠️ {total_collisions} 件の衝突について決定が必要です")

    # Progress bar
    if total_collisions > 0:
        progress = decisions_made / total_collisions
        st.progress(progress, text=f"決定進捗: {decisions_made}/{total_collisions}")


def render_collision_help_section() -> None:
    """Render a help section explaining collision handling options."""
    with st.expander("❓ ファイル名衝突について", expanded=False):
        st.markdown(
            """
        **ファイル名衝突とは？**

        同じ名前のファイルが既にアップロード済みの場合に発生します。

        **選択肢の説明:**

        🔄 **上書きする**
        - 既存のファイルを新しいファイルで完全に置き換えます
        - 既存ファイルは削除され、復元できません
        - アップロード日時は更新されますが、写真IDは保持されます

        ⏭️ **スキップする**
        - 新しいファイルはアップロードされません
        - 既存のファイルはそのまま保持されます
        - 他のファイルのアップロードには影響しません

        **推奨事項:**
        - 同じ写真の異なるバージョンの場合は「上書き」を選択
        - 異なる写真で偶然同じ名前の場合は、ファイル名を変更してから再アップロード
        - 不明な場合は「スキップ」を選択して安全を確保
        """
        )


def clear_collision_decisions(collision_results: dict[str, dict[str, Any]]) -> None:
    """
    Clear all collision decisions from session state.

    Args:
        collision_results: Dictionary mapping filename to collision info
    """
    for filename in collision_results.keys():
        decision_key = f"decision_{filename}"
        if decision_key in st.session_state:
            del st.session_state[decision_key]

    logger.info("collision_decisions_cleared", collision_count=len(collision_results))


def get_collision_decisions_from_session(collision_results: dict[str, dict[str, Any]]) -> dict[str, str]:
    """
    Retrieve collision decisions from session state.

    Args:
        collision_results: Dictionary mapping filename to collision info

    Returns:
        dict: Dictionary mapping filename to user decision
    """
    decisions = {}

    for filename in collision_results.keys():
        decision_key = f"decision_{filename}"
        if decision_key in st.session_state:
            decisions[filename] = st.session_state[decision_key]

    return decisions


def validate_collision_decisions(
    collision_results: dict[str, dict[str, Any]], user_decisions: dict[str, str]
) -> tuple[bool, list[str]]:
    """
    Validate that all required collision decisions have been made.

    Args:
        collision_results: Dictionary mapping filename to collision info
        user_decisions: Dictionary mapping filename to user decision

    Returns:
        tuple: (all_decisions_made, list_of_pending_files)
    """
    pending_files = []

    for filename in collision_results.keys():
        if filename not in user_decisions or user_decisions[filename] == "pending":
            pending_files.append(filename)

    all_decisions_made = len(pending_files) == 0

    logger.info(
        "collision_decisions_validated",
        total_collisions=len(collision_results),
        decisions_made=len(user_decisions),
        pending_files=len(pending_files),
        all_complete=all_decisions_made,
    )

    return all_decisions_made, pending_files
