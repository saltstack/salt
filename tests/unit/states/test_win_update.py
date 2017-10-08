# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.states.win_update as win_update


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


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinUpdateTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the win_update state
    '''
    def setup_loader_modules(self):
        return {win_update: {'PyWinUpdater': MockPyWinUpdater}}

    def test_installed(self):
        '''
            Test to install specified windows updates
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': '',
               'warnings': ["The 'win_update' module is deprecated, and will "
                            "be removed in Salt Fluorine. Please use the "
                            "'win_wua' module instead."]}

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
               'comment': '',
               'warnings': ["The 'win_update' module is deprecated, and will "
                            "be removed in Salt Fluorine. Please use the "
                            "'win_wua' module instead."]}

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
