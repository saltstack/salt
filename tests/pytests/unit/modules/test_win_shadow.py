"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.win_shadow
"""

import pytest

import salt.modules.win_shadow as win_shadow
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_shadow: {"__salt__": {"user.update": MagicMock(return_value=True)}}}


def test_info():
    """
    Test if it return information for the specified user
    """
    mock_user_info = MagicMock(
        return_value={"name": "SALT", "password_changed": "", "expiration_date": ""}
    )
    with patch.dict(win_shadow.__salt__, {"user.info": mock_user_info}):
        assert win_shadow.info("SALT") == {
            "name": "SALT",
            "passwd": "Unavailable",
            "lstchg": "",
            "min": "",
            "max": "",
            "warn": "",
            "inact": "",
            "expire": "",
        }


def test_set_password():
    """
    Test if it set the password for a named user.
    """
    mock_cmd = MagicMock(return_value={"retcode": False})
    mock_user_info = MagicMock(
        return_value={"name": "SALT", "password_changed": "", "expiration_date": ""}
    )
    with patch.dict(
        win_shadow.__salt__, {"cmd.run_all": mock_cmd, "user.info": mock_user_info}
    ):
        assert win_shadow.set_password("root", "mysecretpassword")
