# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

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
import salt.states.win_servermanager as win_servermanager


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinServermanagerTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the win_servermanager state
    '''
    def setup_loader_modules(self):
        return {win_servermanager: {}}

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
                          'Restarted': False,
                          'RestartNeeded': False,
                          'ExitCode': 1234,
                          'Features': {
                              'squidward': {
                                  'DisplayName': 'Squidward',
                                  'Message': '',
                                  'RestartNeeded': True,
                                  'SkipReason': 0,
                                  'Success': True
                              }
                          }})
        with patch.dict(win_servermanager.__salt__,
                        {"win_servermanager.list_installed": mock_list,
                         "win_servermanager.install": mock_install}):
            ret = {'name': 'spongebob',
                   'changes': {},
                   'result': True,
                   'comment': 'The following features are already installed:\n'
                              '- spongebob'}
            self.assertDictEqual(win_servermanager.installed('spongebob'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": True}):
                ret = {'name': 'spongebob',
                       'result': None,
                       'comment': '',
                       'changes': {
                           'spongebob': 'Will be installed recurse=False'}}
                self.assertDictEqual(
                    win_servermanager.installed('spongebob'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": False}):
                ret = {'name': 'squidward',
                       'result': True,
                       'comment': 'Installed the following:\n- squidward',
                       'changes': {
                           'squidward': {'new': 'patrick', 'old': ''}}}
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
                          'Restarted': False,
                          'ExitCode': 1234,
                          'Features': {
                              'squidward': {
                                  'DisplayName': 'Squidward',
                                  'Message': '',
                                  'RestartNeeded': True,
                                  'SkipReason': 0,
                                  'Success': True
                              }
                          }})
        with patch.dict(win_servermanager.__salt__,
                        {"win_servermanager.list_installed": mock_list,
                         "win_servermanager.remove": mock_remove}):
            ret = {'name': 'squidward',
                   'changes': {},
                   'result': True,
                   'comment': 'The following features are not installed:\n'
                              '- squidward'}
            self.assertDictEqual(
                win_servermanager.removed('squidward'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": True}):
                ret = {'name': 'squidward',
                       'result': None,
                       'comment': '',
                       'changes': {'squidward': 'Will be removed'}}
                self.assertDictEqual(
                    win_servermanager.removed('squidward'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": False}):
                ret = {'name': 'squidward',
                       'result': True,
                       'comment': 'Removed the following:\n- squidward',
                       'changes': {
                           'squidward': {'new': '', 'old': 'patrick'}}}
                self.assertDictEqual(
                    win_servermanager.removed('squidward'), ret)
