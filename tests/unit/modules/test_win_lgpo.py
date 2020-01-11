# -*- coding: utf-8 -*-
'''
:codeauthor: Shane Lee <slee@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import os

# Import Salt Testing Libs
from tests.support.helpers import destructiveTest
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.config
import salt.modules.cmdmod
import salt.modules.file
import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo
import salt.utils.platform
import salt.utils.win_dacl
import salt.utils.win_lgpo_auditpol
import salt.utils.win_reg

LOADER_DICTS = {
    win_lgpo: {
        '__salt__': {
            'file.file_exists': salt.modules.file.file_exists,
            'file.makedirs': win_file.makedirs_,
            'file.write': salt.modules.file.write,
            'file.remove': win_file.remove,
            'cmd.run': salt.modules.cmdmod.run},
        '__opts__': salt.config.DEFAULT_MINION_OPTS.copy(),
        '__utils__': {
            'reg.read_value': salt.utils.win_reg.read_value,
            'auditpol.get_auditpol_dump':
                salt.utils.win_lgpo_auditpol.get_auditpol_dump}},
    win_file: {
        '__utils__': {
            'dacl.set_perms': salt.utils.win_dacl.set_perms}}}


class WinLGPOTestCase(TestCase):
    '''
    Test cases for salt.modules.win_lgpo
    '''
    encoded_null = chr(0).encode('utf-16-le')

    def test__getAdmlDisplayName(self):
        display_name = '$(string.KeepAliveTime1)'
        adml_xml_data = 'junk, we are mocking the return'
        obj_xpath = Mock()
        obj_xpath.text = '300000 or 5 minutes (recommended) '
        mock_xpath_obj = MagicMock(return_value=[obj_xpath])
        with patch.object(win_lgpo, 'ADML_DISPLAY_NAME_XPATH', mock_xpath_obj):
            result = win_lgpo._getAdmlDisplayName(adml_xml_data=adml_xml_data,
                                                  display_name=display_name)
        expected = '300000 or 5 minutes (recommended)'
        self.assertEqual(result, expected)

    def test__encode_string(self):
        '''
        ``_encode_string`` should return a null terminated ``utf-16-le`` encoded
        string when a string value is passed
        '''
        encoded_value = b''.join(['Salt is awesome'.encode('utf-16-le'),
                                  self.encoded_null])
        value = win_lgpo._encode_string('Salt is awesome')
        self.assertEqual(value, encoded_value)

    def test__encode_string_empty_string(self):
        '''
        ``_encode_string`` should return an encoded null when an empty string
        value is passed
        '''
        value = win_lgpo._encode_string('')
        self.assertEqual(value, self.encoded_null)

    def test__encode_string_error(self):
        '''
        ``_encode_string`` should raise an error if a non-string value is passed
        '''
        self.assertRaises(TypeError, win_lgpo._encode_string, [1])
        test_list = ['item1', 'item2']
        self.assertRaises(TypeError, win_lgpo._encode_string, [test_list])
        test_dict = {'key1': 'value1', 'key2': 'value2'}
        self.assertRaises(TypeError, win_lgpo._encode_string, [test_dict])

    def test__encode_string_none(self):
        '''
        ``_encode_string`` should return an encoded null when ``None`` is passed
        '''
        value = win_lgpo._encode_string(None)
        self.assertEqual(value, self.encoded_null)

    def test__multi_string_get_transform_list(self):
        '''
        ``_multi_string_get_transform`` should return the list when a list is
        passed
        '''
        test_value = ['Spongebob', 'Squarepants']
        value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
        self.assertEqual(value, test_value)

    def test__multi_string_get_transform_none(self):
        '''
        ``_multi_string_get_transform`` should return "Not Defined" when
        ``None`` is passed
        '''
        test_value = None
        value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
        self.assertEqual(value, 'Not Defined')

    def test__multi_string_get_transform_invalid(self):
        '''
        ``_multi_string_get_transform`` should return "Not Defined" when
        ``None`` is passed
        '''
        test_value = 'Some String'
        value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
        self.assertEqual(value, 'Invalid Value')

    def test__multi_string_put_transform_list(self):
        '''
        ``_multi_string_put_transform`` should return the list when a list is
        passed
        '''
        test_value = ['Spongebob', 'Squarepants']
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, test_value)

    def test__multi_string_put_transform_none(self):
        '''
        ``_multi_string_put_transform`` should return ``None`` when
        "Not Defined" is passed
        '''
        test_value = "Not Defined"
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, None)

    def test__multi_string_put_transform_list_from_string(self):
        '''
        ``_multi_string_put_transform`` should return a list when a comma
        delimited string is passed
        '''
        test_value = "Spongebob,Squarepants"
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, ['Spongebob', 'Squarepants'])

    def test__multi_string_put_transform_invalid(self):
        '''
        ``_multi_string_put_transform`` should return "Invalid" value if neither
        string nor list is passed
        '''
        test_value = None
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, "Invalid Value")


@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinLGPOGetPolicyADMXTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test functions related to the ``get_policy`` function using policy templates
    (admx/adml)
    '''
    def setup_loader_modules(self):
        return LOADER_DICTS

    def test_get_policy_name(self):
        result = win_lgpo.get_policy(policy_name='Allow Telemetry',
                                     policy_class='machine',
                                     return_value_only=True,
                                     return_full_policy_names=True,
                                     hierarchical_return=False)
        expected = 'Not Configured'
        self.assertEqual(result, expected)

    def test_get_policy_id(self):
        result = win_lgpo.get_policy(policy_name='AllowTelemetry',
                                     policy_class='machine',
                                     return_value_only=True,
                                     return_full_policy_names=True,
                                     hierarchical_return=False)
        expected = 'Not Configured'
        self.assertEqual(result, expected)

    def test_get_policy_name_full_return_full_names(self):
        result = win_lgpo.get_policy(policy_name='Allow Telemetry',
                                     policy_class='machine',
                                     return_value_only=False,
                                     return_full_policy_names=True,
                                     hierarchical_return=False)
        expected = {
            'Windows Components\\Data Collection and Preview Builds\\'
            'Allow Telemetry': 'Not Configured'}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_full_names(self):
        result = win_lgpo.get_policy(policy_name='AllowTelemetry',
                                     policy_class='machine',
                                     return_value_only=False,
                                     return_full_policy_names=True,
                                     hierarchical_return=False)
        expected = {
            'Windows Components\\Data Collection and Preview Builds\\'
            'Allow Telemetry': 'Not Configured'}
        self.assertDictEqual(result, expected)

    def test_get_policy_name_full_return_ids(self):
        result = win_lgpo.get_policy(policy_name='Allow Telemetry',
                                     policy_class='machine',
                                     return_value_only=False,
                                     return_full_policy_names=False,
                                     hierarchical_return=False)
        expected = {'AllowTelemetry': 'Not Configured'}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_ids(self):
        result = win_lgpo.get_policy(policy_name='AllowTelemetry',
                                     policy_class='machine',
                                     return_value_only=False,
                                     return_full_policy_names=False,
                                     hierarchical_return=False)
        expected = {'AllowTelemetry': 'Not Configured'}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_ids_hierarchical(self):
        result = win_lgpo.get_policy(policy_name='AllowTelemetry',
                                     policy_class='machine',
                                     return_value_only=False,
                                     return_full_policy_names=False,
                                     hierarchical_return=True)
        expected = {
            'Computer Configuration': {
                'Administrative Templates': {
                    'WindowsComponents': {
                        'DataCollectionAndPreviewBuilds': {
                            'AllowTelemetry': 'Not Configured'}}}}}
        self.assertDictEqual(result, expected)

    def test_get_policy_name_return_full_names_hierarchical(self):
        result = win_lgpo.get_policy(policy_name='Allow Telemetry',
                                     policy_class='machine',
                                     return_value_only=False,
                                     return_full_policy_names=True,
                                     hierarchical_return=True)
        expected = {
            'Computer Configuration': {
                'Administrative Templates': {
                    'Windows Components': {
                        'Data Collection and Preview Builds': {
                            'Allow Telemetry': 'Not Configured'}}}}}
        self.assertDictEqual(result, expected)


