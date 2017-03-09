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
from salt.states import win_firewall
import salt.utils


# Globals
win_firewall.__salt__ = {}
win_firewall.__opts__ = {}


if salt.utils.is_windows():
    WINDOWS = True
else:
    WINDOWS = False


@skipIf(not WINDOWS, 'Only run if Windows')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinFirewallTestCase(TestCase):
    '''
        Validate the win_firewall state
    '''
    def test_disabled(self):
        '''
            Test to disable all the firewall profiles (Windows only)
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': None,
               'comment': ''}
        mock = MagicMock(return_value={})
        with patch.dict(win_firewall.__salt__, {"firewall.get_config": mock}):
            with patch.dict(win_firewall.__opts__, {"test": True}):
                self.assertDictEqual(win_firewall.disabled('salt'), ret)

            with patch.dict(win_firewall.__opts__, {"test": False}):
                ret.update({'comment': 'All the firewall profiles'
                            ' are disabled', 'result': True})
                self.assertDictEqual(win_firewall.disabled('salt'), ret)

    def test_add_rule(self):
        '''
            Test to add a new firewall rule (Windows only)
        '''
        ret = {'name': 'salt',
               'changes': {'new rule': 'salt'},
               'result': None,
               'comment': ''}
        mock = MagicMock(return_value=False)
        with patch.dict(win_firewall.__salt__, {"firewall.get_rule": mock}):
            with patch.dict(win_firewall.__opts__, {"test": True}):
                self.assertDictEqual(win_firewall.add_rule('salt', 'stack'),
                                     ret)
            with patch.dict(win_firewall.__opts__, {"test": False}):
                with patch.dict(win_firewall.__opts__, {"test": False}):
                    ret.update({'comment': 'A rule with that name already'
                                ' exists', 'result': True, 'changes': {}})
                    self.assertDictEqual(win_firewall.add_rule('salt',
                                                               'stack'), ret)
