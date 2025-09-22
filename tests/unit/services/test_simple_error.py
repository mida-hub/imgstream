
import pytest
import os
import sys
from unittest.mock import MagicMock

from src.imgstream.ui.handlers.error import ImageProcessingError

@pytest.fixture
def setup_streamlit_mock():
    original_environment = os.environ.get("ENVIRONMENT")
    original_streamlit = sys.modules.get("streamlit")

    os.environ["ENVIRONMENT"] = "test"
    streamlit_mock = MagicMock()
    streamlit_mock.secrets = {"gcp_service_account": {"type": "service_account"}}
    sys.modules["streamlit"] = streamlit_mock

    yield

    if original_environment is not None:
        os.environ["ENVIRONMENT"] = original_environment
    else:
        del os.environ["ENVIRONMENT"]

    if original_streamlit is not None:
        sys.modules["streamlit"] = original_streamlit
    else:
        del sys.modules["streamlit"]

def test_simple_image_processing_error(setup_streamlit_mock):
    with pytest.raises(ImageProcessingError):
        raise ImageProcessingError("Test error")