@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinLGPOGetPolicyFromPolicyInfoTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test functions related to the ``get_policy`` function using _policy_info
    object
    '''
    def setup_loader_modules(self):
        return LOADER_DICTS

    def test_get_policy_name(self):
        result = win_lgpo.get_policy(
            policy_name='Network firewall: Public: Settings: Display a '
                        'notification',
            policy_class='machine',
            return_value_only=True,
            return_full_policy_names=True,
            hierarchical_return=False)
        expected = 'Not configured'
        self.assertEqual(result, expected)

    def test_get_policy_id(self):
        result = win_lgpo.get_policy(
            policy_name='WfwPublicSettingsNotification',
            policy_class='machine',
            return_value_only=True,
            return_full_policy_names=True,
            hierarchical_return=False)
        expected = 'Not configured'
        self.assertEqual(result, expected)

    def test_get_policy_name_full_return(self):
        result = win_lgpo.get_policy(
            policy_name='Network firewall: Public: Settings: Display a '
                        'notification',
            policy_class='machine',
            return_value_only=False,
            return_full_policy_names=True,
            hierarchical_return=False)
        expected = {
            'Network firewall: Public: Settings: Display a notification':
                'Not configured'}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return(self):
        result = win_lgpo.get_policy(
            policy_name='WfwPublicSettingsNotification',
            policy_class='machine',
            return_value_only=False,
            return_full_policy_names=True,
            hierarchical_return=False)
        expected = {
            'Network firewall: Public: Settings: Display a notification':
                'Not configured'}
        self.assertDictEqual(result, expected)

    def test_get_policy_name_full_return_ids(self):
        result = win_lgpo.get_policy(
            policy_name='Network firewall: Public: Settings: Display a '
                        'notification',
            policy_class='machine',
            return_value_only=False,
            return_full_policy_names=False,
            hierarchical_return=False)
        expected = {
            'Network firewall: Public: Settings: Display a notification':
                'Not configured'}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_ids(self):
        result = win_lgpo.get_policy(
            policy_name='WfwPublicSettingsNotification',
            policy_class='machine',
            return_value_only=False,
            return_full_policy_names=False,
            hierarchical_return=False)
        expected = {'WfwPublicSettingsNotification': 'Not configured'}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_ids_hierarchical(self):
        result = win_lgpo.get_policy(
            policy_name='WfwPublicSettingsNotification',
            policy_class='machine',
            return_value_only=False,
            return_full_policy_names=False,
            hierarchical_return=True)
        expected = {
            'Computer Configuration': {
                'Windows Settings': {
                    'Security Settings': {
                        'Windows Firewall with Advanced Security': {
                            'Windows Firewall with Advanced Security - Local '
                            'Group Policy Object': {
                                'WfwPublicSettingsNotification':
                                    'Not configured'}}}}}}
        self.assertDictEqual(result, expected)

    def test_get_policy_id_full_return_full_names_hierarchical(self):
        result = win_lgpo.get_policy(
            policy_name='WfwPublicSettingsNotification',
            policy_class='machine',
            return_value_only=False,
            return_full_policy_names=True,
            hierarchical_return=True)
        expected = {
            'Computer Configuration': {
                'Windows Settings': {
                    'Security Settings': {
                        'Windows Firewall with Advanced Security': {
                            'Windows Firewall with Advanced Security - Local '
                            'Group Policy Object': {
                                'Network firewall: Public: Settings: Display a '
                                'notification':
                                    'Not configured'}}}}}}
        self.assertDictEqual(result, expected)


@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinLGPOPolicyInfoMechanismsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test getting local group policy settings defined in the _policy_info object
    Go through each mechanism
    '''
    def setup_loader_modules(self):
        return LOADER_DICTS

    @classmethod
    def setUpClass(cls):
        cls.policy_data = salt.modules.win_lgpo._policy_info()

    def _test_policy(self, policy_name):
        '''
        Helper function to get current setting
        '''
        policy_definition = self.policy_data.policies['Machine']['policies'][policy_name]
        return salt.modules.win_lgpo._get_policy_info_setting(policy_definition)

    def test_registry_mechanism(self):
        '''
        Test getting policy value using the Registry mechanism
        '''
        policy_name = 'RemoteRegistryExactPaths'
        result = self._test_policy(policy_name=policy_name)
        expected = [
            'System\\CurrentControlSet\\Control\\ProductOptions',
            'System\\CurrentControlSet\\Control\\Server Applications',
            'Software\\Microsoft\\Windows NT\\CurrentVersion'
        ]
        self.assertListEqual(result, expected)

    def test_secedit_mechanism(self):
        '''
        Test getting policy value using the Secedit mechanism
        '''
        policy_name = 'LSAAnonymousNameLookup'
        result = self._test_policy(policy_name=policy_name)
        expected = 'Disabled'
        self.assertEqual(result, expected)

    def test_netsh_mechanism(self):
        '''
        Test getting the policy value using the NetSH mechanism
        '''
        policy_name = 'WfwDomainState'
        result = self._test_policy(policy_name=policy_name)
        expected = 'Not configured'
        self.assertEqual(result, expected)

    @destructiveTest
    def test_adv_audit_mechanism(self):
        '''
        Test getting the policy value using the AdvAudit mechanism
        '''
        system_root = os.environ.get('SystemRoot', 'C:\\Windows')
        f_audit = os.path.join(system_root, 'security', 'audit', 'audit.csv')
        f_audit_gpo = os.path.join(system_root, 'System32', 'GroupPolicy',
                                   'Machine', 'Microsoft', 'Windows NT',
                                   'Audit', 'audit.csv')
        if os.path.exists(f_audit):
            os.remove(f_audit)
        if os.path.exists(f_audit_gpo):
            os.remove(f_audit_gpo)
        policy_name = 'AuditCredentialValidation'
        result = self._test_policy(policy_name=policy_name)
        expected = 'Not Configured'
        self.assertEqual(result, expected)

    def test_net_user_modal_mechanism(self):
        '''
        Test getting the policy value using the NetUserModal mechanism
        '''
        policy_name = 'PasswordHistory'
        result = self._test_policy(policy_name=policy_name)
        expected = 0
        self.assertEqual(result, expected)

    def test_lsa_rights_mechanism(self):
        '''
        Test getting the policy value using the LsaRights mechanism
        '''
        policy_name = 'SeTrustedCredManAccessPrivilege'
        result = self._test_policy(policy_name=policy_name)
        expected = []
        self.assertEqual(result, expected)

    def test_script_ini_mechanism(self):
        '''
        Test getting the policy value using the ScriptIni value
        '''
        policy_name = 'StartupScripts'
        result = self._test_policy(policy_name=policy_name)
        expected = None
        self.assertEqual(result, expected)


