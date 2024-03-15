"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.logadm
"""

import pytest

import salt.modules.logadm as logadm
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {logadm: {}}


def test_show_conf():
    """
    Test for Show parsed configuration
    """
    with patch.object(logadm, "_parse_conf", return_value=True):
        assert logadm.show_conf("conf_file")


def test_rotate():
    """
    Test for Set up pattern for logging.
    """
    with patch.dict(
        logadm.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 1, "stderr": "stderr"})},
    ):
        assert logadm.rotate("name") == {
            "Output": "stderr",
            "Error": "Failed in adding log",
        }

    with patch.dict(
        logadm.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stderr": "stderr"})},
    ):
        assert logadm.rotate("name") == {"Result": "Success"}


def test_remove():
    """
    Test for Remove log pattern from logadm
    """
    with patch.dict(
        logadm.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 1, "stderr": "stderr"})},
    ):
        assert logadm.remove("name") == {
            "Output": "stderr",
            "Error": "Failure in removing log. Possibly already removed?",
        }

    with patch.dict(
        logadm.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stderr": "stderr"})},
    ):
        assert logadm.remove("name") == {"Result": "Success"}
