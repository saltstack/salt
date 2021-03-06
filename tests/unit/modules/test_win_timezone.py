"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
import salt.modules.win_timezone as win_timezone
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


@skipIf(not win_timezone.HAS_PYTZ, "This test requires pytz")
class WinTimezoneTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.win_timezone
    """

    def setup_loader_modules(self):
        return {win_timezone: {}}

    def test_get_zone_normal(self):
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
            self.assertEqual(win_timezone.get_zone(), "Asia/Calcutta")

    def test_get_zone_normal_dstoff(self):
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
            self.assertEqual(win_timezone.get_zone(), "America/Denver")

    def test_get_zone_unknown(self):
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
            self.assertEqual(win_timezone.get_zone(), "Unknown")

    def test_get_zone_error(self):
        """
        Test get_zone when it encounters an error
        """
        mock_read_fatal = MagicMock(
            return_value={"pid": 78, "retcode": 1, "stderr": "", "stdout": ""}
        )
        with patch.dict(win_timezone.__salt__, {"cmd.run_all": mock_read_fatal}):
            self.assertRaises(CommandExecutionError, win_timezone.get_zone)

    # 'get_offset' function tests: 1

    def test_get_offset(self):
        """
        Test if it get current numeric timezone offset from UCT (i.e. +0530)
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
            self.assertEqual(win_timezone.get_offset(), "+0530")

    # 'get_zonecode' function tests: 1

    def test_get_zonecode(self):
        """
        Test if it get current timezone (i.e. PST, MDT, etc)
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
            self.assertEqual(win_timezone.get_zonecode(), "IST")

    # 'set_zone' function tests: 1

    def test_set_zone(self):
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

            self.assertTrue(win_timezone.set_zone("Asia/Calcutta"))

    # 'zone_compare' function tests: 1

    def test_zone_compare(self):
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
            self.assertTrue(win_timezone.zone_compare("Asia/Calcutta"))

    # 'get_hwclock' function tests: 1

    def test_get_hwclock(self):
        """
        Test if it get current hardware clock setting (UTC or localtime)
        """
        self.assertEqual(win_timezone.get_hwclock(), "localtime")

    # 'set_hwclock' function tests: 1

    def test_set_hwclock(self):
        """
        Test if it sets the hardware clock to be either UTC or localtime
        """
        self.assertFalse(win_timezone.set_hwclock("UTC"))
