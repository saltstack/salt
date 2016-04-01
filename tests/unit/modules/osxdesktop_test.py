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
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import osxdesktop

# Globals
osxdesktop.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class OsxDesktopTestCase(TestCase):
    '''
    Test cases for salt.modules.osxdesktop
    '''
    # 'get_output_volume' function tests: 1

    def test_get_output_volume(self):
        '''
        Test if it get the output volume (range 0 to 100)
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(osxdesktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(osxdesktop.get_output_volume())

    # 'set_output_volume' function tests: 1

    def test_set_output_volume(self):
        '''
        Test if it set the volume of sound (range 0 to 100)
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(osxdesktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(osxdesktop.set_output_volume('my-volume'))

    # 'screensaver' function tests: 1

    def test_screensaver(self):
        '''
        Test if it launch the screensaver
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(osxdesktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(osxdesktop.screensaver())

    # 'lock' function tests: 1

    def test_lock(self):
        '''
        Test if it lock the desktop session
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(osxdesktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(osxdesktop.lock())

    # 'say' function tests: 1

    def test_say(self):
        '''
        Test if it says some words.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(osxdesktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(osxdesktop.say())


if __name__ == '__main__':
    from integration import run_tests
    run_tests(OsxDesktopTestCase, needs_daemon=False)
