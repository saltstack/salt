"""
Test the win_runas util
"""

from random import randint

import pytest

import salt.modules.win_useradd as win_useradd
import salt.utils.win_runas as win_runas

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def user():
    with pytest.helpers.create_account() as account:
        yield account


@pytest.fixture
def int_user():
    with pytest.helpers.create_account() as account:
        int_name = randint(10000, 99999)
        win_useradd.rename(account.username, int_name)
        account.username = int_name
        yield account


@pytest.mark.parametrize(
    "cmd, expected",
    [
        ("hostname && whoami", "username"),
        ("hostname && echo foo", "foo"),
        ("hostname && python --version", "Python"),
    ],
)
def test_compound_runas(user, cmd, expected):
    if expected == "username":
        expected = user.username
    result = win_runas.runas(
        cmdLine=cmd,
        username=user.username,
        password=user.password,
    )
    assert expected in result["stdout"]


@pytest.mark.parametrize(
    "cmd, expected",
    [
        ("hostname && whoami", "username"),
        ("hostname && echo foo", "foo"),
        ("hostname && python --version", "Python"),
    ],
)
def test_compound_runas_unpriv(user, cmd, expected):
    if expected == "username":
        expected = user.username
    result = win_runas.runas_unpriv(
        cmd=cmd,
        username=user.username,
        password=user.password,
    )
    assert expected in result["stdout"]


def test_runas_str_user(user):
    result = win_runas.runas(
        cmdLine="whoami", username=user.username, password=user.password
    )
    assert user.username in result["stdout"]


def test_runas_int_user(int_user):
    result = win_runas.runas(
        cmdLine="whoami", username=int(int_user.username), password=int_user.password
    )
    assert str(int_user.username) in result["stdout"]


def test_runas_unpriv_str_user(user):
    result = win_runas.runas_unpriv(
        cmd="whoami", username=user.username, password=user.password
    )
    assert user.username in result["stdout"]


def test_runas_unpriv_int_user(int_user):
    result = win_runas.runas_unpriv(
        cmd="whoami", username=int(int_user.username), password=int_user.password
    )
    assert str(int_user.username) in result["stdout"]
