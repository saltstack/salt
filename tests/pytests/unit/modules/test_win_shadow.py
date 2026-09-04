"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.win_shadow
"""

import pytest

import salt.modules.win_shadow as win_shadow
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_unless_on_windows,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def configure_loader_modules():
    return {
        win_shadow: {
            "__salt__": {
                "user.update": MagicMock(return_value=True),
                "user.info": MagicMock(return_value={"account_locked": False}),
            }
        }
    }


def _win_error(code):
    """Return a pywintypes.error with the given winerror code."""
    import pywintypes

    return pywintypes.error(code, "LogonUser", f"winerror {code}")


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# verify_password unit tests
# ---------------------------------------------------------------------------


def test_verify_password_valid():
    """LogonUser succeeds — password is correct."""
    mock_handle = MagicMock()
    with patch("win32security.LogonUser", return_value=mock_handle):
        assert win_shadow.verify_password("testuser", "correct") is True
    mock_handle.Close.assert_called_once()


def test_verify_password_wrong_password():
    """LogonUser raises ERROR_LOGON_FAILURE — password is wrong, no lockout."""
    import winerror

    mock_post_info = MagicMock(return_value={"account_locked": False})
    with patch.dict(win_shadow.__salt__, {"user.info": mock_post_info}):
        with patch(
            "win32security.LogonUser",
            side_effect=_win_error(winerror.ERROR_LOGON_FAILURE),
        ):
            assert win_shadow.verify_password("testuser", "wrong") is False


def test_verify_password_causes_lockout():
    """
    LogonUser raises ERROR_LOGON_FAILURE and the account is now locked.
    The function should unlock it and return False.
    """
    import winerror

    user_info_responses = [
        {"account_locked": False},  # pre_info
        {"account_locked": True},  # post_info (our call caused lockout)
    ]
    mock_user_info = MagicMock(side_effect=user_info_responses)
    mock_user_update = MagicMock(return_value=True)

    with patch.dict(
        win_shadow.__salt__,
        {"user.info": mock_user_info, "user.update": mock_user_update},
    ):
        with patch(
            "win32security.LogonUser",
            side_effect=_win_error(winerror.ERROR_LOGON_FAILURE),
        ):
            result = win_shadow.verify_password("testuser", "wrong")

    assert result is False
    mock_user_update.assert_called_once_with("testuser", unlock_account=True)


def test_verify_password_pre_locked():
    """
    Account was already locked before the call — must raise CommandExecutionError.
    """
    import winerror

    with patch(
        "win32security.LogonUser",
        side_effect=_win_error(winerror.ERROR_ACCOUNT_LOCKED_OUT),
    ):
        with pytest.raises(CommandExecutionError):
            win_shadow.verify_password("testuser", "anypass")


def test_verify_password_wrong_password_pre_locked_no_unlock():
    """
    Account was already locked (ERROR_LOGON_FAILURE path).
    The function must NOT call user.update because it was pre-locked.
    """
    import winerror

    mock_pre_info = MagicMock(return_value={"account_locked": True})
    mock_user_update = MagicMock(return_value=True)

    with patch.dict(
        win_shadow.__salt__,
        {"user.info": mock_pre_info, "user.update": mock_user_update},
    ):
        with patch(
            "win32security.LogonUser",
            side_effect=_win_error(winerror.ERROR_LOGON_FAILURE),
        ):
            result = win_shadow.verify_password("testuser", "wrong")

    assert result is False
    mock_user_update.assert_not_called()


@pytest.mark.parametrize(
    "error_code",
    [
        "ERROR_ACCOUNT_DISABLED",
        "ERROR_ACCOUNT_EXPIRED",
        "ERROR_PASSWORD_EXPIRED",
        "ERROR_PASSWORD_MUST_CHANGE",
        "ERROR_ACCOUNT_RESTRICTION",
        "ERROR_INVALID_LOGON_HOURS",
        "ERROR_INVALID_WORKSTATION",
        "ERROR_LOGON_NOT_GRANTED",
        "ERROR_LOGON_TYPE_NOT_GRANTED",
    ],
)
def test_verify_password_restriction_errors_return_true(error_code):
    """
    Errors that occur after a successful credential check (the password is
    correct but some other restriction prevents logon) must return True.
    """
    import winerror

    code = getattr(winerror, error_code)
    with patch("win32security.LogonUser", side_effect=_win_error(code)):
        assert win_shadow.verify_password("testuser", "correct") is True


def test_verify_password_unknown_error():
    """An unrecognised winerror code must raise CommandExecutionError."""
    with patch("win32security.LogonUser", side_effect=_win_error(9999)):
        with pytest.raises(CommandExecutionError):
            win_shadow.verify_password("testuser", "anypass")


def test_verify_password_upn_format():
    """UPN-format names (user@domain) are split correctly."""
    mock_handle = MagicMock()
    with patch("win32security.LogonUser", return_value=mock_handle) as mock_logon:
        win_shadow.verify_password("alice@corp.example", "pass")
    args = mock_logon.call_args[0]
    assert args[0] == "alice"
    assert args[1] == "corp.example"


def test_verify_password_downlevel_format():
    """Down-level names (DOMAIN\\user) are split correctly."""
    mock_handle = MagicMock()
    with patch("win32security.LogonUser", return_value=mock_handle) as mock_logon:
        win_shadow.verify_password("CORP\\alice", "pass")
    args = mock_logon.call_args[0]
    assert args[0] == "alice"
    assert args[1] == "CORP"


def test_verify_password_local_format():
    """Plain local names use '.' as the domain."""
    mock_handle = MagicMock()
    with patch("win32security.LogonUser", return_value=mock_handle) as mock_logon:
        win_shadow.verify_password("alice", "pass")
    args = mock_logon.call_args[0]
    assert args[0] == "alice"
    assert args[1] == "."
