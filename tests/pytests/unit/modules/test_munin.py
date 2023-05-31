"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.munin as munin
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {munin: {}}


def test_run():
    """
    Test if it runs one or more named munin plugins
    """
    mock = MagicMock(return_value="uptime.value 0.01")
    with patch.dict(munin.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.munin.list_plugins", MagicMock(return_value=["uptime"])
    ):
        assert munin.run("uptime") == {"uptime": {"uptime": 0.01}}


def test_run_all():
    """
    Test if it runs all the munin plugins
    """
    mock = MagicMock(return_value="uptime.value 0.01")
    with patch.dict(munin.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.munin.list_plugins", MagicMock(return_value=["uptime"])
    ):
        assert munin.run_all() == {"uptime": {"uptime": 0.01}}


def test_list_plugins():
    """
    Test if it list all the munin plugins
    """
    with patch("salt.modules.munin.list_plugins", MagicMock(return_value=["uptime"])):
        assert munin.list_plugins() == ["uptime"]
