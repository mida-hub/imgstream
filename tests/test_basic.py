"""
Basic tests to verify test environment setup.
"""

import pytest
from src.imgstream import __version__, __description__


def test_version() -> None:
    """Test that version is defined."""
    assert __version__ == "0.1.0"


def test_description() -> None:
    """Test that description is defined."""
    assert __description__ == "Personal photo management web application with Streamlit"


def test_basic_math() -> None:
    """Basic test to verify pytest is working."""
    assert 1 + 1 == 2


@pytest.mark.unit
def test_unit_marker() -> None:
    """Test that unit marker works."""
    assert True


@pytest.mark.integration
def test_integration_marker() -> None:
    """Test that integration marker works."""
    assert True


def test_sample_fixtures(sample_user_id: str, sample_image_data: bytes) -> None:
    """Test that fixtures are working."""
    assert sample_user_id == "test-user@example.com"
    assert isinstance(sample_image_data, bytes)
    assert len(sample_image_data) > 0
