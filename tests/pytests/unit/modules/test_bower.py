"""
    :codeauthor: Alexander Pyatkin <asp@thexyz.net>
"""


import pytest

import salt.modules.bower as bower
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {bower: {"_check_valid_version": MagicMock(return_value=True)}}


def test_install_with_error():
    """
    Test if it raises an exception when install package fails
    """
    mock = MagicMock(return_value={"retcode": 1, "stderr": "error"})
    with patch.dict(bower.__salt__, {"cmd.run_all": mock}):
        pytest.raises(
            CommandExecutionError, bower.install, "/path/to/project", "underscore"
        )


def test_install_new_package():
    """
    Test if it returns True when install package succeeds
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": '{"underscore":{}}'})
    with patch.dict(bower.__salt__, {"cmd.run_all": mock}):
        assert bower.install("/path/to/project", "underscore")


def test_install_existing_package():
    """
    Test if it returns False when package already installed
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": "{}"})
    with patch.dict(bower.__salt__, {"cmd.run_all": mock}):
        assert not bower.install("/path/to/project", "underscore")


def test_uninstall_with_error():
    """
    Test if it raises an exception when uninstall package fails
    """
    mock = MagicMock(return_value={"retcode": 1, "stderr": "error"})
    with patch.dict(bower.__salt__, {"cmd.run_all": mock}):
        pytest.raises(
            CommandExecutionError, bower.uninstall, "/path/to/project", "underscore"
        )


def test_uninstall_existing_package():
    """
    Test if it returns True when uninstall package succeeds
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": '{"underscore": {}}'})
    with patch.dict(bower.__salt__, {"cmd.run_all": mock}):
        assert bower.uninstall("/path/to/project", "underscore")


def test_uninstall_missing_package():
    """
    Test if it returns False when package is not installed
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": "{}"})
    with patch.dict(bower.__salt__, {"cmd.run_all": mock}):
        assert not bower.uninstall("/path/to/project", "underscore")


def test_list_packages_with_error():
    """
    Test if it raises an exception when list installed packages fails
    """
    mock = MagicMock(return_value={"retcode": 1, "stderr": "error"})
    with patch.dict(bower.__salt__, {"cmd.run_all": mock}):
        pytest.raises(CommandExecutionError, bower.list_, "/path/to/project")


def test_list_packages_success():
    """
    Test if it lists installed Bower packages
    """
    output = '{"dependencies": {"underscore": {}, "jquery":{}}}'
    mock = MagicMock(return_value={"retcode": 0, "stdout": output})
    with patch.dict(bower.__salt__, {"cmd.run_all": mock}):
        assert bower.list_("/path/to/project") == {"underscore": {}, "jquery": {}}
