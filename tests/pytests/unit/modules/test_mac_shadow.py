"""
Unit Tests for the mac_desktop execution module.
"""

import pytest

import salt.modules.mac_shadow as mac_shadow
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skip_unless_on_darwin,
]


def test_get_account_created():
    with patch.object(mac_shadow, "_get_account_policy_data_value", return_value="0"):
        result = mac_shadow.get_account_created("junk")
        expected = "1969-12-31 17:00:00"
        assert result == expected


def test_get_account_created_error():
    with patch.object(
        mac_shadow, "_get_account_policy_data_value", side_effect=CommandExecutionError
    ):
        result = mac_shadow.get_account_created("junk")
        expected = "0"
        assert result == expected


def test_get_last_change():
    with patch.object(mac_shadow, "_get_account_policy_data_value", return_value="0"):
        result = mac_shadow.get_last_change("junk")
        expected = "1969-12-31 17:00:00"
        assert result == expected


def test_get_last_change_error():
    with patch.object(
        mac_shadow, "_get_account_policy_data_value", side_effect=CommandExecutionError
    ):
        result = mac_shadow.get_last_change("junk")
        expected = "0"
        assert result == expected


def test_login_failed_count():
    with patch.object(mac_shadow, "_get_account_policy_data_value", return_value="0"):
        result = mac_shadow.get_login_failed_count("junk")
        expected = "0"
        assert result == expected


def test_get_login_failed_count_error():
    with patch.object(
        mac_shadow, "_get_account_policy_data_value", side_effect=CommandExecutionError
    ):
        result = mac_shadow.get_login_failed_count("junk")
        expected = "0"
        assert result == expected


def test_login_failed_last():
    with patch.object(mac_shadow, "_get_account_policy_data_value", return_value="0"):
        result = mac_shadow.get_login_failed_last("junk")
        expected = "1969-12-31 17:00:00"
        assert result == expected


def test_get_login_failed_last_error():
    with patch.object(
        mac_shadow, "_get_account_policy_data_value", side_effect=CommandExecutionError
    ):
        result = mac_shadow.get_login_failed_last("junk")
        expected = "0"
        assert result == expected
