# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import win_servermanager

# Globals
win_servermanager.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinServermanagerTestCase(TestCase):
    '''
    Test cases for salt.modules.win_servermanager
    '''
    def test_list_available(self):
        '''
        Test win_servermanager.list_available
        '''
        mock = MagicMock(return_value='')
        with patch.dict(win_servermanager.__salt__, {'cmd.shell': mock}):
            self.assertEqual(win_servermanager.list_available(), '')

    def test_list_installed(self):
        '''
        Test win_servermanager.list_installed
        '''
        mock = MagicMock(return_value=[{'Installed': True,
                                        'Name': 'Spongebob',
                                        'DisplayName': 'Square Pants'},
                                       {'Installed': False,
                                        'Name': 'Patrick',
                                        'DisplayName': 'Plankton'}])
        with patch.object(win_servermanager, '_pshell_json', mock):
            expected = {'Spongebob': 'Square Pants'}
            self.assertDictEqual(win_servermanager.list_installed(), expected)

    def test_install(self):
        '''
        Test win_servermanager.install
        '''
        mock = MagicMock(return_value={'ExitCode': 0,
                                       'Success': True,
                                       'FeatureResult':
                                           [{'DisplayName': 'Spongebob',
                                             'RestartNeeded': False}]})
        with patch.object(win_servermanager, '_pshell_json', mock):
            expected = {'ExitCode': 0,
                        'DisplayName': 'Spongebob',
                        'RestartNeeded': False,
                        'Success': True}
            self.assertDictEqual(
                win_servermanager.install('Telnet-Client'), expected)

    def test_remove(self):
        '''
        Test win_servermanager.remove
        '''
        mock = MagicMock(return_value={'ExitCode': 0,
                                       'Success': True,
                                       'FeatureResult':
                                           [{'DisplayName': 'Spongebob',
                                             'RestartNeeded': False}]})
        with patch.object(win_servermanager, '_pshell_json', mock):
            expected = {'ExitCode': 0,
                        'DisplayName': 'Spongebob',
                        'RestartNeeded': False,
                        'Success': True}
            self.assertDictEqual(
                win_servermanager.remove('Telnet-Client'), expected)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinServermanagerTestCase, needs_daemon=False)
