"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.webutil
"""


import pytest

import salt.modules.webutil as htpasswd
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {htpasswd: {}}


# 'useradd' function tests: 1


def test_useradd():
    """
    Test if it adds an HTTP user using the htpasswd command
    """
    mock = MagicMock(return_value={"out": "Salt"})
    with patch.dict(htpasswd.__salt__, {"cmd.run_all": mock}), patch(
        "os.path.exists", MagicMock(return_value=True)
    ):
        assert htpasswd.useradd("/etc/httpd/htpasswd", "larry", "badpassword") == {
            "out": "Salt"
        }


# 'userdel' function tests: 2


def test_userdel():
    """
    Test if it delete an HTTP user from the specified htpasswd file.
    """
    mock = MagicMock(return_value="Salt")
    with patch.dict(htpasswd.__salt__, {"cmd.run": mock}), patch(
        "os.path.exists", MagicMock(return_value=True)
    ):
        assert htpasswd.userdel("/etc/httpd/htpasswd", "larry") == ["Salt"]


def test_userdel_missing_htpasswd():
    """
    Test if it returns error when no htpasswd file exists
    """
    with patch("os.path.exists", MagicMock(return_value=False)):
        assert (
            htpasswd.userdel("/etc/httpd/htpasswd", "larry")
            == "Error: The specified htpasswd file does not exist"
        )
