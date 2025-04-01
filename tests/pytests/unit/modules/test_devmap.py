"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import os.path

import pytest

import salt.modules.devmap as devmap
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {devmap: {}}


def test_multipath_list():
    """
    Test for Device-Mapper Multipath list
    """
    mock = MagicMock(return_value="A")
    with patch.dict(devmap.__salt__, {"cmd.run": mock}):
        assert devmap.multipath_list() == ["A"]


def test_multipath_flush():
    """
    Test for Device-Mapper Multipath flush
    """
    mock = MagicMock(return_value=False)
    with patch.object(os.path, "exists", mock):
        assert devmap.multipath_flush("device") == "device does not exist"

    mock = MagicMock(return_value=True)
    with patch.object(os.path, "exists", mock):
        mock = MagicMock(return_value="A")
        with patch.dict(devmap.__salt__, {"cmd.run": mock}):
            assert devmap.multipath_flush("device") == ["A"]
