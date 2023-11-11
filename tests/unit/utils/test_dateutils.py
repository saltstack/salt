"""
Tests for salt.utils.dateutils
"""

import datetime

import salt.utils.dateutils
from tests.support.mock import patch
from tests.support.unit import TestCase


class DateutilsTestCase(TestCase):
    def test_date_cast(self):
        now = datetime.datetime.now()
        with patch("datetime.datetime"):
            datetime.datetime.now.return_value = now
            self.assertEqual(now, salt.utils.dateutils.date_cast(None))
        self.assertEqual(now, salt.utils.dateutils.date_cast(now))
        ret = salt.utils.dateutils.date_cast("Mon Dec 23 10:19:15 MST 2013")
        expected_ret = datetime.datetime(2013, 12, 23, 10, 19, 15)
        self.assertEqual(ret, expected_ret)

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