@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinLGPOGetPointAndPrintNCTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test variations of the Point and Print Restrictions policy when Not
    Configured (NC)
    '''
    not_configured = False

    def setup_loader_modules(self):
        return LOADER_DICTS

    def setUp(self):
        if not self.not_configured:
            computer_policy = {'Point and Print Restrictions': 'Not Configured'}
            win_lgpo.set_(computer_policy=computer_policy)
            self.not_configured = True

    def _get_policy_adm_setting(self, policy_name, policy_class,
                                return_full_policy_names, hierarchical_return):
        '''
        Helper function to get current setting
        '''
        # Get the policy
        success, policy_obj, _, _ = salt.modules.win_lgpo._lookup_admin_template(
            policy_name=policy_name,
            policy_class=policy_class,
            adml_language='en-US')
        if success:
            return salt.modules.win_lgpo._get_policy_adm_setting(
                admx_policy=policy_obj,
                policy_class=policy_class,
                adml_language='en-US',
                return_full_policy_names=return_full_policy_names,
                hierarchical_return=hierarchical_return
            )
        return 'Policy Not Found'

    def test_point_and_print_not_configured(self):
        result = self._get_policy_adm_setting(
            policy_name='Point and Print Restrictions',
            policy_class='Machine',
            return_full_policy_names=False,
            hierarchical_return=False
        )
        expected = {
            'PointAndPrint_Restrictions_Win7': 'Not Configured'
        }
        self.assertDictEqual(result, expected)

    def test_point_and_print_not_configured_hierarchical(self):
        result = self._get_policy_adm_setting(
            policy_name='Point and Print Restrictions',
            policy_class='Machine',
            return_full_policy_names=False,
            hierarchical_return=True
        )
        expected = {
            'Computer Configuration': {
                'Administrative Templates': {
                    'Printers': {
                        'PointAndPrint_Restrictions_Win7':
                            'Not Configured'}}}}
        self.assertDictEqual(result, expected)

    def test_point_and_print_not_configured_full_names(self):
        result = self._get_policy_adm_setting(
            policy_name='Point and Print Restrictions',
            policy_class='Machine',
            return_full_policy_names=True,
            hierarchical_return=False
        )
        expected = {
            'Printers\\Point and Print Restrictions': 'Not Configured'
        }
        self.assertDictEqual(result, expected)

    def test_point_and_print_not_configured_full_names_hierarchical(self):
        result = self._get_policy_adm_setting(
            policy_name='Point and Print Restrictions',
            policy_class='Machine',
            return_full_policy_names=True,
            hierarchical_return=True
        )
        expected = {
            'Computer Configuration': {
                'Administrative Templates': {
                    'Printers': {
                        'Point and Print Restrictions':
                            'Not Configured'}}}}
        self.assertDictEqual(result, expected)


@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinLGPOGetPointAndPrintENTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test variations of the Point and Print Restrictions policy when Enabled (EN)
    '''
    configured = False

    def setup_loader_modules(self):
        return LOADER_DICTS

    def setUp(self):
        if not self.configured:
            computer_policy = {
                'Point and Print Restrictions': {
                    'Users can only point and print to these servers':
                        True,
                    'Enter fully qualified server names separated by '
                    'semicolons':
                        'fakeserver1;fakeserver2',
                    'Users can only point and print to machines in their '
                    'forest':
                        True,
                    'Security Prompts: When installing drivers for a new '
                    'connection':
                        'Show warning and elevation prompt',
                    'When updating drivers for an existing connection':
                        'Show warning only',
                },
            }
            win_lgpo.set_(computer_policy=computer_policy)
            self.configured = True

    def _get_policy_adm_setting(self, policy_name, policy_class,
                                return_full_policy_names, hierarchical_return):
        '''
        Helper function to get current setting
        '''
        # Get the policy
        success, policy_obj, _, _ = salt.modules.win_lgpo._lookup_admin_template(
            policy_name=policy_name,
            policy_class=policy_class,
            adml_language='en-US')
        if success:
            return salt.modules.win_lgpo._get_policy_adm_setting(
                admx_policy=policy_obj,
                policy_class=policy_class,
                adml_language='en-US',
                return_full_policy_names=return_full_policy_names,
                hierarchical_return=hierarchical_return
            )
        return 'Policy Not Found'

    def test_point_and_print_enabled(self):
        result = self._get_policy_adm_setting(
            policy_name='Point and Print Restrictions',
            policy_class='Machine',
            return_full_policy_names=False,
            hierarchical_return=False
        )
        expected = {
            'PointAndPrint_Restrictions_Win7': {
                'PointAndPrint_NoWarningNoElevationOnInstall_Enum':
                    'Show warning and elevation prompt',
                'PointAndPrint_NoWarningNoElevationOnUpdate_Enum':
                    'Show warning only',
                'PointAndPrint_TrustedForest_Chk':
                    True,
                'PointAndPrint_TrustedServers_Chk':
                    True,
                u'PointAndPrint_TrustedServers_Edit':
                    'fakeserver1;fakeserver2'}}
        self.assertDictEqual(result, expected)

    def test_point_and_print_enabled_hierarchical(self):
        result = self._get_policy_adm_setting(
            policy_name='Point and Print Restrictions',
            policy_class='Machine',
            return_full_policy_names=False,
            hierarchical_return=True
        )
        expected = {
            'Computer Configuration': {
                'Administrative Templates': {
                    'Printers': {
                        'PointAndPrint_Restrictions_Win7': {
                            'PointAndPrint_NoWarningNoElevationOnInstall_Enum':
                                'Show warning and elevation prompt',
                            'PointAndPrint_NoWarningNoElevationOnUpdate_Enum':
                                'Show warning only',
                            'PointAndPrint_TrustedForest_Chk':
                                True,
                            'PointAndPrint_TrustedServers_Chk':
                                True,
                            u'PointAndPrint_TrustedServers_Edit':
                                'fakeserver1;fakeserver2'}}}}}
        self.assertDictEqual(result, expected)

    def test_point_and_print_enabled_full_names(self):
        result = self._get_policy_adm_setting(
            policy_name='Point and Print Restrictions',
            policy_class='Machine',
            return_full_policy_names=True,
            hierarchical_return=False
        )
        expected = {
            'Printers\\Point and Print Restrictions': {
                'Enter fully qualified server names separated by semicolons':
                    'fakeserver1;fakeserver2',
                'Security Prompts: When installing drivers for a new '
                'connection':
                    'Show warning and elevation prompt',
                'Users can only point and print to machines in their forest':
                    True,
                u'Users can only point and print to these servers': True,
                u'When updating drivers for an existing connection':
                    'Show warning only'}}
        self.assertDictEqual(result, expected)

    def test_point_and_print_enabled_full_names_hierarchical(self):
        result = self._get_policy_adm_setting(
            policy_name='Point and Print Restrictions',
            policy_class='Machine',
            return_full_policy_names=True,
            hierarchical_return=True
        )
        expected = {
            'Computer Configuration': {
                'Administrative Templates': {
                    'Printers': {
                        'Point and Print Restrictions': {
                            'Enter fully qualified server names separated by '
                            'semicolons':
                                'fakeserver1;fakeserver2',
                            'Security Prompts: When installing drivers for a '
                            'new connection':
                                'Show warning and elevation prompt',
                            'Users can only point and print to machines in '
                            'their forest':
                                True,
                            u'Users can only point and print to these servers':
                                True,
                            u'When updating drivers for an existing connection':
                                'Show warning only'}}}}}
        self.assertDictEqual(result, expected)
