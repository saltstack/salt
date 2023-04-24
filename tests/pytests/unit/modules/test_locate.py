"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.locate
"""


import pytest

import salt.modules.locate as locate
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {locate: {}}


# 'version' function tests: 1


def test_version():
    """
    Test if it returns the version of locate
    """
    mock = MagicMock(return_value="mlocate 0.26")
    with patch.dict(locate.__salt__, {"cmd.run": mock}):
        assert locate.version() == ["mlocate 0.26"]


# 'stats' function tests: 1


def test_stats():
    """
    Test if it returns statistics about the locate database
    """
    ret = {
        "files": "75,253",
        "directories": "49,252",
        "bytes in file names": "93,214",
        "bytes used to store database": "29,165",
        "database": "/var/lib/mlocate/mlocate.db",
    }

    mock_ret = """Database /var/lib/mlocate/mlocate.db:
    49,252 directories
    75,253 files
    93,214 bytes in file names
    29,165 bytes used to store database"""

    with patch.dict(locate.__salt__, {"cmd.run": MagicMock(return_value=mock_ret)}):
        assert locate.stats() == ret


# 'updatedb' function tests: 1


def test_updatedb():
    """
    Test if it updates the locate database
    """
    mock = MagicMock(return_value="")
    with patch.dict(locate.__salt__, {"cmd.run": mock}):
        assert locate.updatedb() == []


# 'locate' function tests: 1


def test_locate():
    """
    Test if it performs a file lookup.
    """
    mock = MagicMock(return_value="")
    with patch.dict(locate.__salt__, {"cmd.run": mock}):
        assert locate.locate("wholename", database="myfile") == []
