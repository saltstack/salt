# -*- coding: utf-8 -*-
'''
Unit tests for the LGPO module
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Libs
import salt.modules.win_lgpo as win_lgpo
import salt.utils.platform

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch


@skipIf(not salt.utils.platform.is_windows(), 'Not a Windows system')
class WinLgpoNetShTestCase(TestCase, LoaderModuleMockMixin):
    '''
    NetSH test cases
    '''

    def setup_loader_modules(self):
        return {win_lgpo: {
            '__context__': {}
        }}

    def test__set_netsh_value_firewall(self):
        '''
        Test setting the firewall inbound policy
        '''
        context = {
            'lgpo.netsh_data': {
                'Private': {
                    'Inbound': 'Block'}}}
        expected = {
            'lgpo.netsh_data': {
                'Private': {
                    'Inbound': 'Allow'}}}
        with patch('salt.utils.win_lgpo_netsh.set_firewall_settings',
                   MagicMock(return_value=True)),\
                patch.dict(win_lgpo.__context__, context):
            result = win_lgpo._set_netsh_value(profile='Private',
                                               section='firewallpolicy',
                                               option='Inbound',
                                               value='Allow')
            self.assertTrue(result)
            self.assertEqual(win_lgpo.__context__, expected)

    def test__set_netsh_value_settings(self):
        '''
        Test setting firewall settings
        '''
        context = {
            'lgpo.netsh_data': {
                'private': {
                    'localfirewallrules': 'disable'}}}
        expected = {
            'lgpo.netsh_data': {
                'private': {
                    'localfirewallrules': 'enable'}}}
        with patch('salt.utils.win_lgpo_netsh.set_settings',
                   MagicMock(return_value=True)), \
                patch.dict(win_lgpo.__context__, context):
            result = win_lgpo._set_netsh_value(profile='private',
                                               section='settings',
                                               option='localfirewallrules',
                                               value='enable')
            self.assertTrue(result)
            self.assertEqual(win_lgpo.__context__, expected)

    def test__set_netsh_value_state(self):
        '''
        Test setting the firewall state
        '''
        context = {
            'lgpo.netsh_data': {
                'private': {
                    'State': 'notconfigured'}}}
        expected = {
            'lgpo.netsh_data': {
                'private': {
                    'State': 'on'}}}
        with patch('salt.utils.win_lgpo_netsh.set_state',
                   MagicMock(return_value=True)), \
                patch.dict(win_lgpo.__context__, context):
            result = win_lgpo._set_netsh_value(profile='private',
                                               section='state',
                                               option='unused',
                                               value='on')
            self.assertTrue(result)
            self.assertEqual(win_lgpo.__context__, expected)

    def test__set_netsh_value_logging(self):
        '''
        Test setting firewall logging
        '''
        context = {
            'lgpo.netsh_data': {
                'private': {
                    'allowedconnections': 'notconfigured'}}}
        expected = {
            'lgpo.netsh_data': {
                'private': {
                    'allowedconnections': 'enable'}}}
        with patch('salt.utils.win_lgpo_netsh.set_logging_settings',
                   MagicMock(return_value=True)), \
                patch.dict(win_lgpo.__context__, context):
            result = win_lgpo._set_netsh_value(profile='private',
                                               section='logging',
                                               option='allowedconnections',
                                               value='enable')
            self.assertTrue(result)
            self.assertEqual(win_lgpo.__context__, expected)


class WinLgpoSeceditTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Secedit test cases
    '''

    @classmethod
    def setUpClass(cls):
        cls.secedit_data = [
            '[Unicode]',
            'Unicode=yes',
            '[System Access]',
            'MinimumPasswordAge = 0',
            'MaximumPasswordAge = 42',
            '[Event Audit]',
            'AuditSystemEvents = 0',
            'AuditLogonEvents = 0',
            '[Registry Values]',
            r'MACHINE\Software\Microsoft\Windows NT\CurrentVersion\Setup\RecoveryConsole\SecurityLevel=4,0',
            r'MACHINE\Software\Microsoft\Windows NT\CurrentVersion\Setup\RecoveryConsole\SetCommand=4,0',
            '[Privilege Rights]',
            'SeNetworkLogonRight = *S-1-1-0,*S-1-5-32-544,*S-1-5-32-545,*S-1-5-32-551',
            'SeBackupPrivilege = *S-1-5-32-544,*S-1-5-32-551',
            '[Version]',
            'signature="$CHICAGO$"',
            'Revision=1']

    @classmethod
    def tearDownClass(cls):
        del cls.secedit_data

    def setup_loader_modules(self):
        return {win_lgpo: {
            '__context__': {},
            '__opts__': {'cachedir': 'C:\\cachedir'},
            '__salt__': {}
        }}

    def test__get_secedit_data(self):
        '''
        Test getting secedit data and loading it into __context__
        '''
        expected = {
            'AuditLogonEvents': '0',
            'AuditSystemEvents': '0',
            r'MACHINE\Software\Microsoft\Windows NT\CurrentVersion\Setup\RecoveryConsole\SecurityLevel': '4,0',
            r'MACHINE\Software\Microsoft\Windows NT\CurrentVersion\Setup\RecoveryConsole\SetCommand': '4,0',
            'MaximumPasswordAge': '42',
            'MinimumPasswordAge': '0',
            'Revision': '1',
            'SeBackupPrivilege': '*S-1-5-32-544,*S-1-5-32-551',
            'SeNetworkLogonRight': '*S-1-1-0,*S-1-5-32-544,*S-1-5-32-545,*S-1-5-32-551',
            'Unicode': 'yes',
            'signature': '"$CHICAGO$"'}
        with patch.object(win_lgpo, '_load_secedit_data',
                          MagicMock(return_value=self.secedit_data)):
            result = win_lgpo._get_secedit_data()
            self.assertDictEqual(result, expected)
            self.assertDictEqual(win_lgpo.__context__['lgpo.secedit_data'],
                                 expected)

    def test__get_secedit_value(self):
        '''
        Test getting a specific secedit value
        '''
        with patch.object(win_lgpo, '_load_secedit_data',
                          MagicMock(return_value=self.secedit_data)):
            result = win_lgpo._get_secedit_value('AuditSystemEvents')
            self.assertEqual(result, '0')

    def test__get_secedit_value_not_defined(self):
        '''
        Test getting a secedit value that is undefined
        '''
        with patch.object(win_lgpo, '_load_secedit_data',
                          MagicMock(return_value=self.secedit_data)):
            result = win_lgpo._get_secedit_value('UndefinedKey')
            self.assertEqual(result, 'Not Defined')

    def test__write_secedit_data(self):
        '''
        Test writing secedit data and updating the __context__
        '''
        mock_true = MagicMock(return_value=True)
        mock_false = MagicMock(return_value=False)
        mock_retcode = MagicMock(return_value=0)
        new_secedit_data = {'System Access': ['MaximumPasswordAge=100']}
        with patch.object(win_lgpo, '_load_secedit_data',
                          MagicMock(return_value=self.secedit_data)),\
                patch.dict(win_lgpo.__salt__, {'file.write': mock_true,
                                               'file.file_exists': mock_false,
                                               'cmd.retcode': mock_retcode}):
            # Populate __context__['lgpo.secedit_data']
            # It will have been run before this function is called
            win_lgpo._get_secedit_data()
            self.assertEqual(
                win_lgpo.__context__['lgpo.secedit_data']['MaximumPasswordAge'],
                '42')
            result = win_lgpo._write_secedit_data(new_secedit_data)
            self.assertTrue(result)
            self.assertEqual(
                win_lgpo.__context__['lgpo.secedit_data']['MaximumPasswordAge'],
                '100')
