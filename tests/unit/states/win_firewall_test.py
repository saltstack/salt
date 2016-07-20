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
from salt.states import win_firewall

# Globals
win_firewall.__salt__ = {}
win_firewall.__opts__ = {}


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
               'changes': {},
               'result': None,
               'comment': ''}
        mock = MagicMock(return_value=True)
        with patch.dict(win_firewall.__salt__, {"firewall.get_rule": mock}):
            with patch.dict(win_firewall.__opts__, {"test": True}):
                self.assertDictEqual(win_firewall.add_rule('salt', 'stack'),
                                     ret)
            with patch.dict(win_firewall.__opts__, {"test": False}):
                with patch.dict(win_firewall.__opts__, {"test": False}):
                    ret.update({'comment': 'A rule with that name already'
                                ' exists', 'result': True})
                    self.assertDictEqual(win_firewall.add_rule('salt',
                                                               'stack'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinFirewallTestCase, needs_daemon=False)
