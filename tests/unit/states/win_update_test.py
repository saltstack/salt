# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import win_update


class MockPyWinUpdater(object):
    '''
        Mock PyWinUpdater class
    '''
    def __init__(self):
        pass

    @staticmethod
    def SetCategories(arg):
        '''
            Mock SetCategories
        '''
        return arg

    @staticmethod
    def SetIncludes(arg):
        '''
            Mock SetIncludes
        '''
        return arg

    @staticmethod
    def GetInstallationResults():
        '''
            Mock GetInstallationResults
        '''
        return True

    @staticmethod
    def GetDownloadResults():
        '''
            Mock GetDownloadResults
        '''
        return True

    @staticmethod
    def SetSkips(arg):
        return True


@patch('salt.states.win_update.PyWinUpdater', MockPyWinUpdater)
@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinUpdateTestCase(TestCase):
    '''
        Validate the win_update state
    '''
    def test_installed(self):
        '''
            Test to install specified windows updates
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}

        mock = MagicMock(side_effect=[['Saltstack', False, 5],
                                      ['Saltstack', True, 5],
                                      ['Saltstack', True, 5],
                                      ['Saltstack', True, 5]])
        with patch.object(win_update, '_search', mock):
            ret.update({'comment': 'Saltstack'})
            self.assertDictEqual(win_update.installed('salt'), ret)

            mock = MagicMock(side_effect=[['dude', False, 5],
                                          ['dude', True, 5],
                                          ['dude', True, 5]])
            with patch.object(win_update, '_download', mock):
                ret.update({'comment': 'Saltstackdude'})
                self.assertDictEqual(win_update.installed('salt'), ret)

                mock = MagicMock(side_effect=[['@Me', False, 5],
                                              ['@Me', True, 5]])
                with patch.object(win_update, '_install', mock):
                    ret.update({'comment': 'Saltstackdude@Me'})
                    self.assertDictEqual(win_update.installed('salt'), ret)

                    ret.update({'changes': True, 'result': True})
                    self.assertDictEqual(win_update.installed('salt'), ret)

    def test_downloaded(self):
        '''
            Test to cache updates for later install.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}

        mock = MagicMock(side_effect=[['Saltstack', False, 5],
                                      ['Saltstack', True, 5],
                                      ['Saltstack', True, 5]])
        with patch.object(win_update, '_search', mock):
            ret.update({'comment': 'Saltstack'})
            self.assertDictEqual(win_update.downloaded('salt'), ret)

            mock = MagicMock(side_effect=[['dude', False, 5],
                                          ['dude', True, 5]])
            with patch.object(win_update, '_download', mock):
                ret.update({'comment': 'Saltstackdude'})
                self.assertDictEqual(win_update.downloaded('salt'), ret)

                ret.update({'changes': True, 'result': True})
                self.assertDictEqual(win_update.downloaded('salt'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinUpdateTestCase, needs_daemon=False)
