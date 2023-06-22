"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.pam
"""
import pytest

import salt.modules.pam as pam
from tests.support.mock import mock_open, patch


@pytest.fixture
def MOCK_FILE():
    return "ok ok ignore"


@pytest.fixture
def configure_loader_modules():
    return {pam: {}}


def test_read_file(MOCK_FILE):
    """
    Test if the parsing function works
    """
    with patch("os.path.exists", return_value=True), patch(
        "salt.utils.files.fopen", mock_open(read_data=MOCK_FILE)
    ):
        assert pam.read_file("/etc/pam.d/login") == [
            {
                "arguments": [],
                "control_flag": "ok",
                "interface": "ok",
                "module": "ignore",
            }
        ]
