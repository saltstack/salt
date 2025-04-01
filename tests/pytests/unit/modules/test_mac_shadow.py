"""
Unit Tests for the mac_desktop execution module.
"""

from datetime import datetime

import pytest

import salt.modules.mac_shadow as mac_shadow
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture
def zero_date():
    return datetime.fromtimestamp(0).strftime("%Y-%m-%d %H:%M:%S")


def test_get_account_created(zero_date):
    with patch.object(mac_shadow, "_get_account_policy_data_value", return_value="0"):
        result = mac_shadow.get_account_created("junk")
        assert result == zero_date


def test_get_account_created_no_value():
    with patch.object(
        mac_shadow,
        "_get_account_policy_data_value",
        side_effect=CommandExecutionError("Value not found: creationTime"),
    ):
        result = mac_shadow.get_account_created("junk")
        expected = "0"
        assert result == expected


def test_get_account_created_error():
    with patch.object(
        mac_shadow,
        "_get_account_policy_data_value",
        side_effect=CommandExecutionError("Unknown error: something happened"),
    ), pytest.raises(CommandExecutionError):
        mac_shadow.get_account_created("junk")


def test_get_last_change(zero_date):
    with patch.object(mac_shadow, "_get_account_policy_data_value", return_value="0"):
        result = mac_shadow.get_last_change("junk")
        assert result == zero_date


def test_get_last_change_no_value():
    with patch.object(
        mac_shadow,
        "_get_account_policy_data_value",
        side_effect=CommandExecutionError("Value not found: creationTime"),
    ):
        result = mac_shadow.get_last_change("junk")
        expected = "0"
        assert result == expected


def test_get_last_change_error():
    with patch.object(
        mac_shadow,
        "_get_account_policy_data_value",
        side_effect=CommandExecutionError("Unknown error: something happened"),
    ), pytest.raises(CommandExecutionError):
        mac_shadow.get_last_change("junk")


def test_login_failed_count():
    with patch.object(mac_shadow, "_get_account_policy_data_value", return_value="0"):
        result = mac_shadow.get_login_failed_count("junk")
        expected = "0"
        assert result == expected


def test_get_login_failed_count_no_value():
    with patch.object(
        mac_shadow,
        "_get_account_policy_data_value",
        side_effect=CommandExecutionError("Value not found: creationTime"),
    ):
        result = mac_shadow.get_login_failed_count("junk")
        expected = "0"
        assert result == expected


def test_get_login_failed_count_error():
    with patch.object(
        mac_shadow,
        "_get_account_policy_data_value",
        side_effect=CommandExecutionError("Unknown error: something happened"),
    ), pytest.raises(CommandExecutionError):
        mac_shadow.get_login_failed_count("junk")


def test_login_failed_last(zero_date):
    with patch.object(mac_shadow, "_get_account_policy_data_value", return_value="0"):
        result = mac_shadow.get_login_failed_last("junk")
        assert result == zero_date


def test_get_login_failed_last_no_value():
    with patch.object(
        mac_shadow,
        "_get_account_policy_data_value",
        side_effect=CommandExecutionError("Value not found: creationTime"),
    ):
        result = mac_shadow.get_login_failed_last("junk")
        expected = "0"
        assert result == expected


def test_get_login_failed_last_error():
    with patch.object(
        mac_shadow,
        "_get_account_policy_data_value",
        side_effect=CommandExecutionError("Unknown error: something happened"),
    ), pytest.raises(CommandExecutionError):
        mac_shadow.get_login_failed_last("junk")
