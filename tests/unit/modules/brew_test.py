# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@satlstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.mock import MagicMock, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import brew

# Global Variables
brew.__salt__ = {}

TAPS_STRING = 'homebrew/dupes\nhomebrew/science\nhomebrew/x11'
TAPS_LIST = ['homebrew/dupes', 'homebrew/science', 'homebrew/x11']


class BrewTestCase(TestCase):
    '''
    TestCase for salt.modules.brew module
    '''

    def test_list_taps(self):
        '''
        Tests the return of the list of taps
        '''
        mock_taps = MagicMock(return_value=TAPS_STRING)
        with patch.dict(brew.__salt__, {'cmd.run': mock_taps}):
            self.assertEqual(brew._list_taps(), TAPS_LIST)

    @patch('salt.modules.brew._list_taps', MagicMock(return_value=TAPS_LIST))
    def test_tap_installed(self):
        '''
        Tests if tap argument is already installed or not
        '''
        self.assertTrue(brew._tap('homebrew/science'))

    @patch('salt.modules.brew._list_taps', MagicMock(return_value={}))
    def test_tap_failure(self):
        '''
        Tests if the tap installation failed
        '''
        mock_failure = MagicMock(return_value=1)
        with patch.dict(brew.__salt__, {'cmd.retcode': mock_failure}):
            self.assertFalse(brew._tap('homebrew/test'))

    @patch('salt.modules.brew._list_taps', MagicMock(return_value=TAPS_LIST))
    def test_tap(self):
        '''
        Tests adding unofficial Github repos to the list of brew taps
        '''
        mock_success = MagicMock(return_value=0)
        with patch.dict(brew.__salt__, {'cmd.retcode': mock_success}):
            self.assertTrue(brew._tap('homebrew/test'))

    def test_homebrew_bin(self):
        '''
        Tests the path to the homebrew binary
        '''
        mock_path = MagicMock(return_value='/usr/local')
        with patch.dict(brew.__salt__, {'cmd.run': mock_path}):
            self.assertEqual(brew._homebrew_bin(), '/usr/local/bin/brew')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BrewTestCase, needs_daemon=False)
