"""
Main Streamlit application for imgstream.

This is the entry point for the photo management web application.
"""

import streamlit as st


def main() -> None:
    """Main application entry point."""
    st.set_page_config(
        page_title="imgstream - Photo Management",
        page_icon="📸",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📸 imgstream")
    st.subheader("Personal Photo Management")

    # Placeholder content - will be implemented in later tasks
    st.info("🚧 Application is under development")
    st.write("This is the initial setup of the imgstream application.")


if __name__ == "__main__":
    main()
