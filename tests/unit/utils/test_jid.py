"""
Tests for salt.utils.jid
"""


import datetime
import os

import salt.utils.jid
from tests.support.mock import patch
from tests.support.unit import TestCase


class JidTestCase(TestCase):
    def test_jid_to_time(self):
        test_jid = 20131219110700123489
        expected_jid = "2013, Dec 19 11:07:00.123489"
        self.assertEqual(salt.utils.jid.jid_to_time(test_jid), expected_jid)

        # Test incorrect lengths
        incorrect_jid_length = 2012
        self.assertEqual(salt.utils.jid.jid_to_time(incorrect_jid_length), "")

    def test_is_jid(self):
        self.assertTrue(salt.utils.jid.is_jid("20131219110700123489"))  # Valid JID
        self.assertFalse(salt.utils.jid.is_jid(20131219110700123489))  # int
        self.assertFalse(
            salt.utils.jid.is_jid("2013121911070012348911111")
        )  # Wrong length

    def test_gen_jid(self):
        now = datetime.datetime(2002, 12, 25, 12, 0, 0, 0)
        with patch("salt.utils.jid._utc_now", return_value=now):
            ret = salt.utils.jid.gen_jid({})
            self.assertEqual(ret, "20021225120000000000")
            with patch("salt.utils.jid.LAST_JID_DATETIME", None):
                ret = salt.utils.jid.gen_jid({"unique_jid": True})
                self.assertEqual(ret, "20021225120000000000_{}".format(os.getpid()))
                ret = salt.utils.jid.gen_jid({"unique_jid": True})
                self.assertEqual(ret, "20021225120000000001_{}".format(os.getpid()))

    def test_deprecation_58225(self):
        # check that type error will be raised
        self.assertRaises(TypeError, salt.utils.jid.gen_jid)

        # check that opts is missing and not another arg
        try:
            salt.utils.jid.gen_jid()  # pylint: disable=no-value-for-parameter
        except TypeError as no_opts:
            self.assertEqual(
                str(no_opts), "gen_jid() missing 1 required positional argument: 'opts'"
            )
