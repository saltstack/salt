"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import os

import pytest

import salt.modules.debconfmod as debconfmod
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {debconfmod: {}}


def test_get_selections():
    """
    Test for Answers to debconf questions for all packages
    """
    mock = MagicMock(return_value=[])
    with patch.dict(debconfmod.__salt__, {"cmd.run_stdout": mock}):
        with patch.object(debconfmod, "_unpack_lines", mock):
            assert debconfmod.get_selections(False) == {}


def test_show():
    """
    Test for Answers to debconf questions for a package
    """
    mock = MagicMock(return_value={})
    with patch.object(debconfmod, "get_selections", mock):
        assert debconfmod.show("name") is None


def test_set_():
    """
    Test for Set answers to debconf questions for a package.
    """
    mock = MagicMock(return_value=None)
    with patch.object(os, "write", mock):
        with patch.object(os, "close", mock):
            with patch.object(debconfmod, "_set_file", mock):
                with patch.object(os, "unlink", mock):
                    assert debconfmod.set_("package", "question", "type", "value")


def test_set_template():
    """
    Test for Set answers to debconf questions from a template.
    """
    mock = MagicMock(return_value="A")
    with patch.dict(debconfmod.__salt__, {"cp.get_template": mock}):
        with patch.object(debconfmod, "set_file", mock):
            assert (
                debconfmod.set_template(
                    "path", "template", "context", "defaults", "saltenv"
                )
                == "A"
            )


def test_set_file():
    """
    Test for Set answers to debconf questions from a file.
    """
    mock = MagicMock(return_value="A")
    with patch.dict(debconfmod.__salt__, {"cp.cache_file": mock}):
        mock = MagicMock(return_value=None)
        with patch.object(debconfmod, "_set_file", mock):
            assert debconfmod.set_file("path")

    mock = MagicMock(return_value=False)
    with patch.dict(debconfmod.__salt__, {"cp.cache_file": mock}):
        mock = MagicMock(return_value=None)
        with patch.object(debconfmod, "_set_file", mock):
            assert not debconfmod.set_file("path")
