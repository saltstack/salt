"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.pyenv as pyenv
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pyenv: {}}


def test_install():
    """
    Test if it install pyenv systemwide
    """
    mock_opt = MagicMock(return_value="salt stack")
    mock_ret = MagicMock(return_value=0)
    with patch.dict(
        pyenv.__salt__, {"config.option": mock_opt, "cmd.retcode": mock_ret}
    ):
        assert pyenv.install()


def test_update():
    """
    Test if it updates the current versions of pyenv and python-Build
    """
    mock_opt = MagicMock(return_value="salt stack")
    with patch.dict(pyenv.__salt__, {"config.option": mock_opt}):
        assert not pyenv.update()


def test_is_installed():
    """
    Test if it check if pyenv is installed.
    """
    mock_cmd = MagicMock(return_value=True)
    mock_opt = MagicMock(return_value="salt stack")
    with patch.dict(
        pyenv.__salt__, {"config.option": mock_opt, "cmd.has_exec": mock_cmd}
    ):
        assert pyenv.is_installed()


def test_install_python():
    """
    Test if it install a python implementation.
    """
    mock_opt = MagicMock(return_value="salt stack")
    mock_cmd = MagicMock(return_value=True)
    mock_all = MagicMock(
        return_value={"retcode": 0, "stdout": "salt", "stderr": "error"}
    )
    with patch.dict(pyenv.__grains__, {"os": "Linux"}):
        mock_all = MagicMock(
            return_value={"retcode": 0, "stdout": "salt", "stderr": "error"}
        )
        with patch.dict(
            pyenv.__salt__,
            {
                "config.option": mock_opt,
                "cmd.has_exec": mock_cmd,
                "cmd.run_all": mock_all,
            },
        ):
            assert pyenv.install_python("2.0.0-p0") == "error"

        mock_all = MagicMock(
            return_value={"retcode": True, "stdout": "salt", "stderr": "error"}
        )
        with patch.dict(
            pyenv.__salt__,
            {
                "config.option": mock_opt,
                "cmd.has_exec": mock_cmd,
                "cmd.run_all": mock_all,
            },
        ):
            assert not pyenv.install_python("2.0.0-p0")


def test_uninstall_python():
    """
    Test if it uninstall a python implementation.
    """
    mock_opt = MagicMock(return_value="salt stack")
    mock_cmd = MagicMock(return_value=True)
    mock_all = MagicMock(
        return_value={"retcode": True, "stdout": "salt", "stderr": "error"}
    )
    with patch.dict(
        pyenv.__salt__,
        {
            "cmd.has_exec": mock_cmd,
            "config.option": mock_opt,
            "cmd.run_all": mock_all,
        },
    ):
        assert pyenv.uninstall_python("2.0.0-p0")


def test_versions():
    """
    Test if it list the installed versions of python.
    """
    mock_opt = MagicMock(return_value="salt stack")
    mock_cmd = MagicMock(return_value=True)
    mock_all = MagicMock(
        return_value={"retcode": True, "stdout": "salt", "stderr": "error"}
    )
    with patch.dict(
        pyenv.__salt__,
        {
            "cmd.has_exec": mock_cmd,
            "config.option": mock_opt,
            "cmd.run_all": mock_all,
        },
    ):
        assert pyenv.versions() == []


def test_default():
    """
    Test if it returns or sets the currently defined default python.
    """
    mock_opt = MagicMock(return_value="salt stack")
    mock_cmd = MagicMock(return_value=True)
    mock_all = MagicMock(
        return_value={"retcode": True, "stdout": "salt", "stderr": "error"}
    )
    with patch.dict(
        pyenv.__salt__,
        {
            "cmd.has_exec": mock_cmd,
            "config.option": mock_opt,
            "cmd.run_all": mock_all,
        },
    ):
        assert pyenv.default() == ""
        assert pyenv.default("2.0.0-p0")


def test_list():
    """
    Test if it list the installable versions of python.
    """
    mock_opt = MagicMock(return_value="salt stack")
    mock_cmd = MagicMock(return_value=True)
    mock_all = MagicMock(
        return_value={"retcode": True, "stdout": "salt", "stderr": "error"}
    )
    with patch.dict(
        pyenv.__salt__,
        {
            "cmd.has_exec": mock_cmd,
            "config.option": mock_opt,
            "cmd.run_all": mock_all,
        },
    ):
        assert pyenv.list_() == []


def test_rehash():
    """
    Test if it run pyenv rehash to update the installed shims.
    """
    mock_opt = MagicMock(return_value="salt stack")
    mock_cmd = MagicMock(return_value=True)
    mock_all = MagicMock(
        return_value={"retcode": True, "stdout": "salt", "stderr": "error"}
    )
    with patch.dict(
        pyenv.__salt__,
        {
            "cmd.has_exec": mock_cmd,
            "config.option": mock_opt,
            "cmd.run_all": mock_all,
        },
    ):
        assert pyenv.rehash()


def test_do():
    """
    Test if it execute a python command with pyenv's
    shims from the user or the system.
    """
    mock_opt = MagicMock(return_value="salt stack")
    mock_cmd = MagicMock(return_value=True)
    mock_all = MagicMock(
        return_value={"retcode": True, "stdout": "salt", "stderr": "error"}
    )
    with patch.dict(
        pyenv.__salt__,
        {
            "cmd.has_exec": mock_cmd,
            "config.option": mock_opt,
            "cmd.run_all": mock_all,
        },
    ):
        assert not pyenv.do("gem list bundler")

    mock_all = MagicMock(
        return_value={"retcode": 0, "stdout": "salt", "stderr": "error"}
    )
    with patch.dict(
        pyenv.__salt__,
        {
            "config.option": mock_opt,
            "cmd.has_exec": mock_cmd,
            "cmd.run_all": mock_all,
        },
    ):
        assert pyenv.do("gem list bundler") == "salt"


def test_do_with_python():
    """
    Test if it execute a python command with pyenv's
    shims using a specific python version.
    """
    mock_opt = MagicMock(return_value="salt stack")
    mock_cmd = MagicMock(return_value=True)
    mock_all = MagicMock(
        return_value={"retcode": True, "stdout": "salt", "stderr": "error"}
    )
    with patch.dict(
        pyenv.__salt__,
        {
            "cmd.has_exec": mock_cmd,
            "config.option": mock_opt,
            "cmd.run_all": mock_all,
        },
    ):
        assert not pyenv.do_with_python("2.0.0-p0", "gem list bundler")
