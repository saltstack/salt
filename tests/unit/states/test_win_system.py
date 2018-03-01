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
import salt.states.win_system as win_system


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinSystemTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the win_system state
    '''
    def setup_loader_modules(self):
        return {win_system: {}}

    def test_computer_desc(self):
        '''
            Test to manage the computer's description field
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(side_effect=['salt', 'stack', 'stack'])
        with patch.dict(win_system.__salt__,
                        {"system.get_computer_desc": mock}):
            ret.update({'comment': "Computer description"
                        " already set to 'salt'"})
            self.assertDictEqual(win_system.computer_desc('salt'), ret)

            with patch.dict(win_system.__opts__, {"test": True}):
                ret.update({'result': None, 'comment': "Computer description"
                            " will be changed to 'salt'"})
                self.assertDictEqual(win_system.computer_desc('salt'), ret)

            with patch.dict(win_system.__opts__, {"test": False}):
                mock = MagicMock(return_value={'Computer Description': 'nfs'})
                with patch.dict(win_system.__salt__,
                                {"system.set_computer_desc": mock}):
                    ret.update({'result': False, 'comment': "Unable to set"
                                " computer description to 'salt'"})
                    self.assertDictEqual(win_system.computer_desc('salt'), ret)

    def test_computer_name(self):
        '''
            Test to manage the computer's name
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__,
                        {"system.get_computer_name": mock}):
            mock = MagicMock(side_effect=[None, 'SALT', 'Stack', 'stack'])
            with patch.dict(win_system.__salt__,
                            {"system.get_pending_computer_name": mock}):
                ret.update({'comment': "Computer name already set to 'salt'"})
                self.assertDictEqual(win_system.computer_name('salt'), ret)

                ret.update({'comment': "The current computer name"
                            " is 'salt', but will be changed to 'salt' on"
                            " the next reboot"})
                self.assertDictEqual(win_system.computer_name('salt'), ret)

                with patch.dict(win_system.__opts__, {"test": True}):
                    ret.update({'result': None, 'comment': "Computer name will"
                                " be changed to 'salt'"})
                    self.assertDictEqual(win_system.computer_name('salt'), ret)

                with patch.dict(win_system.__opts__, {"test": False}):
                    mock = MagicMock(return_value=False)
                    with patch.dict(win_system.__salt__,
                                    {"system.set_computer_name": mock}):
                        ret.update({'comment': "Unable to set computer name"
                                    " to 'salt'", 'result': False})
                        self.assertDictEqual(win_system.computer_name('salt'),
                                             ret)

    def test_hostname(self):
        ret = {
            'name': 'salt',
            'changes': {},
            'result': True,
            'comment': ''
        }

        mock = MagicMock(return_value='minion')
        with patch.dict(win_system.__salt__, {"system.get_hostname": mock}):
            mock = MagicMock(return_value=True)
            with patch.dict(win_system.__salt__, {"system.set_hostname": mock}):
                ret.update({'comment': "The current hostname is 'minion', "
                                       "but will be changed to 'salt' on the next reboot",
                            'changes': {'hostname': 'salt'}})
                self.assertDictEqual(win_system.hostname('salt'), ret)

            mock = MagicMock(return_value=False)
            with patch.dict(win_system.__salt__, {"system.set_hostname": mock}):
                ret.update({'comment': "Unable to set hostname",
                            'changes': {},
                            'result': False})
                self.assertDictEqual(win_system.hostname('salt'), ret)

        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {"system.get_hostname": mock}):
            ret.update({'comment': "Hostname is already set to 'salt'",
                            'changes': {},
                            'result': True})

            self.assertDictEqual(win_system.hostname('salt'), ret)

        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {"system.get_hostname": mock}):
            ret.update({'name': 'SALT',
                        'comment': "Hostname is already set to 'SALT'",
                        'changes': {},
                        'result': True})

            self.assertDictEqual(win_system.hostname('SALT'), ret)
