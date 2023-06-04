"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.rbenv
"""


import os

import pytest

import salt.modules.rbenv as rbenv
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rbenv: {}}


def test_install():
    """
    Test for install Rbenv systemwide
    """
    with patch.object(rbenv, "_rbenv_path", return_value=True):
        with patch.object(rbenv, "_install_rbenv", return_value=True):
            with patch.object(rbenv, "_install_ruby_build", return_value=True):
                with patch.object(os.path, "expanduser", return_value="A"):
                    assert rbenv.install()


def test_update():
    """
    Test for updates the current versions of Rbenv and Ruby-Build
    """
    with patch.object(rbenv, "_rbenv_path", return_value=True):
        with patch.object(rbenv, "_update_rbenv", return_value=True):
            with patch.object(rbenv, "_update_ruby_build", return_value=True):
                with patch.object(os.path, "expanduser", return_value="A"):
                    assert rbenv.update()


def test_is_installed():
    """
    Test for check if Rbenv is installed.
    """
    with patch.object(rbenv, "_rbenv_bin", return_value="A"):
        with patch.dict(rbenv.__salt__, {"cmd.has_exec": MagicMock(return_value=True)}):
            assert rbenv.is_installed()


def test_install_ruby():
    """
    Test for install a ruby implementation.
    """
    with patch.dict(rbenv.__grains__, {"os": "FreeBSD"}):
        with patch.dict(rbenv.__salt__, {"config.get": MagicMock(return_value="True")}):
            with patch.object(
                rbenv,
                "_rbenv_exec",
                return_value={"retcode": 0, "stderr": "stderr"},
            ):
                with patch.object(rbenv, "rehash", return_value=None):
                    assert rbenv.install_ruby("ruby") == "stderr"

            with patch.object(
                rbenv,
                "_rbenv_exec",
                return_value={"retcode": 1, "stderr": "stderr"},
            ):
                with patch.object(rbenv, "uninstall_ruby", return_value=None):
                    assert not rbenv.install_ruby("ruby")


def test_uninstall_ruby():
    """
    Test for uninstall a ruby implementation.
    """
    with patch.object(rbenv, "_rbenv_exec", return_value=None):
        assert rbenv.uninstall_ruby("ruby", "runas")


def test_versions():
    """
    Test for list the installed versions of ruby.
    """
    with patch.object(rbenv, "_rbenv_exec", return_value="A\nBC\nD"):
        assert rbenv.versions() == ["A", "BC", "D"]


def test_default():
    """
    Test for returns or sets the currently defined default ruby.
    """
    with patch.object(rbenv, "_rbenv_exec", MagicMock(side_effect=[None, False])):
        assert rbenv.default("ruby", "runas")

        assert rbenv.default() == ""


def test_list_():
    """
    Test for list the installable versions of ruby.
    """
    with patch.object(rbenv, "_rbenv_exec", return_value="A\nB\nCD\n"):
        assert rbenv.list_() == ["A", "B", "CD"]


def test_rehash():
    """
    Test for run rbenv rehash to update the installed shims.
    """
    with patch.object(rbenv, "_rbenv_exec", return_value=None):
        assert rbenv.rehash()


def test_do_with_ruby():
    """
    Test for execute a ruby command with rbenv's shims using a
    specific ruby version.
    """
    with patch.object(rbenv, "do", return_value="A"):
        assert rbenv.do_with_ruby("ruby", "cmdline") == "A"
