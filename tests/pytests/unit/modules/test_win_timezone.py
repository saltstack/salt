"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import importlib.util

import pytest

import salt.modules.win_timezone as win_timezone
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

requires_tzdata = pytest.mark.skipif(
    not importlib.util.find_spec("tzdata"), reason="requires tzdata"
)


@pytest.fixture
def configure_loader_modules():
    return {
        win_timezone: {
            "__opts__": {},
            "__salt__": {},
            "__utils__": {},
        },
    }


def test_get_zone_normal():
    """
    Test if it get current timezone (i.e. Asia/Calcutta)
    """
    mock_read_ok = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "India Standard Time",
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read_ok}):
        assert win_timezone.get_zone() == "Asia/Calcutta"


def test_get_zone_normal_dstoff():
    """
    Test if it gets current timezone with dst off (i.e. America/Denver)
    """
    mock_read_ok = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "Mountain Standard Time_dstoff",
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read_ok}):
        assert win_timezone.get_zone() == "America/Denver"


def test_get_zone_normal_dstoff_issue():
    """
    Test regression with dstoff fix stripping unwanted characters
    """
    mock_read_ok = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "FLE Standard Time",
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read_ok}):
        assert win_timezone.get_zone() == "Europe/Kiev"


@pytest.mark.parametrize("timezone", win_timezone.mapper.list_win())
def test_get_zone_all(timezone):
    """
    Test all Win zones are properly resolved and none returns Unknown
    """
    mock_read_ok = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": timezone,
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read_ok}):
        assert win_timezone.get_zone() != "Unknown"


def test_get_zone_unknown():
    """
    Test get_zone with unknown timezone (i.e. Indian Standard Time)
    """
    mock_read_error = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "Indian Standard Time",
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read_error}):
        assert win_timezone.get_zone() == "Unknown"


def test_get_zone_error():
    """
    Test get_zone when it encounters an error
    """
    mock_read_fatal = MagicMock(
        return_value={"pid": 78, "retcode": 1, "stderr": "", "stdout": ""}
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read_fatal}):
        with pytest.raises(CommandExecutionError):
            win_timezone.get_zone()


@requires_tzdata
def test_get_offset():
    """
    India Standard Time is a fixed +05:30 offset with no DST, so the result
    is predictable regardless of when the test runs.
    """
    mock_read = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "India Standard Time",
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read}):
        assert win_timezone.get_offset() == "+0530"


@requires_tzdata
def test_get_offset_negative():
    """
    Hawaiian Standard Time is a fixed -10:00 offset with no DST.
    """
    mock_read = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "Hawaiian Standard Time",
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read}):
        assert win_timezone.get_offset() == "-1000"


@requires_tzdata
def test_get_offset_utc():
    """
    UTC maps to Etc/GMT which is always +0000.
    """
    mock_read = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "UTC",
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read}):
        assert win_timezone.get_offset() == "+0000"


@requires_tzdata
def test_get_zonecode():
    """
    India Standard Time uses the fixed abbreviation IST.
    """
    mock_read = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "India Standard Time",
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read}):
        assert win_timezone.get_zonecode() == "IST"


@requires_tzdata
def test_get_zonecode_hawaii():
    """
    Hawaiian Standard Time uses the fixed abbreviation HST (no DST).
    """
    mock_read = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "Hawaiian Standard Time",
        }
    )
    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read}):
        assert win_timezone.get_zonecode() == "HST"


def test_set_zone():
    """
    Test if it unlinks, then symlinks /etc/localtime to the set timezone.
    """
    mock_write = MagicMock(
        return_value={"pid": 78, "retcode": 0, "stderr": "", "stdout": ""}
    )
    mock_read = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "India Standard Time",
        }
    )

    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_write}), patch.dict(
        win_timezone.__salt__, {"cmd.run_all": mock_read}
    ):
        assert win_timezone.set_zone("Asia/Calcutta")


def test_zone_compare():
    """
    Test if it checks the md5sum between the given timezone, and
    the one set in /etc/localtime. Returns True if they match,
    and False if not. Mostly useful for running state checks.
    """
    mock_read = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": "India Standard Time",
        }
    )

    with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read}):
        assert win_timezone.zone_compare("Asia/Calcutta")


def test_get_hwclock():
    """
    Test if it get current hardware clock setting (UTC or localtime)
    """
    assert win_timezone.get_hwclock() == "localtime"


def test_set_hwclock():
    """
    Test if it sets the hardware clock to be either UTC or localtime
    """
    assert not win_timezone.set_hwclock("UTC")
