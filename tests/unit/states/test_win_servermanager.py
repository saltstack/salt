# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.states import win_servermanager

# Globals
win_servermanager.__salt__ = {}
win_servermanager.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinServermanagerTestCase(TestCase):
    '''
        Validate the win_servermanager state
    '''
    def test_installed(self):
        '''
            Test to install the windows feature
        '''
        mock_list = MagicMock(
            side_effect=[{'spongebob': 'squarepants'},
                         {'squidward': 'patrick'},
                         {'spongebob': 'squarepants'},
                         {'spongebob': 'squarepants',
                          'squidward': 'patrick'}])
        mock_install = MagicMock(
            return_value={'Success': True,
                          'RestartNeeded': False,
                          'ExitCode': 1234})
        with patch.dict(win_servermanager.__salt__,
                        {"win_servermanager.list_installed": mock_list,
                         "win_servermanager.install": mock_install}):
            ret = {'name': 'spongebob',
                   'changes': {},
                   'result': True,
                   'comment': 'The feature spongebob is already installed'}
            self.assertDictEqual(win_servermanager.installed('spongebob'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": True}):
                ret = {'name': 'spongebob',
                       'result': None,
                       'comment': '',
                       'changes': {
                           'feature': 'spongebob will be installed '
                                      'recurse=False'}}
                self.assertDictEqual(
                    win_servermanager.installed('spongebob'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": False}):
                ret = {'name': 'squidward',
                       'result': True,
                       'comment': 'Installed squidward',
                       'changes': {
                           'Success': True,
                           'RestartNeeded': False,
                           'ExitCode': 1234,
                           'feature': {'squidward': {'new': 'patrick',
                                                     'old': ''}}}}
                self.assertDictEqual(
                    win_servermanager.installed('squidward'), ret)

    def test_removed(self):
        '''
            Test to remove the windows feature
        '''
        mock_list = MagicMock(
            side_effect=[{'spongebob': 'squarepants'},
                         {'squidward': 'patrick'},
                         {'spongebob': 'squarepants',
                          'squidward': 'patrick'},
                         {'spongebob': 'squarepants'}])
        mock_remove = MagicMock(
            return_value={'Success': True,
                          'RestartNeeded': False,
                          'ExitCode': 1234})
        with patch.dict(win_servermanager.__salt__,
                        {"win_servermanager.list_installed": mock_list,
                         "win_servermanager.remove": mock_remove}):
            ret = {'name': 'squidward',
                   'changes': {},
                   'result': True,
                   'comment': 'The feature squidward is not installed'}
            self.assertDictEqual(
                win_servermanager.removed('squidward'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": True}):
                ret = {'name': 'squidward',
                       'result': None,
                       'comment': '',
                       'changes': {'feature': 'squidward will be removed'}}
                self.assertDictEqual(
                    win_servermanager.removed('squidward'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": False}):
                ret = {'name': 'squidward',
                       'result': True,
                       'comment': 'Removed squidward',
                       'changes': {
                           'Success': True,
                           'RestartNeeded': False,
                           'ExitCode': 1234,
                           'feature': {'squidward': {'new': '',
                                                     'old': 'patrick'}}}}
                self.assertDictEqual(
                    win_servermanager.removed('squidward'), ret)
