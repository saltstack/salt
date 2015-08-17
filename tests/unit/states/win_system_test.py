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
from salt.states import win_system

# Globals
win_system.__salt__ = {}
win_system.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinSystemTestCase(TestCase):
    '''
        Validate the win_system state
    '''
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
        ret = {'name': 'SALT',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(return_value='SALT')
        with patch.dict(win_system.__salt__,
                        {"system.get_computer_name": mock}):
            mock = MagicMock(side_effect=[None, 'SALT', 'Stack', 'stack'])
            with patch.dict(win_system.__salt__,
                            {"system.get_pending_computer_name": mock}):
                ret.update({'comment': "Computer name already set to 'SALT'"})
                self.assertDictEqual(win_system.computer_name('salt'), ret)

                ret.update({'comment': "The current computer name"
                            " is 'SALT', but will be changed to 'SALT' on"
                            " the next reboot"})
                self.assertDictEqual(win_system.computer_name('salt'), ret)

                with patch.dict(win_system.__opts__, {"test": True}):
                    ret.update({'result': None, 'comment': "Computer name will"
                                " be changed to 'SALT'"})
                    self.assertDictEqual(win_system.computer_name('salt'), ret)

                with patch.dict(win_system.__opts__, {"test": False}):
                    mock = MagicMock(return_value=False)
                    with patch.dict(win_system.__salt__,
                                    {"system.set_computer_name": mock}):
                        ret.update({'comment': "Unable to set computer name"
                                    " to 'SALT'", 'result': False})
                        self.assertDictEqual(win_system.computer_name('salt'),
                                             ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinSystemTestCase, needs_daemon=False)
