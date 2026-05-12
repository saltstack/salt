import logging

import pytest
from saltfactories.utils import random_string

import salt.modules.cmdmod as cmdmod
import salt.modules.win_useradd as win_useradd
from tests.support.mock import MagicMock, patch

try:
    import pywintypes

    WINAPI = True
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
