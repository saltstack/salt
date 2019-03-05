# -*- coding: utf-8 -*-
'''
Tests for salt.utils.jid
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
import datetime
import os

# Import Salt libs
import salt.utils.jid
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)


class JidTestCase(TestCase):
    def test_jid_to_time(self):
        test_jid = 20131219110700123489
        expected_jid = '2013, Dec 19 11:07:00.123489'
        self.assertEqual(salt.utils.jid.jid_to_time(test_jid), expected_jid)

        # Test incorrect lengths
        incorrect_jid_length = 2012
        self.assertEqual(salt.utils.jid.jid_to_time(incorrect_jid_length), '')

    def test_is_jid(self):
        self.assertTrue(salt.utils.jid.is_jid('20131219110700123489'))  # Valid JID
        self.assertFalse(salt.utils.jid.is_jid(20131219110700123489))  # int
        self.assertFalse(salt.utils.jid.is_jid('2013121911070012348911111'))  # Wrong length

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_gen_jid(self):
        now = datetime.datetime(2002, 12, 25, 12, 00, 00, 00)
        with patch('datetime.datetime'):
            datetime.datetime.now.return_value = now
            ret = salt.utils.jid.gen_jid({})
            self.assertEqual(ret, '20021225120000000000')
            salt.utils.jid.LAST_JID_DATETIME = None
            ret = salt.utils.jid.gen_jid({'unique_jid': True})
            self.assertEqual(ret, '20021225120000000000_{0}'.format(os.getpid()))
            ret = salt.utils.jid.gen_jid({'unique_jid': True})
            self.assertEqual(ret, '20021225120000000001_{0}'.format(os.getpid()))
