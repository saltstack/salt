"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.hadoop
"""

import pytest

import salt.modules.hadoop as hadoop
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {hadoop: {}}


def test_version():
    """
    Test for Return version from hadoop version
    """
    mock = MagicMock(return_value="A \nB \n")
    with patch.dict(hadoop.__salt__, {"cmd.run": mock}):
        assert hadoop.version() == "B"


def test_dfs():
    """
    Test for Execute a command on DFS
    """
    with patch.object(hadoop, "_hadoop_cmd", return_value="A"):
        assert hadoop.dfs("command") == "A"

    assert hadoop.dfs() == "Error: command must be provided"


def test_dfs_present():
    """
    Test for Check if a file or directory is present on the distributed FS.
    """
    with patch.object(
        hadoop, "_hadoop_cmd", side_effect=["No such file or directory", "A"]
    ):
        assert not hadoop.dfs_present("path")
        assert hadoop.dfs_present("path")


def test_dfs_absent():
    """
    Test for Check if a file or directory is absent on the distributed FS.
    """
    with patch.object(
        hadoop, "_hadoop_cmd", side_effect=["No such file or directory", "A"]
    ):
        assert hadoop.dfs_absent("path")
        assert not hadoop.dfs_absent("path")


def test_namenode_format():
    """
    Test for Format a name node
    """
    with patch.object(hadoop, "_hadoop_cmd", return_value="A"):
        assert hadoop.namenode_format("force") == "A"
