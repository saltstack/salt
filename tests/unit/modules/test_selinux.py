# -*- coding: utf-8 -*-

# Import Salt Testing Libs
from __future__ import absolute_import
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
import salt.modules.selinux as selinux


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SelinuxModuleTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.selinux
    '''
    def setup_loader_modules(self):
        return {selinux: {}}

    def test_fcontext_get_policy_parsing(self):
        '''
        Test to verify that the parsing of the semanage output into fields is
        correct. Added with #45784.
        '''
        cases = [
            {
                'semanage_out': '/var/www(/.*)?     all files          system_u:object_r:httpd_sys_content_t:s0',
                'name': '/var/www(/.*)?',
                'filetype': 'all files',
                'sel_user': 'system_u',
                'sel_role': 'object_r',
                'sel_type': 'httpd_sys_content_t',
                'sel_level': 's0'
            },
            {
                'semanage_out': '/var/www(/.*)? all files          system_u:object_r:httpd_sys_content_t:s0',
                'name': '/var/www(/.*)?',
                'filetype': 'all files',
                'sel_user': 'system_u',
                'sel_role': 'object_r',
                'sel_type': 'httpd_sys_content_t',
                'sel_level': 's0'
            },
            {
                'semanage_out': '/var/lib/dhcp3?                                    directory          system_u:object_r:dhcp_state_t:s0',
                'name': '/var/lib/dhcp3?',
                'filetype': 'directory',
                'sel_user': 'system_u',
                'sel_role': 'object_r',
                'sel_type': 'dhcp_state_t',
                'sel_level': 's0'
            },
            {
                'semanage_out': '/var/lib/dhcp3?  directory          system_u:object_r:dhcp_state_t:s0',
                'name': '/var/lib/dhcp3?',
                'filetype': 'directory',
                'sel_user': 'system_u',
                'sel_role': 'object_r',
                'sel_type': 'dhcp_state_t',
                'sel_level': 's0'
            },
            {
                'semanage_out': '/var/lib/dhcp3? directory          system_u:object_r:dhcp_state_t:s0',
                'name': '/var/lib/dhcp3?',
                'filetype': 'directory',
                'sel_user': 'system_u',
                'sel_role': 'object_r',
                'sel_type': 'dhcp_state_t',
                'sel_level': 's0'
            }
        ]

        for case in cases:
            with patch.dict(selinux.__salt__, {'cmd.shell': MagicMock(return_value=case['semanage_out'])}):
                ret = selinux.fcontext_get_policy(case['name'])
                self.assertEqual(ret['filespec'], case['name'])
                self.assertEqual(ret['filetype'], case['filetype'])
                self.assertEqual(ret['sel_user'], case['sel_user'])
                self.assertEqual(ret['sel_role'], case['sel_role'])
                self.assertEqual(ret['sel_type'], case['sel_type'])
                self.assertEqual(ret['sel_level'], case['sel_level'])
