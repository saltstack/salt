"""
Tests for salt.utils.dateutils
"""

import datetime

import pytest

import salt.utils.dateutils
from tests.support.mock import patch
from tests.support.unit import TestCase

try:
    import timelib  # pylint: disable=import-error,unused-import

    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False


class DateutilsTestCase(TestCase):
    def test_date_cast(self):
        now = datetime.datetime.now()
        with patch("datetime.datetime"):
            datetime.datetime.now.return_value = now
            self.assertEqual(now, salt.utils.dateutils.date_cast(None))
        self.assertEqual(now, salt.utils.dateutils.date_cast(now))
        try:
            ret = salt.utils.dateutils.date_cast("Mon Dec 23 10:19:15 MST 2013")
            expected_ret = datetime.datetime(2013, 12, 23, 10, 19, 15)
            self.assertEqual(ret, expected_ret)
        except RuntimeError:
            if not HAS_TIMELIB:
                # Unparseable without timelib installed
                self.skipTest("'timelib' is not installed")
            else:
                raise

    @pytest.mark.skipif(not HAS_TIMELIB, reason="'timelib' is not installed")
    def test_strftime(self):

        # Taken from doctests

        expected_ret = "2002-12-25"

        src = datetime.datetime(2002, 12, 25, 12, 00, 00, 00)
        ret = salt.utils.dateutils.strftime(src)
        self.assertEqual(ret, expected_ret)

        src = "2002/12/25"
        ret = salt.utils.dateutils.strftime(src)
        self.assertEqual(ret, expected_ret)

        src = 1040814000
        ret = salt.utils.dateutils.strftime(src)
        self.assertEqual(ret, expected_ret)

        src = "1040814000"
        ret = salt.utils.dateutils.strftime(src)
        self.assertEqual(ret, expected_ret)
