"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.pecl
"""


import pytest

import salt.modules.pecl as pecl
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {pecl: {}}


def test_install():
    """
    Test to installs one or several pecl extensions.
    """
    with patch.object(pecl, "_pecl", return_value="A"):
        assert pecl.install("fuse", force=True) == "A"

        assert not pecl.install("fuse")

        with patch.object(pecl, "list_", return_value={"A": ["A", "B"]}):
            assert pecl.install(["A", "B"])


def test_uninstall():
    """
    Test to uninstall one or several pecl extensions.
    """
    with patch.object(pecl, "_pecl", return_value="A"):
        assert pecl.uninstall("fuse") == "A"


def test_update():
    """
    Test to update one or several pecl extensions.
    """
    with patch.object(pecl, "_pecl", return_value="A"):
        assert pecl.update("fuse") == "A"


def test_list_():
    """
    Test to list installed pecl extensions.
    """
    with patch.object(pecl, "_pecl", return_value="A\nB"):
        assert pecl.list_("channel") == {}
