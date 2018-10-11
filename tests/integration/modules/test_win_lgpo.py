# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import textwrap
import re
import io

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest, generate_random_name
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils.files
import salt.utils.platform

@skipIf(not salt.utils.platform.is_windows(), 'windows test only')
class WinLgpoTest(ModuleCase):
    '''
    Tests for salt.modules.win_lgpo
    '''

    def setUp(self):
        '''
        setup function

        downloads and extracts the lgpo.exe tool into c:\windows\system32
        for use in validating the registry.pol files
        '''
        ret = self.run_function('archive.unzip',
                                'https://www.microsoft.com/en-us/download/confirmation.aspx?id=55319&6B49FDFB-8E5B-4B07-BC31-15695C5A2143=1',
                                dest='c:\\windows\\system32')

    @destructiveTest
    def test_set_computer_policy(self):
        '''
        Test setting/unsetting/changing multiple policies
        '''

        def _testSeceditPolicy(policy_name,
                               policy_config,
                               expected_regex,
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
                                    policy_name,
                                    policy_config,
                                    cumulative_rights_assignments=cumulative_rights_assignments)
            self.assertTrue(ret)
            secedit_output_file = os.path.join(RUNTIME_VARS.TMP, generate_random_name('secedit-output-'))
            secedit_output = self.run_function(
                    'cmd.run',
                    'secedit /export /cfg {0}'.format(secedit_output_file))
            secedit_file_content = None
            if secedit_output:
                with io.open(secedit_output_file, encoding='utf-16') as _reader:
                    _secdata = _reader.read()
            for expected_regex in expected_regexes:
                match = re.search(
                        expected_regex,
                        lgpo_output,
                        re.IGNORECASE)
                assert match not None
        def _testComputerAdmxPolicy(policy_name,
                                    policy_config,
                                    expected_regexes):
            '''
            Takes a ADMX policy name and config and validates that the expected
            output is returned from lgpo looking at the Registry.pol file

            policy_name
                name of the ADMX policy to configure
            policy_config
                the configuration of the policy
            expected_regexes
                the expected regexes to be found in the lgpo parse output
            '''
            ret = self.run_function('lgpo.set_computer_policy',
                                    policy_name,
                                    policy_config)
            self.assertTrue(ret)
            lgpo_output = self.run_function(
                    'cmd.run',
                    'lgpo.exe /parse /m c:\\Windows\\System32\\GroupPolicy\\Machine\\Registry.pol')
            for expected_regex in expected_regexes:
                match = re.search(
                        expected_regex,
                        lgpo_output,
                        re.IGNORECASE)
                assert match not None

        # configure RA_Unsolicit
        _testComputerAdmxPolicy('RA_Unsolicit',
                                {
                                    'Configure Offer Remote Access': Enabled,
                                    'Permit remote control of this computer': 'Allow helpers to remotely control the computer',
                                    'Helpers': ['administrators', 'user1']
                                },
                                [
                                    r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*user1[\s]*SZ:user1[\s]*',
                                    r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*administrators[\s]*SZ:administrators[\s]*',
                                    r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicited[\s]*DWORD:1',
                                    r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicitedFullControl[\s]*DWORD:1',
                                ])
        # Disable RA_Unsolicit
        _testComputerAdmxPolicy('RA_Unsolicit',
                                'Disabled',
                                [
                                    r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicited[\s]*DWORD:0',
                                    r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services[\s]*fAllowUnsolicitedFullControl[\s]*DELETE',
                                    r'Computer[\s]*Software\\policies\\Microsoft\\Windows NT\\Terminal Services\\RAUnsolicit[\s]*\*[\s]*DELETEALLVALUES',
                                ])
        # Not Configure RA_Unsolicit
        _testComputerAdmxPolicy('RA_Unsolicit',
                                'Not Configured',
                                [r'; Source file:  c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*; PARSING COMPLETED.'])

        # Disable Configure NTP Client
        _testComputerAdmxPolicy('System\Windows Time Service\Time Providers\Configure Windows NTP Client',
                                'Disabled',
                                [
                                    r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*NtpServer[\s]*DELETE',
                                    r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\Parameters[\s]*Type[\s]*DELETE',
                                    r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*CrossSiteSyncFlags[\s]*DELETE',
                                    r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMinutes[\s]*DELETE',
                                    r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*ResolvePeerBackoffMaxTimes[\s]*DELETE',
                                    r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*SpecialPollInterval[\s]*DELETE',
                                    r'Computer[\s]*Software\\Policies\\Microsoft\\W32time\\TimeProviders\\NtpClient[\s]*EventLogFlags[\s]*DELETE'
                                ]
        # Enable Configure NTP Client
         _testComputerAdmxPolicy('System\Windows Time Service\Time Providers\Configure Windows NTP Client',
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
        _testComputerAdmxPolicy('System\Windows Time Service\Time Providers\Configure Windows NTP Client',
                                'Not Configured',
                                [r'; Source file:  c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*; PARSING COMPLETED.'])

        # disable Configure Automatic Updates
        _testComputerAdmxPolicy('Windows Components\Windows Update\Configure Automatic Updates',
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
        _testComputerAdmxPolicy('Windows Components\Windows Update\Configure Automatic Updates',
                                'Not Configured',
                                [r'; Source file:  c:\\windows\\system32\\grouppolicy\\machine\\registry.pol[\s]*; PARSING COMPLETED.'])
        
        # disable PasswordComplexity
        _testSeceditPolicy('Password must meet complexity requirements',
                           'Disabled',
                           [r'^PasswordComplexity = 0'])
        # enable PasswordComplexity
        _testSeceditPolicy('PasswordComplexity',
                           'Disabled',
                           [r'^PasswordComplexity = 1'])
        # set Minimum password length
        _testSeceditPolicy('Minimum password length',
                           10,
                           [r'^MinimumPasswordLength = 10'])
        # set MinimumPasswordLength = 0
        _testSeceditPolicy('MinimumPasswordLength',
                           0,
                           [r'^MinimumPasswordLength = 0'])
        # set SeNetworkLogonRight to only Administrators
        _testSeceditPolicy('Access this computer from the network',
                           ['Administrators'],
                           [r'^SeNetworkLogonRight = \*S-1-5-32-544'],
                           cumulative_rights_assignments=False)
        # set SeNetworkLogonRight back to the default
        _testSeceditPolicy('SeNetworkLogonRight',
                           ['Everyone', 'Administrators', 'Users', 'Backup Operators'],
                           [r'^SeNetworkLogonRight = \*S-1-1-0,\*S-1-5-32-544,\*S-1-5-32-545,\*S-1-5-32-551'])
    def tearDown(self):
        pass
