# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import re
import io
import logging

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest, generate_random_name
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils.files
import salt.utils.platform
import salt.utils.win_reg as reg

log = logging.getLogger(__name__)


@skipIf(not salt.utils.platform.is_windows(), 'windows test only')
class WinLgpoTest(ModuleCase):
    '''
    Tests for salt.modules.win_lgpo
    '''
    osrelease = None

    def _testRegistryPolicy(self,
                            policy_name,
                            policy_config,
                            registry_value_hive,
                            registry_value_path,
                            registry_value_vname,
                            expected_value_data):
        '''
        Takes a registry based policy name and config and validates taht the
        expected registry value exists and has the correct data

        policy_name
            name of the registry based policy to configure
        policy_config
            the configuration of the policy
        registry_value_hive
            the registry hive that the policy registry path is in
        registry_value_path
            the registry value path that the policy updates
        registry_value_vname
            the registry value name
        expected_value_data
            the expected data that the value will contain
        '''
        ret = self.run_function('lgpo.set_computer_policy',
                                (policy_name, policy_config))
        self.assertTrue(ret)
        val = reg.read_value(
                registry_value_hive,
                registry_value_path,
                registry_value_vname)
        self.assertTrue(val['success'], msg='Failed to obtain the registry data for policy {0}'.format(policy_name))
        if val['success']:
            self.assertEqual(val['vdata'], expected_value_data, 'The registry value data {0} does not match the expected value {1} for policy {2}'.format(
                        val['vdata'],
                        expected_value_data,
                        policy_name))

    def _testSeceditPolicy(self,
                           policy_name,
                           policy_config,
                           expected_regexes,
                           cumulative_rights_assignments=True):
        '''
        Takes a secedit policy name and config and validates that the expected
        output is returned from secedit

        policy_name
            name of the secedit policy to configure
        policy_config
            the configuration of the policy
        expected_regexes
            the expected regexes to be found in the secedit output file
        '''
        ret = self.run_function('lgpo.set_computer_policy',
                                (policy_name, policy_config),
                                cumulative_rights_assignments=cumulative_rights_assignments)
        self.assertTrue(ret)
        secedit_output_file = os.path.join(RUNTIME_VARS.TMP, generate_random_name('secedit-output-'))
        secedit_output = self.run_function(
                'cmd.run',
                (),
                cmd='secedit /export /cfg {0}'.format(secedit_output_file))
        secedit_file_content = None
        if secedit_output:
            with io.open(secedit_output_file, encoding='utf-16') as _reader:
                secedit_file_content = _reader.read()
        for expected_regex in expected_regexes:
            match = re.search(
                    expected_regex,
                    secedit_file_content,
                    re.IGNORECASE | re.MULTILINE)
            self.assertIsNotNone(match, 'Failed validating policy "{0}" configuration, regex "{1}" not found in secedit output'.format(policy_name, expected_regex))

    def _testComputerAdmxPolicy(self,
                                policy_name,
                                policy_config,
                                expected_regexes,
                                assert_true=True):
        '''
        Takes a ADMX policy name and config and validates that the expected
        output is returned from lgpo looking at the Registry.pol file

        policy_name
            name of the ADMX policy to configure
        policy_config
            the configuration of the policy
        expected_regexes
            the expected regexes to be found in the lgpo parse output
        assert_true
            set to false if expecting the module run to fail
        '''
        ret = self.run_function('lgpo.set_computer_policy',
                                (policy_name, policy_config))
        log.debug('lgpo set_computer_policy ret == %s', ret)
        if assert_true:
            self.assertTrue(ret)
            lgpo_output = self.run_function(
                    'cmd.run',
                    (),
                    cmd='lgpo.exe /parse /m c:\\Windows\\System32\\GroupPolicy\\Machine\\Registry.pol')
            # validate that the lgpo output doesn't say the format is invalid
            self.assertIsNone(
                re.search(
                    r'Invalid file format\.',
                    lgpo_output,
                    re.IGNORECASE), 'Failed validating Registry.pol file format')
            # validate that the regexes we expect are in the output
            for expected_regex in expected_regexes:
                match = re.search(
                        expected_regex,
                        lgpo_output,
                        re.IGNORECASE)
                self.assertIsNotNone(match, 'Failed validating policy "{0}" configuration, regex "{1}" not found in lgpo output'.format(policy_name, expected_regex))
        else:
            # expecting it to fail
            self.assertNotEqual(ret, True)

    def runTest(self):
        '''
        runTest method
        '''
        pass

    @classmethod
    def setUpClass(cls):
        '''
        class setup function, only runs once

        downloads and extracts the lgpo.exe tool into c:/windows/system32
        for use in validating the registry.pol files

        gets osrelease grain for tests that are only applicable to certain
        windows versions
        '''
        osrelease_grains = cls().run_function('grains.item', ['osrelease'])
        if 'osrelease' in osrelease_grains:
            cls.osrelease = osrelease_grains['osrelease']
        else:
            log.debug('Unable to get osrelease grain')
        if not os.path.exists(r'c:\windows\system32\lgpo.exe'):
            log.debug('lgpo.exe does not exist, attempting to download/extract')
            ret = cls().run_function('state.single',
                                     ('archive.extracted', r'c:\windows\system32'),
                                     source='https://download.microsoft.com/download/8/5/C/85C25433-A1B0-4FFA-9429-7E023E7DA8D8/LGPO.zip',
                                     archive_format='zip',
                                     source_hash='sha256=6ffb6416366652993c992280e29faea3507b5b5aa661c33ba1af31f48acea9c4',
                                     enforce_toplevel=False)
            log.debug('ret from archive.unzip == %s', ret)

    @destructiveTest
    def test_set_computer_policy_NTP_Client(self):
        '''
        Test setting/unsetting/changing NTP Client policies
        '''
        # Disable Configure NTP Client
        self._testComputerAdmxPolicy(r'System\Windows Time Service\Time Providers\Configure Windows NTP Client',
                                     'Disabled',
                                     [
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*NtpServer[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*Type[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*CrossSiteSyncFlags[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMinutes[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMaxTimes[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*SpecialPollInterval[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*EventLogFlags[\s]*DELETE'
                                     ])
        # Enable Configure NTP Client
        self._testComputerAdmxPolicy(r'System\Windows Time Service\Time Providers\Configure Windows NTP Client',
                                     {
                                         'NtpServer': 'time.windows.com,0x9',
                                         'Type': 'NT5DS',
                                         'CrossSiteSyncFlags': 2,
                                         'ResolvePeerBackoffMinutes': 15,
                                         'ResolvePeerBackoffMaxTimes': 7,
                                         'W32TIME_SpecialPollInterval': 3600,
                                         'W32TIME_NtpClientEventLogFlags': 0
                                     },
                                     [
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*NtpServer[\s]*SZ:time.windows.com,0x9',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*Type[\s]*SZ:NT5DS',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*CrossSiteSyncFlags[\s]*DWORD:2',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMinutes[\s]*DWORD:15',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMaxTimes[\s]*DWORD:7',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*SpecialPollInterval[\s]*DWORD:3600',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*EventLogFlags[\s]*DWORD:0',
                                     ])
        # set Configure NTP Client to 'Not Configured'
        self._testComputerAdmxPolicy(r'System\Windows Time Service\Time Providers\Configure Windows NTP Client',
                                     'Not Configured',
                                     [r'; Source file:  c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*; PARSING COMPLETED.'])

    @destructiveTest
    def test_set_computer_policy_RA_Unsolicit(self):
        '''
        Test setting/unsetting/changing RA_Unsolicit policy
        '''

        # Disable RA_Unsolicit
        log.debug('Attempting to disable RA_Unsolicit')
        self._testComputerAdmxPolicy('RA_Unsolicit',
                                     'Disabled',
                                     [
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicited[\s]*DWORD:0',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicitedFullControl[\s]*DELETE',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*\*[\s]*DELETEALLVALUES',
                                     ])
        # configure RA_Unsolicit
        log.debug('Attempting to configure RA_Unsolicit')
        self._testComputerAdmxPolicy('RA_Unsolicit',
                                     {
                                         'Configure Offer Remote Access': 'Enabled',
                                         'Permit remote control of this computer': 'Allow helpers to remotely control the computer',
                                         'Helpers': ['administrators', 'user1']
                                     },
                                     [
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*user1[\s]*SZ:user1[\s]*',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*administrators[\s]*SZ:administrators[\s]*',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicited[\s]*DWORD:1',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicitedFullControl[\s]*DWORD:1',
                                     ])
        # Not Configure RA_Unsolicit
        log.debug('Attempting to set RA_Unsolicit to Not Configured')
        self._testComputerAdmxPolicy('RA_Unsolicit',
                                     'Not Configured',
                                     [r'; Source file:  c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*; PARSING COMPLETED.'])

    @destructiveTest
    def test_set_computer_policy_WindowsUpdate(self):
        '''
        Test setting/unsetting/changing WindowsUpdate policy
        '''
        # disable Configure Automatic Updates
        self._testComputerAdmxPolicy(r'Windows Components\Windows Update\Configure Automatic Updates',
                                     'Disabled',
                                     [
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*NoAutoUpdate[\s]*DWORD:1',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AUOptions[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AutomaticMaintenanceEnabled[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallDay[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallTime[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AllowMUUpdateService[\s]*DELETE'
                                 ])
        # set Configure Automatic Updates to 'Not Configured'
        self._testComputerAdmxPolicy(r'Windows Components\Windows Update\Configure Automatic Updates',
                                     'Not Configured',
                                     [r'; Source file:  c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*; PARSING COMPLETED.'])

    @destructiveTest
    def test_set_computer_policy_ClipboardRedirection(self):
        '''
        Test setting/unsetting/changing ClipboardRedirection policy
        '''
        # Enable/Disable/Not Configured "Do not allow Clipboard redirection"
        self._testComputerAdmxPolicy(r'Windows Components\Remote Desktop Services\Remote Desktop Session Host\Device and Resource Redirection\Do not allow Clipboard redirection',
                                     'Enabled',
                                     [r'Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fDisableClip[\s]*DWORD:1'])
        self._testComputerAdmxPolicy(r'Windows Components\Remote Desktop Services\Remote Desktop Session Host\Device and Resource Redirection\Do not allow Clipboard redirection',
                                     'Disabled',
                                     [r'Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fDisableClip[\s]*DWORD:0'])
        self._testComputerAdmxPolicy(r'Windows Components\Remote Desktop Services\Remote Desktop Session Host\Device and Resource Redirection\Do not allow Clipboard redirection',
                                     'Not Configured',
                                     [r'; Source file:  c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*; PARSING COMPLETED.'])

    @destructiveTest
    def test_set_computer_policy_PasswordComplexity(self):
        '''
        Test setting/unsetting/changing PasswordComplexity
        '''
        # disable PasswordComplexity
        self._testSeceditPolicy('Password must meet complexity requirements',
                                'Disabled',
                                [r'^PasswordComplexity = 0'])
        # enable PasswordComplexity
        self._testSeceditPolicy('PasswordComplexity',
                                'Enabled',
                                [r'^PasswordComplexity = 1'])

    @destructiveTest
    def test_set_computer_policy_PasswordLen(self):
        '''
        Test setting/unsetting/changing PasswordLength
        '''
        # set Minimum password length
        self._testSeceditPolicy('Minimum password length',
                                10,
                                [r'^MinimumPasswordLength = 10'])
        # set MinimumPasswordLength = 0
        self._testSeceditPolicy('MinPasswordLen',
                                0,
                                [r'^MinimumPasswordLength = 0'])

    @destructiveTest
    def test_set_computer_policy_SeNetworkLogonRight(self):
        '''
        Test setting/unsetting/changing PasswordLength
        '''
        # set SeNetworkLogonRight to only Administrators
        self._testSeceditPolicy('Access this computer from the network',
                                ['Administrators'],
                                [r'^SeNetworkLogonRight = \*S-1-5-32-544'],
                                cumulative_rights_assignments=False)
        # set SeNetworkLogonRight back to the default
        self._testSeceditPolicy('SeNetworkLogonRight',
                                ['Everyone', 'Administrators', 'Users', 'Backup Operators'],
                                [r'^SeNetworkLogonRight = \*S-1-1-0,\*S-1-5-32-544,\*S-1-5-32-545,\*S-1-5-32-551'])

    @destructiveTest
    def test_set_computer_policy_multipleAdmxPolicies(self):
        '''
        Tests setting several ADMX policies in succession and validating the configuration w/lgop
        '''
        # set one policy
        self._testComputerAdmxPolicy(r'Windows Components\Remote Desktop Services\Remote Desktop Session Host\Device and Resource Redirection\Do not allow Clipboard redirection',
                                     'Disabled',
                                     [r'Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fDisableClip[\s]*DWORD:0'])

        # set another policy and make sure both this policy and the previous are okay
        self._testComputerAdmxPolicy('RA_Unsolicit',
                                     {
                                         'Configure Offer Remote Access': 'Enabled',
                                         'Permit remote control of this computer': 'Allow helpers to remotely control the computer',
                                         'Helpers': ['administrators', 'user1']
                                     },
                                     [
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fDisableClip[\s]*DWORD:0',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*user1[\s]*SZ:user1[\s]*',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*administrators[\s]*SZ:administrators[\s]*',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicited[\s]*DWORD:1',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicitedFullControl[\s]*DWORD:1',
                                     ])
        # Configure Automatic Updates and validate everything is still okay
        self._testComputerAdmxPolicy(r'Windows Components\Windows Update\Configure Automatic Updates',
                                     'Disabled',
                                     [
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fDisableClip[\s]*DWORD:0',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*user1[\s]*SZ:user1[\s]*',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*administrators[\s]*SZ:administrators[\s]*',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicited[\s]*DWORD:1',
                                         r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicitedFullControl[\s]*DWORD:1',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*NoAutoUpdate[\s]*DWORD:1',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AUOptions[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AutomaticMaintenanceEnabled[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallDay[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*ScheduledInstallTime[\s]*DELETE',
                                         r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU[\s]*AllowMUUpdateService[\s]*DELETE'
                                     ])

    @destructiveTest
    def test_set_computer_policy_DisableDomainCreds(self):
        '''
        Tests Enable/Disable of DisableDomainCreds policy
        '''
        self._testRegistryPolicy('DisableDomainCreds',
                                 'Enabled',
                                 'HKEY_LOCAL_MACHINE',
                                 'SYSTEM\\CurrentControlSet\\Control\\Lsa',
                                 'DisableDomainCreds',
                                 1)
        self._testRegistryPolicy(
                'Network access: Do not allow storage of passwords and credentials for network authentication',
                'Disabled',
                'HKEY_LOCAL_MACHINE',
                'SYSTEM\\CurrentControlSet\\Control\\Lsa',
                'DisableDomainCreds',
                0)

    @destructiveTest
    def test_set_computer_policy_ForceGuest(self):
        '''
        Tests changing ForceGuest policy
        '''
        self._testRegistryPolicy('ForceGuest',
                                 'Guest only - local users authenticate as Guest',
                                 'HKEY_LOCAL_MACHINE',
                                 'SYSTEM\\CurrentControlSet\\Control\\Lsa',
                                 'ForceGuest',
                                 1)
        self._testRegistryPolicy(
                'Network access: Sharing and security model for local accounts',
                'Classic - local users authenticate as themselves',
                'HKEY_LOCAL_MACHINE',
                'SYSTEM\\CurrentControlSet\\Control\\Lsa',
                'ForceGuest',
                0)

    @destructiveTest
    def test_set_computer_policy_DisableUXWUAccess(self):
        '''
        Tests changing DisableUXWUAccess
        #50079 shows using the 'Remove access to use all Windows Update features' failed
        Policy only exists on 2016
        '''
        valid_osreleases = ['2016Server']
        if self.osrelease not in valid_osreleases:
            self.skipTest('DisableUXWUAccess policy is only applicable if the osrelease grain is {0}'.format(' or '.join(valid_osreleases)))
        else:
            self._testComputerAdmxPolicy(r'DisableUXWUAccess',
                                         'Enabled',
                                         [r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetDisableUXWUAccess[\s]*DWORD:1'])
            self._testComputerAdmxPolicy(r'Remove access to use all Windows Update features',
                                         'Disabled',
                                         [r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetDisableUXWUAccess[\s]*DWORD:0'])
            self._testComputerAdmxPolicy(r'Windows Components\Windows Update\Remove access to use all Windows Update features',
                                         'Not Configured',
                                         [r'; Source file:  c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*; PARSING COMPLETED.'])

    @destructiveTest
    def test_set_computer_policy_Access_data_sources_across_domains(self):
        '''
        Tests that a policy that has multiple names
        '''
        self._testComputerAdmxPolicy(r'Access data sources across domains',
                                     'Enabled',
                                     [],
                                     assert_true=False)
        self._testComputerAdmxPolicy(r'Windows Components\Internet Explorer\Internet Control Panel\Security Page\Internet Zone\Access data sources across domains',
                                     {'Access data sources across domains': 'Prompt'},
                                     [r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\\Zones\\3[\s]*1406[\s]*DWORD:1'])
        self._testComputerAdmxPolicy(r'Windows Components\Internet Explorer\Internet Control Panel\Security Page\Internet Zone\Access data sources across domains',
                                     {'Access data sources across domains': 'Enable'},
                                     [r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\\Zones\\3[\s]*1406[\s]*DWORD:0'])
        self._testComputerAdmxPolicy(r'Windows Components\Internet Explorer\Internet Control Panel\Security Page\Internet Zone\Access data sources across domains',
                                     'Disabled',
                                     [r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\\Zones\\3[\s]*1406[\s]*DELETE'])

    @destructiveTest
    def test_set_computer_policy_ActiveHours(self):
        '''
        Test configuring the ActiveHours policy, #47784
        Only applies to 2016Server
        # activehours.sls
            active_hours_policy:
              lgpo.set:
                - computer_policy:
                    'ActiveHours':
                        'ActiveHoursStartTime': '8 AM'
                        'ActiveHoursEndTime': '7 PM'
        '''
        valid_osreleases = ['2016Server']
        if self.osrelease not in valid_osreleases:
            self.skipTest('ActiveHours policy is only applicable if the osrelease grain is {0}'.format(' or '.join(valid_osreleases)))
        else:
            self._testComputerAdmxPolicy(r'ActiveHours',
                                         {'ActiveHoursStartTime': '8 AM', 'ActiveHoursEndTime': '7 PM'},
                                         [
                                            r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetActiveHours[\s]*DWORD:1',
                                            r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursStart[\s]*DWORD:8',
                                            r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursEnd[\s]*DWORD:19'
                                         ])
            self._testComputerAdmxPolicy(r'ActiveHours',
                                         {'ActiveHoursStartTime': '5 AM', 'ActiveHoursEndTime': '10 PM'},
                                         [
                                            r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetActiveHours[\s]*DWORD:1',
                                            r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursStart[\s]*DWORD:5',
                                            r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursEnd[\s]*DWORD:22'
                                         ])
            self._testComputerAdmxPolicy('Turn off auto-restart for updates during active hours',
                                         'Disabled',
                                         [
                                            r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*SetActiveHours[\s]*DWORD:0',
                                            r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursStart[\s]*DELETE',
                                            r'Computer[\s]*Software\\Policies\\Microsoft\\Windows\\WindowsUpdate[\s]*ActiveHoursEnd[\s]*DELETE'
                                         ])
            self._testComputerAdmxPolicy(r'Windows Components\Windows Update\Turn off auto-restart for updates during active hours',
                                         'Not Configured',
                                         [r'; Source file:  c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*; PARSING COMPLETED.'])

    def tearDown(self):
        '''
        tearDown method, runs after each test
        '''
        ret = self.run_function('state.single',
                                ('file.absent', 'c:\\windows\\system32\\grouppolicy\\machine\\registry.pol'))
        ret = self.run_function('state.single',
                                ('file.absent', 'c:\\windows\\system32\\grouppolicy\\user\\registry.pol'))
