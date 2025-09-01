"""Configuration for UI unit tests."""

import pytest
import streamlit as st
from unittest.mock import patch


@pytest.fixture(autouse=True)
def disable_streamlit_caching():
    """Fixture to disable streamlit caching for all tests in this module."""
    st.cache_data.clear()
    st.cache_resource.clear()
    with patch("streamlit.cache_data", new=lambda *args, **kwargs: lambda f: f), \
         patch("streamlit.cache_resource", new=lambda *args, **kwargs: lambda f: f):
        yield