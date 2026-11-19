"""
Unit tests for salt.utils.win_pdh.
"""

import pytest

import salt.utils.win_pdh as win_pdh
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_get_all_counters_default_instances():
    mock_win32pdh = MagicMock()
    mock_win32pdh.EnumObjectItems.return_value = (
        ["% Processor Time", "% User Time"],
        ["0", "_Total"],
    )
    expected_ret = {"\\Processor(*)\\% Processor Time": 12.5}
    with patch.object(win_pdh, "win32pdh", mock_win32pdh, create=True):
        with patch.object(
            win_pdh, "get_counters", return_value=expected_ret
        ) as mock_get_counters:
            ret = win_pdh.get_all_counters("Processor")

    assert ret == expected_ret
    mock_win32pdh.EnumObjectItems.assert_called_once_with(
        None, None, "Processor", -1, 0
    )
    mock_get_counters.assert_called_once_with(
        [
            ("Processor", "0", "% Processor Time"),
            ("Processor", "*", "% Processor Time"),
            ("Processor", None, "% Processor Time"),
            ("Processor", "0", "% User Time"),
            ("Processor", "*", "% User Time"),
            ("Processor", None, "% User Time"),
        ]
    )


def test_get_all_counters_non_list_instance_list():
    mock_win32pdh = MagicMock()
    mock_win32pdh.EnumObjectItems.return_value = (
        ["% Processor Time"],
        ["0", "_Total"],
    )
    with patch.object(win_pdh, "win32pdh", mock_win32pdh, create=True):
        with patch.object(
            win_pdh, "get_counters", return_value={}
        ) as mock_get_counters:
            win_pdh.get_all_counters("Processor", instance_list="_Total")

    mock_get_counters.assert_called_once_with(
        [
            ("Processor", "*", "% Processor Time"),
            ("Processor", None, "% Processor Time"),
        ]
    )


def test_get_all_counters_empty_instances():
    mock_win32pdh = MagicMock()
    mock_win32pdh.EnumObjectItems.return_value = (["Available Bytes"], [])
    with patch.object(win_pdh, "win32pdh", mock_win32pdh, create=True):
        with patch.object(
            win_pdh, "get_counters", return_value={}
        ) as mock_get_counters:
            win_pdh.get_all_counters("Memory")

    mock_get_counters.assert_called_once_with([("Memory", None, "Available Bytes")])


def test_get_all_counters_empty_counters():
    mock_win32pdh = MagicMock()
    mock_win32pdh.EnumObjectItems.return_value = ([], ["0"])
    with patch.object(win_pdh, "win32pdh", mock_win32pdh, create=True):
        with patch.object(win_pdh, "get_counters") as mock_get_counters:
            ret = win_pdh.get_all_counters("EmptyObj")

    assert ret == {}
    mock_get_counters.assert_not_called()
