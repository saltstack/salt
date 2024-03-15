"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.ret
"""

import pytest

import salt.loader
import salt.modules.ret as ret
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {ret: {}}


# 'get_jid' function tests: 1


def test_get_jid():
    """
    Test if it return the information for a specified job id
    """
    mock_ret = MagicMock(return_value="DB")
    with patch.object(
        salt.loader,
        "returners",
        MagicMock(return_value={"redis.get_jid": mock_ret}),
    ):
        assert ret.get_jid("redis", "net") == "DB"


# 'get_fun' function tests: 1


def test_get_fun():
    """
    Test if it return info about last time fun was called on each minion
    """
    mock_ret = MagicMock(return_value="DB")
    with patch.object(
        salt.loader,
        "returners",
        MagicMock(return_value={"mysql.get_fun": mock_ret}),
    ):
        assert ret.get_fun("mysql", "net") == "DB"


# 'get_jids' function tests: 1


def test_get_jids():
    """
    Test if it return a list of all job ids
    """
    mock_ret = MagicMock(return_value="DB")
    with patch.object(
        salt.loader,
        "returners",
        MagicMock(return_value={"mysql.get_jids": mock_ret}),
    ):
        assert ret.get_jids("mysql") == "DB"


# 'get_minions' function tests: 1


def test_get_minions():
    """
    Test if it return a list of all minions
    """
    mock_ret = MagicMock(return_value="DB")
    with patch.object(
        salt.loader,
        "returners",
        MagicMock(return_value={"mysql.get_minions": mock_ret}),
    ):
        assert ret.get_minions("mysql") == "DB"
