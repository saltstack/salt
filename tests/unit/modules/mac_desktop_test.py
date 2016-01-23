# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import mac_desktop

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

# Globals
mac_desktop.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MacDesktopTestCase(TestCase):
    '''
    Test cases for salt.modules.mac_desktop
    '''
    # 'get_output_volume' function tests: 1

    def test_get_output_volume(self):
        '''
        Test if it get the output volume (range 0 to 100)
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(mac_desktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(mac_desktop.get_output_volume())

    # 'set_output_volume' function tests: 1

    def test_set_output_volume(self):
        '''
        Test if it set the volume of sound (range 0 to 100)
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(mac_desktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(mac_desktop.set_output_volume('my-volume'))

    # 'screensaver' function tests: 1

    def test_screensaver(self):
        '''
        Test if it launch the screensaver
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(mac_desktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(mac_desktop.screensaver())

    # 'lock' function tests: 1

    def test_lock(self):
        '''
        Test if it lock the desktop session
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(mac_desktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(mac_desktop.lock())

    # 'say' function tests: 1

    def test_say(self):
        '''
        Test if it says some words.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(mac_desktop.__salt__, {'cmd.run': mock}):
            self.assertTrue(mac_desktop.say())


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacDesktopTestCase, needs_daemon=False)
