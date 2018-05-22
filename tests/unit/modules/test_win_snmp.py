# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for Windows SNMP Module 'module.win_snmp'
    :platform: Windows
    :maturity: develop
    .. versionadded:: 2017.7.0
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Libs
import salt.modules.win_snmp as win_snmp

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

COMMUNITY_NAMES = {'TestCommunity': 'Read Create'}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinSnmpTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.win_snmp
    '''
    def setup_loader_modules(self):
        return {win_snmp: {}}

    def test_get_agent_service_types(self):
        '''
        Test - Get the sysServices types that can be configured.
        '''
        with patch.dict(win_snmp.__salt__):
            self.assertIsInstance(win_snmp.get_agent_service_types(), list)

    def test_get_permission_types(self):
        '''
        Test - Get the permission types that can be configured for communities.
        '''
        with patch.dict(win_snmp.__salt__):
            self.assertIsInstance(win_snmp.get_permission_types(), list)

    def test_get_auth_traps_enabled(self):
        '''
        Test - Determine whether the host is configured to send authentication traps.
        '''
        mock_value = MagicMock(return_value={'vdata': 1})
        with patch.dict(win_snmp.__salt__, {'reg.read_value': mock_value}):
            self.assertTrue(win_snmp.get_auth_traps_enabled())

    def test_set_auth_traps_enabled(self):
        '''
        Test - Manage the sending of authentication traps.
        '''
        mock_value = MagicMock(return_value=True)
        kwargs = {'status': True}
        with patch.dict(win_snmp.__salt__, {'reg.set_value': mock_value}), \
                patch('salt.modules.win_snmp.get_auth_traps_enabled',
                      MagicMock(return_value=True)):
            self.assertTrue(win_snmp.set_auth_traps_enabled(**kwargs))

    def test_get_community_names(self):
        '''
        Test - Get the current accepted SNMP community names and their permissions.
        '''
        mock_value = MagicMock(return_value=[{'vdata': 16,
                                              'vname': 'TestCommunity'}])
        with patch.dict(win_snmp.__salt__, {'reg.list_values': mock_value}):
            self.assertEqual(win_snmp.get_community_names(),
                             COMMUNITY_NAMES)

    def test_set_community_names(self):
        '''
        Test - Manage the SNMP accepted community names and their permissions.
        '''
        mock_value = MagicMock(return_value=True)
        kwargs = {'communities': COMMUNITY_NAMES}
        with patch.dict(win_snmp.__salt__, {'reg.set_value': mock_value}), \
                patch('salt.modules.win_snmp.get_community_names',
                      MagicMock(return_value=COMMUNITY_NAMES)):
            self.assertTrue(win_snmp.set_community_names(**kwargs))
