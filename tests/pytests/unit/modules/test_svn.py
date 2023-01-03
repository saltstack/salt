"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.svn
"""

import pytest

import salt.modules.svn as svn
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {svn: {}}


def test_info():
    """
    Test to display the Subversion information from the checkout.
    """
    mock = MagicMock(
        side_effect=[
            {"retcode": 0, "stdout": True},
            {"retcode": 0, "stdout": "A\n\nB"},
            {"retcode": 0, "stdout": "A\n\nB"},
        ]
    )
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.info("cwd", fmt="xml")

        assert svn.info("cwd", fmt="list") == [[], []]

        assert svn.info("cwd", fmt="dict") == [{}, {}]


def test_checkout():
    """
    Test to download a working copy of the remote Subversion repository
    directory or file
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": True})
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.checkout("cwd", "remote")


def test_switch():
    """
    Test to switch a working copy of a remote Subversion repository
    directory
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": True})
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.switch("cwd", "remote")


def test_update():
    """
    Test to update the current directory, files, or directories from
    the remote Subversion repository
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": True})
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.update("cwd")


def test_diff():
    """
    Test to return the diff of the current directory, files, or
    directories from the remote Subversion repository
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": True})
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.diff("cwd")


def test_commit():
    """
    Test to commit the current directory, files, or directories to
    the remote Subversion repository
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": True})
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.commit("cwd")


def test_add():
    """
    Test to add files to be tracked by the Subversion working-copy
    checkout
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": True})
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.add("cwd", False)


def test_remove():
    """
    Test to remove files and directories from the Subversion repository
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": True})
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.remove("cwd", False)


def test_status():
    """
    Test to display the status of the current directory, files, or
    directories in the Subversion repository
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": True})
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.status("cwd")


def test_export():
    """
    Test to create an unversioned copy of a tree.
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": True})
    with patch.dict(svn.__salt__, {"cmd.run_all": mock}):
        assert svn.export("cwd", "remote")
