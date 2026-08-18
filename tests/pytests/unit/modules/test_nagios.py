"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.nagios
"""

import os

import pytest

import salt.modules.nagios as nagios
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {nagios: {}}


def test_run():
    """
    Test for Run nagios plugin and return all
     the data execution with cmd.run
    """
    with patch.object(nagios, "_execute_cmd", return_value="A"):
        assert nagios.run("plugin") == "A"


def test_retcode():
    """
    Test for Run one nagios plugin and return retcode of the execution
    """
    with patch.object(nagios, "_execute_cmd", return_value="A"):
        assert nagios.retcode("plugin", key_name="key") == {"key": {"status": "A"}}


def test_run_all():
    """
    Test for Run nagios plugin and return all
     the data execution with cmd.run_all
    """
    with patch.object(nagios, "_execute_cmd", return_value="A"):
        assert nagios.run_all("plugin") == "A"


def test_retcode_pillar():
    """
    Test for Run one or more nagios plugins from pillar data and
     get the result of cmd.retcode
    """
    with patch.dict(nagios.__salt__, {"pillar.get": MagicMock(return_value={})}):
        assert nagios.retcode_pillar("pillar_name") == {}


def test_run_pillar():
    """
    Test for Run one or more nagios plugins from pillar data
     and get the result of cmd.run
    """
    with patch.object(nagios, "_execute_pillar", return_value="A"):
        assert nagios.run_pillar("pillar") == "A"


def test_run_all_pillar():
    """
    Test for Run one or more nagios plugins from pillar data
     and get the result of cmd.run
    """
    with patch.object(nagios, "_execute_pillar", return_value="A"):
        assert nagios.run_all_pillar("pillar") == "A"


def test_list_plugins():
    """
    Test for List all the nagios plugins
    """
    with patch.object(os, "listdir", return_value=[]):
        assert nagios.list_plugins() == []
