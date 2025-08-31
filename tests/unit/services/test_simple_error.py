
import pytest
import os
import sys
from unittest.mock import MagicMock

# Mock streamlit module completely to avoid protobuf issues
os.environ["ENVIRONMENT"] = "test"
streamlit_mock = MagicMock()
streamlit_mock.secrets = {"gcp_service_account": {"type": "service_account"}}
sys.modules["streamlit"] = streamlit_mock

from src.imgstream.ui.handlers.error import ImageProcessingError

def test_simple_image_processing_error():
    with pytest.raises(ImageProcessingError):
        raise ImageProcessingError("Test error")
