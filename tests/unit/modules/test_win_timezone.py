# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import win_timezone

# Globals
win_timezone.__salt__ = {}

# Make sure this module runs on Windows system
IS_WIN = win_timezone.__virtual__()


@skipIf(not IS_WIN, "This test case runs only on Windows system")
class WinTimezoneTestCase(TestCase):
    '''
    Test cases for salt.modules.win_timezone
    '''
    # 'get_zone' function tests: 1

    def test_get_zone(self):
        '''
        Test if it get current timezone (i.e. Asia/Calcutta)
        '''
        mock_cmd = MagicMock(side_effect=['India Standard Time',
                                          'Indian Standard Time'])
        with patch.dict(win_timezone.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(win_timezone.get_zone(), 'Asia/Calcutta')

            self.assertFalse(win_timezone.get_zone())

    # 'get_offset' function tests: 1

    def test_get_offset(self):
        '''
        Test if it get current numeric timezone offset from UCT (i.e. +0530)
        '''
        time = ('(UTC+05:30) Chennai, Kolkata, Mumbai, \
        New Delhi\nIndia Standard Time')
        mock_cmd = MagicMock(side_effect=['India Standard Time', time])
        with patch.dict(win_timezone.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(win_timezone.get_offset(), '+0530')

        mock_cmd = MagicMock(return_value='India Standard Time')
        with patch.dict(win_timezone.__salt__, {'cmd.run': mock_cmd}):
            self.assertFalse(win_timezone.get_offset())

    # 'get_zonecode' function tests: 1

    def test_get_zonecode(self):
        '''
        Test if it get current timezone (i.e. PST, MDT, etc)
        '''
        self.assertFalse(win_timezone.get_zonecode())

    # 'set_zone' function tests: 1

    def test_set_zone(self):
        '''
        Test if it unlinks, then symlinks /etc/localtime to the set timezone.
        '''
        mock_cmd = MagicMock(return_value=0)
        with patch.dict(win_timezone.__salt__, {'cmd.retcode': mock_cmd}):
            self.assertTrue(win_timezone.set_zone('Asia/Calcutta'))

    # 'zone_compare' function tests: 1

    def test_zone_compare(self):
        '''
        Test if it checks the md5sum between the given timezone, and
        the one set in /etc/localtime. Returns True if they match,
        and False if not. Mostly useful for running state checks.
        '''
        mock_cmd = MagicMock(return_value='India Standard Time')
        with patch.dict(win_timezone.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_timezone.zone_compare('Asia/Calcutta'))

    # 'get_hwclock' function tests: 1

    def test_get_hwclock(self):
        '''
        Test if it get current hardware clock setting (UTC or localtime)
        '''
        self.assertEqual(win_timezone.get_hwclock(), 'localtime')

    # 'set_hwclock' function tests: 1

    def test_set_hwclock(self):
        '''
        Test if it sets the hardware clock to be either UTC or localtime
        '''
        self.assertFalse(win_timezone.set_hwclock('UTC'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinTimezoneTestCase, needs_daemon=False)
