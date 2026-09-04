import logging

import pytest
from saltfactories.utils import random_string

import salt.modules.cmdmod as cmdmod
import salt.modules.win_useradd as win_useradd
from tests.support.mock import MagicMock, patch

try:
    import pywintypes
    import win32net

    WINAPI = True

    class _WinNetError(win32net.error):
        """Subclass that lets us instantiate a win32net.error in tests."""

        winerror = 2221  # NERR_UserNotFound
        funcname = "NetUserGetInfo"
        strerror = "The user name could not be found."

except ImportError:
    WINAPI = False

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {
        win_useradd: {
            "__salt__": {
                "cmd.run_all": cmdmod.run_all,
            },
        }
    }


@pytest.fixture
def username():
    _username = random_string("test-account-", uppercase=False)
    try:
        yield _username
    finally:
        try:
            win_useradd.delete(_username, purge=True, force=True)
        except Exception:  # pylint: disable=broad-except
            # The point here is just system cleanup. It can fail if no account
            # was created
            pass


@pytest.fixture
def account(username):
    with pytest.helpers.create_account(username=username) as account:
        win_useradd.addgroup(account.username, "Users")
        yield account


@pytest.mark.skipif(not WINAPI, reason="pywin32 not available")
def test_info(account, caplog):
    with caplog.at_level(logging.DEBUG):
        win_useradd.info(account.username)
    assert f"user_name: {account.username}" in caplog.text
    assert "domain_name: ." in caplog.text


@pytest.mark.skipif(not WINAPI, reason="pywin32 not available")
def test_info_domain(account, caplog):
    domain = "mydomain"
    dc = "myDC"
    dc_info = {"DomainControllerName": dc}
    with caplog.at_level(logging.DEBUG), patch(
        "win32security.DsGetDcName", MagicMock(return_value=dc_info)
    ):
        account.username = f"{domain}\\{account.username}"
        win_useradd.info(account.username)
    assert f"Found DC: {dc}" in caplog.text


@pytest.mark.skipif(not WINAPI, reason="pywin32 not available")
def test_info_error(account, caplog):
    domain = "mydomain"
    dc = "myDC"
    with caplog.at_level(logging.DEBUG), patch(
        "win32security.DsGetDcName", MagicMock(side_effect=pywintypes.error)
    ):
        account.username = f"{domain}\\{account.username}"
        win_useradd.info(account.username)
    assert f"DC not found. Using username: {account.username}" in caplog.text


@pytest.mark.skipif(not WINAPI, reason="pywin32 not available")
def test_setpassword_user_not_found(caplog):
    """
    Regression test for #68428.

    ``user.setpassword`` must return ``False`` (not the Win32 error string)
    when the target user does not exist, so the CLI and the ``user.present``
    state correctly report failure instead of a bogus success.
    """
    missing_user = random_string("missing-account-", uppercase=False)

    # Force info() to behave as it does when the user doesn't exist: the
    # NetUserGetInfo lookup raises win32net.error and info() returns an empty
    # dict. We patch the underlying win32net call so the production code path
    # in both info() and update() is exercised.
    with caplog.at_level(logging.ERROR), patch(
        "win32net.NetUserGetInfo",
        MagicMock(
            side_effect=_WinNetError(
                2221, "NetUserGetInfo", "The user name could not be found."
            )
        ),
    ):
        result = win_useradd.setpassword(missing_user, "P@ssw0rd")

    assert (
        result is False
    ), f"setpassword on a missing user must return False, got {result!r}"
    assert f"User '{missing_user}' does not exist" in caplog.text
