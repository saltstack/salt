"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.rbenv as rbenv
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rbenv: {}}


def test_installed():
    """
    Test to verify that the specified ruby is installed with rbenv.
    """
    # rbenv.is_installed is used wherever test is False.
    mock_is = MagicMock(side_effect=[False, True, True, True, True])

    # rbenv.install is only called when an action is attempted
    # (ie. Successfully... or Failed...)
    mock_i = MagicMock(side_effect=[False, False, False])

    # rbenv.install_ruby is only called when rbenv is successfully
    # installed and an attempt to install a version of Ruby is
    # made.
    mock_ir = MagicMock(side_effect=[True, False])
    mock_def = MagicMock(return_value="2.3.4")
    mock_ver = MagicMock(return_value=["2.3.4", "2.4.1"])
    with patch.dict(
        rbenv.__salt__,
        {
            "rbenv.is_installed": mock_is,
            "rbenv.install": mock_i,
            "rbenv.default": mock_def,
            "rbenv.versions": mock_ver,
            "rbenv.install_ruby": mock_ir,
        },
    ):
        with patch.dict(rbenv.__opts__, {"test": True}):
            name = "1.9.3-p551"
            comt = "Ruby {} is set to be installed".format(name)
            ret = {"name": name, "changes": {}, "comment": comt, "result": None}
            assert rbenv.installed(name) == ret

            name = "2.4.1"
            comt = "Ruby {} is already installed".format(name)
            ret = {
                "name": name,
                "changes": {},
                "comment": comt,
                "default": False,
                "result": True,
            }
            assert rbenv.installed(name) == ret

            name = "2.3.4"
            comt = "Ruby {} is already installed".format(name)
            ret = {
                "name": name,
                "changes": {},
                "comment": comt,
                "default": True,
                "result": True,
            }
            assert rbenv.installed(name) == ret

        with patch.dict(rbenv.__opts__, {"test": False}):
            name = "2.4.1"
            comt = "Rbenv failed to install"
            ret = {"name": name, "changes": {}, "comment": comt, "result": False}
            assert rbenv.installed(name) == ret

            comt = "Requested ruby exists"
            ret = {
                "name": name,
                "comment": comt,
                "default": False,
                "changes": {},
                "result": True,
            }
            assert rbenv.installed(name) == ret

            name = "2.3.4"
            comt = "Requested ruby exists"
            ret = {
                "name": name,
                "comment": comt,
                "default": True,
                "changes": {},
                "result": True,
            }
            assert rbenv.installed(name) == ret

            name = "1.9.3-p551"
            comt = "Successfully installed ruby"
            ret = {
                "name": name,
                "comment": comt,
                "default": False,
                "changes": {name: "Installed"},
                "result": True,
            }
            assert rbenv.installed(name) == ret

            comt = "Failed to install ruby"
            ret = {"name": name, "comment": comt, "changes": {}, "result": False}
            assert rbenv.installed(name) == ret


def test_absent():
    """
    Test to verify that the specified ruby is not installed with rbenv.
    """
    # rbenv.is_installed is used for all tests here.
    mock_is = MagicMock(
        side_effect=[False, True, True, True, False, True, True, True, True, True]
    )
    # rbenv.uninstall_ruby is only called when an action is
    # attempted (ie. Successfully... or Failed...)
    mock_uninstalled = MagicMock(side_effect=[True, False, False, True])
    mock_def = MagicMock(return_value="2.3.4")
    mock_ver = MagicMock(return_value=["2.3.4", "2.4.1"])
    with patch.dict(
        rbenv.__salt__,
        {
            "rbenv.is_installed": mock_is,
            "rbenv.default": mock_def,
            "rbenv.versions": mock_ver,
            "rbenv.uninstall_ruby": mock_uninstalled,
        },
    ):

        with patch.dict(rbenv.__opts__, {"test": True}):
            name = "1.9.3-p551"
            comt = "Rbenv not installed, {} not either".format(name)
            ret = {"name": name, "changes": {}, "comment": comt, "result": True}
            assert rbenv.absent(name) == ret

            comt = "Ruby {} is already uninstalled".format(name)
            ret = {"name": name, "changes": {}, "comment": comt, "result": True}
            assert rbenv.absent(name) == ret

            name = "2.3.4"
            comt = "Ruby {} is set to be uninstalled".format(name)
            ret = {
                "name": name,
                "changes": {},
                "comment": comt,
                "default": True,
                "result": None,
            }
            assert rbenv.absent("2.3.4") == ret

            name = "2.4.1"
            comt = "Ruby {} is set to be uninstalled".format(name)
            ret = {
                "name": name,
                "changes": {},
                "comment": comt,
                "default": False,
                "result": None,
            }
            assert rbenv.absent("2.4.1") == ret

        with patch.dict(rbenv.__opts__, {"test": False}):
            name = "1.9.3-p551"
            comt = "Rbenv not installed, {} not either".format(name)
            ret = {"name": name, "changes": {}, "comment": comt, "result": True}
            assert rbenv.absent(name) == ret

            comt = "Ruby {} is already absent".format(name)
            ret = {"name": name, "changes": {}, "comment": comt, "result": True}
            assert rbenv.absent(name) == ret

            name = "2.3.4"
            comt = "Successfully removed ruby"
            ret = {
                "name": name,
                "changes": {name: "Uninstalled"},
                "comment": comt,
                "default": True,
                "result": True,
            }
            assert rbenv.absent(name) == ret

            comt = "Failed to uninstall ruby"
            ret = {
                "name": name,
                "changes": {},
                "comment": comt,
                "default": True,
                "result": False,
            }
            assert rbenv.absent(name) == ret

            name = "2.4.1"
            comt = "Failed to uninstall ruby"
            ret = {
                "name": name,
                "changes": {},
                "comment": comt,
                "default": False,
                "result": False,
            }
            assert rbenv.absent(name) == ret

            comt = "Successfully removed ruby"
            ret = {
                "name": name,
                "changes": {name: "Uninstalled"},
                "comment": comt,
                "default": False,
                "result": True,
            }
            assert rbenv.absent(name) == ret


def test_install_rbenv():
    """
    Test to install rbenv if not installed.
    """
    name = "myqueue"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock_is = MagicMock(side_effect=[False, True, True, False, False])
    mock_i = MagicMock(side_effect=[False, True])
    with patch.dict(
        rbenv.__salt__, {"rbenv.is_installed": mock_is, "rbenv.install": mock_i}
    ):

        with patch.dict(rbenv.__opts__, {"test": True}):
            comt = "Rbenv is set to be installed"
            ret.update({"comment": comt, "result": None})
            assert rbenv.install_rbenv(name) == ret

            comt = "Rbenv is already installed"
            ret.update({"comment": comt, "result": True})
            assert rbenv.install_rbenv(name) == ret

        with patch.dict(rbenv.__opts__, {"test": False}):
            comt = "Rbenv is already installed"
            ret.update({"comment": comt, "result": True})
            assert rbenv.install_rbenv(name) == ret

            comt = "Rbenv failed to install"
            ret.update({"comment": comt, "result": False})
            assert rbenv.install_rbenv(name) == ret

            comt = "Rbenv installed"
            ret.update({"comment": comt, "result": True})
            assert rbenv.install_rbenv(name) == ret
