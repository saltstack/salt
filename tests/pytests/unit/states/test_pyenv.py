"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.pyenv as pyenv
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pyenv: {}}


def test_installed():
    """
    Test to verify that the specified python is installed with pyenv.
    """
    name = "python-2.7.6"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    with patch.dict(pyenv.__opts__, {"test": True}):
        comt = "python 2.7.6 is set to be installed"
        ret.update({"comment": comt})
        assert pyenv.installed(name) == ret

    with patch.dict(pyenv.__opts__, {"test": False}):
        mock_f = MagicMock(side_effect=[False, False, True])
        mock_fa = MagicMock(side_effect=[False, True])
        mock_str = MagicMock(return_value="2.7.6")
        mock_lst = MagicMock(return_value=["2.7.6"])
        with patch.dict(
            pyenv.__salt__,
            {
                "pyenv.is_installed": mock_f,
                "pyenv.install": mock_fa,
                "pyenv.default": mock_str,
                "pyenv.versions": mock_lst,
            },
        ):
            comt = "pyenv failed to install"
            ret.update({"comment": comt, "result": False})
            assert pyenv.installed(name) == ret

            comt = "Requested python exists."
            ret.update({"comment": comt, "result": True, "default": True})
            assert pyenv.installed(name) == ret

            assert pyenv.installed(name) == ret


def test_absent():
    """
    Test to verify that the specified python is not installed with pyenv.
    """
    name = "python-2.7.6"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    with patch.dict(pyenv.__opts__, {"test": True}):
        comt = "python 2.7.6 is set to be uninstalled"
        ret.update({"comment": comt})
        assert pyenv.absent(name) == ret

    with patch.dict(pyenv.__opts__, {"test": False}):
        mock_f = MagicMock(side_effect=[False, True])
        mock_t = MagicMock(return_value=True)
        mock_str = MagicMock(return_value="2.7.6")
        mock_lst = MagicMock(return_value=["2.7.6"])
        with patch.dict(
            pyenv.__salt__,
            {
                "pyenv.is_installed": mock_f,
                "pyenv.uninstall_python": mock_t,
                "pyenv.default": mock_str,
                "pyenv.versions": mock_lst,
            },
        ):
            comt = "pyenv not installed, 2.7.6 not either"
            ret.update({"comment": comt, "result": True})
            assert pyenv.absent(name) == ret

            comt = "Successfully removed python"
            ret.update(
                {
                    "comment": comt,
                    "result": True,
                    "default": True,
                    "changes": {"2.7.6": "Uninstalled"},
                }
            )
            assert pyenv.absent(name) == ret


def test_install_pyenv():
    """
    Test to install pyenv if not installed.
    """
    name = "python-2.7.6"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    with patch.dict(pyenv.__opts__, {"test": True}):
        comt = "pyenv is set to be installed"
        ret.update({"comment": comt})
        assert pyenv.install_pyenv(name) == ret

    with patch.dict(pyenv.__opts__, {"test": False}):
        mock_t = MagicMock(return_value=True)
        mock_str = MagicMock(return_value="2.7.6")
        mock_lst = MagicMock(return_value=["2.7.6"])
        with patch.dict(
            pyenv.__salt__,
            {
                "pyenv.install_python": mock_t,
                "pyenv.default": mock_str,
                "pyenv.versions": mock_lst,
            },
        ):
            comt = "Successfully installed python"
            ret.update(
                {
                    "comment": comt,
                    "result": True,
                    "default": False,
                    "changes": {None: "Installed"},
                }
            )
            assert pyenv.install_pyenv(name) == ret
