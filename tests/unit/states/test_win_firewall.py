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
import salt.states.win_firewall as win_firewall


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinFirewallTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the win_firewall state
    '''
    def setup_loader_modules(self):
        return {win_firewall: {}}

    def test_disabled(self):
        '''
            Test to disable all the firewall profiles (Windows only)
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(return_value={'salt': '', 'foo': ''})
        with patch.dict(win_firewall.__salt__, {'firewall.get_config': mock}):
            with patch.dict(win_firewall.__opts__, {'test': True}):
                self.assertDictEqual(win_firewall.disabled('salt'), ret)

            with patch.dict(win_firewall.__opts__, {'test': False}):
                ret.update({'comment': 'Firewall profile salt is disabled',
                            'result': True})
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
        add_rule_mock = MagicMock(return_value=True)
        with patch.dict(win_firewall.__salt__, {'firewall.get_rule': mock,
                                                'firewall.add_rule': add_rule_mock}):
            with patch.dict(win_firewall.__opts__, {'test': True}):
                self.assertDictEqual(win_firewall.add_rule('salt', 'stack'), ret)
            with patch.dict(win_firewall.__opts__, {'test': False}):
                with patch.dict(win_firewall.__opts__, {'test': False}):
                    ret.update({'result': True})
                    result = win_firewall.add_rule('salt', 'stack')
                    self.assertDictEqual(result, ret)
