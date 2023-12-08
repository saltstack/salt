"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.rdp
"""


import pytest

import salt.modules.rdp as rdp
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rdp: {}}


# 'enable' function tests: 1


def test_enable():
    """
    Test if it enables RDP the service on the server
    """
    mock = MagicMock(return_value=True)
    with patch.dict(rdp.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.rdp._parse_return_code_powershell", MagicMock(return_value=0)
    ):
        assert rdp.enable()


# 'disable' function tests: 1


def test_disable():
    """
    Test if it disables RDP the service on the server
    """
    mock = MagicMock(return_value=True)
    with patch.dict(rdp.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.rdp._parse_return_code_powershell", MagicMock(return_value=0)
    ):
        assert rdp.disable()


# 'status' function tests: 1


def test_status():
    """
    Test if it shows rdp is enabled on the server
    """
    mock = MagicMock(return_value="1")
    with patch.dict(rdp.__salt__, {"cmd.run": mock}):
        assert rdp.status()
