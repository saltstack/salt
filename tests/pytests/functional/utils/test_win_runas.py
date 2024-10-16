"""
Test the win_runas util
"""

import pytest

import salt.utils.win_runas as win_runas

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def user():
    with pytest.helpers.create_account() as account:
        yield account


def test_compound_runas(user):
    cmd = "hostname && whoami"
    result = win_runas.runas(
        cmdLine=cmd,
        username=user.username,
        password=user.password,
    )
    assert user.username in result["stdout"]


def test_compound_runas_unpriv(user):
    cmd = "hostname && whoami"
    print(user.username)
    result = win_runas.runas_unpriv(
        cmd=cmd,
        username=user.username,
        password=user.password,
    )
    assert user.username in result["stdout"]
