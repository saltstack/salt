"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.cpan as cpan
from tests.support.mock import MagicMock, patch

# 'install' function tests: 2


@pytest.fixture
def configure_loader_modules():
    return {cpan: {}}


def test_install():
    """
    Test if it install a module from cpan
    """
    mock = MagicMock(return_value="")
    with patch.dict(cpan.__salt__, {"cmd.run": mock}):
        mock = MagicMock(
            side_effect=[{"installed version": None}, {"installed version": "3.1"}]
        )
        with patch.object(cpan, "show", mock):
            assert cpan.install("Alloy") == {"new": "3.1", "old": None}


def test_install_error():
    """
    Test if it install a module from cpan
    """
    mock = MagicMock(return_value="don't know what it is")
    with patch.dict(cpan.__salt__, {"cmd.run": mock}):
        assert cpan.install("Alloy") == {
            "error": "CPAN cannot identify this package",
            "new": None,
            "old": None,
        }


# 'remove' function tests: 4


def test_remove():
    """
    Test if it remove a module using cpan
    """
    with patch("os.listdir", MagicMock(return_value=[""])):
        mock = MagicMock(return_value="")
        with patch.dict(cpan.__salt__, {"cmd.run": mock}):
            mock = MagicMock(
                return_value={
                    "installed version": "2.1",
                    "cpan build dirs": [""],
                    "installed file": "/root",
                }
            )
            with patch.object(cpan, "show", mock):
                assert cpan.remove("Alloy") == {"new": None, "old": "2.1"}


def test_remove_unexist_error():
    """
    Test if it try to remove an unexist module using cpan
    """
    mock = MagicMock(return_value="don't know what it is")
    with patch.dict(cpan.__salt__, {"cmd.run": mock}):
        assert cpan.remove("Alloy") == {"error": "This package does not seem to exist"}


def test_remove_noninstalled_error():
    """
    Test if it remove non installed module using cpan
    """
    mock = MagicMock(return_value={"installed version": None})
    with patch.object(cpan, "show", mock):
        assert cpan.remove("Alloy") == {"new": None, "old": None}


def test_remove_nopan_error():
    """
    Test if it gives no cpan error while removing
    """
    ret = {"error": "No CPAN data available to use for uninstalling"}
    mock = MagicMock(return_value={"installed version": "2.1"})
    with patch.object(cpan, "show", mock):
        assert cpan.remove("Alloy") == ret


# 'list' function tests: 1


def test_list():
    """
    Test if it list installed Perl module
    """
    mock = MagicMock(return_value="")
    with patch.dict(cpan.__salt__, {"cmd.run": mock}):
        assert cpan.list_() == {}


# 'show' function tests: 2


def test_show():
    """
    Test if it show information about a specific Perl module
    """
    mock = MagicMock(return_value="")
    with patch.dict(cpan.__salt__, {"cmd.run": mock}):
        assert cpan.show("Alloy") == {
            "error": "This package does not seem to exist",
            "name": "Alloy",
        }


def test_show_mock():
    """
    Test if it show information about a specific Perl module
    """
    with patch("salt.modules.cpan.show", MagicMock(return_value={"Salt": "salt"})):
        mock = MagicMock(return_value="Salt module installed")
        with patch.dict(cpan.__salt__, {"cmd.run": mock}):
            assert cpan.show("Alloy") == {"Salt": "salt"}


# 'show_config' function tests: 1


def test_show_config():
    """
    Test if it return a dict of CPAN configuration values
    """
    mock = MagicMock(return_value="")
    with patch.dict(cpan.__salt__, {"cmd.run": mock}):
        assert cpan.show_config() == {}
