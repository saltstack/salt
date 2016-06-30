# -*- coding: utf-8 -*-
'''
Manage Local Policy on Windows

Administrative template policies are dynamically read from admx/adml files.  Other
policies must be statically set in the _policy_info class object.

:depends:
  - pywin32 Python module
  - xmltodict

'''

# Import python libs
from __future__ import absolute_import
import os
import logging
import re

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError
from salt.exceptions import SaltInvocationError
import salt.utils.dictupdate as dictupdate
from salt.ext.six import string_types

try:
    import win32net
    import win32security
    import uuid
    import codecs
    import lxml
    from lxml import etree
    from salt.modules.reg import Registry as Registry
    HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

log = logging.getLogger(__name__)
__virtualname__ = 'lgpo'


class _policy_info(object):
    '''
    policy helper stuff
    '''
    def __init__(self):
        self.policies = {
            'StartupScripts': {
                'Policy': 'Startup Scripts',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Scripts (Startup/Shutdown)',
                                 'Startup'],
                'ScriptIni': {
                    'Section': 'Startup',
                    'IniPath': os.path.join(os.getenv('WINDIR'),
                                            'System32',
                                            'GroupPolicy',
                                            'Machine',
                                            'Scripts',
                                            'scripts.ini'),
                },
            },
            'StartupPowershellScripts': {
                'Policy': 'Startup Powershell Scripts',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Scripts (Startup/Shutdown)',
                                 'Startup'],
                'ScriptIni': {
                    'Section': 'Startup',
                    'IniPath': os.path.join(os.getenv('WINDIR'),
                                            'System32',
                                            'GroupPolicy',
                                            'Machine',
                                            'Scripts',
                                            'psscripts.ini'),
                },
            },
            'StartupPowershellScriptOrder': {
                'Policy': 'Startup - For this GPO, run scripts in the following order',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Scripts (Startup/Shutdown)',
                                 'Startup'],
                'ScriptIni': {
                    'IniPath': os.path.join(os.getenv('WINDIR'),
                                            'System32',
                                            'GroupPolicy',
                                            'Machine',
                                            'Scripts',
                                            'psscripts.ini'),
                    'Section': 'ScriptsConfig',
                    'SettingName': 'StartExecutePSFirst',
                    'Settings': ['true', 'false', None],
                },
                'Transform': {
                    'Get': '_powershell_script_order_conversion',
                    'Put': '_powershell_script_order_reverse_conversion',
                },
            },
            'ShutdownScripts': {
                'Policy': 'Shutdown Scripts',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Scripts (Startup/Shutdown)',
                                 'Shutdown'],
                'ScriptIni': {
                    'Section': 'Shutdown',
                    'IniPath': os.path.join(os.getenv('WINDIR'),
                                            'System32',
                                            'GroupPolicy',
                                            'Machine',
                                            'Scripts',
                                            'scripts.ini'),
                },
            },
            'ShutdownPowershellScripts': {
                'Policy': 'Shutdown Powershell Scripts',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Scripts (Startup/Shutdown)',
                                 'Shutdown'],
                'ScriptIni': {
                    'Section': 'Shutdown',
                    'IniPath': os.path.join(os.getenv('WINDIR'),
                                            'System32',
                                            'GroupPolicy',
                                            'Machine',
                                            'Scripts',
                                            'psscripts.ini'),
                },
            },
            'ShutdownPowershellScriptOrder': {
                'Policy': 'Shutdown - For this GPO, run scripts in the following order',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Scripts (Startup/Shutdown)',
                                 'Shutdown'],
                'ScriptIni': {
                    'IniPath': os.path.join(os.getenv('WINDIR'),
                                            'System32',
                                            'GroupPolicy',
                                            'Machine',
                                            'Scripts',
                                            'psscripts.ini'),
                    'Section': 'ScriptsConfig',
                    'SettingName': 'EndExecutePSFirst',
                    'Settings': ['true', 'false', None],
                },
                'Transform': {
                    'Get': '_powershell_script_order_conversion',
                    'Put': '_powershell_script_order_reverse_conversion',
                },
            },
            'RestrictAnonymous': {
                'Policy': 'Network Access: Do not allow anonymous enumeration of SAM accounts and shares',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Settings': [0, 1],
                'Registry': {
                    'Hive': 'HKEY_LOCAL_MACHINE',
                    'Path': 'SYSTEM\\CurrentControlSet\\Control\\Lsa',
                    'Value': 'RestrictAnonymous',
                    'Type': 'REG_DWORD'
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                },
            },
            'PasswordHistory': {
                'Policy': 'Enforce password history',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Password Policy'],
                'Settings': {
                    'Function': '_in_range_inclusive',
                    'Args': {'min': 0, 'max': 24}
                },
                'NetUserModal': {
                    'Modal': 0,
                    'Option': 'password_hist_len'
                },
            },
            'MaxPasswordAge': {
                'Policy': 'Maximum password age',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Password Policy'],
                'Settings': {
                    'Function': '_in_range_inclusive',
                    'Args': {'min': 0, 'max': 86313600}
                },
                'NetUserModal': {
                    'Modal': 0,
                    'Option': 'max_passwd_age',
                },
                'Transform': {
                    'Get': '_seconds_to_days',
                    'Put': '_days_to_seconds'
                },
            },
            'MinPasswordAge': {
                'Policy': 'Minimum password age',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Password Policy'],
                'Settings': {
                    'Function': '_in_range_inclusive',
                    'Args': {'min': 0, 'max': 86313600}
                },
                'NetUserModal': {
                    'Modal': 0,
                    'Option': 'min_passwd_age',
                },
                'Transform': {
                    'Get': '_seconds_to_days',
                    'Put': '_days_to_seconds'
                },
            },
            'MinPasswordLen': {
                'Policy': 'Minimum password length',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Password Policy'],
                'Settings': {
                    'Function': '_in_range_inclusive',
                    'Args': {'min': 0, 'max': 14}
                },
                'NetUserModal': {
                    'Modal': 0,
                    'Option': 'min_passwd_len',
                },
            },
            'PasswordComplexity': {
                'Policy': 'Passwords must meet complexity requirements',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Password Policy'],
                'Settings': [0, 1],
                'Secedit': {
                    'Option': 'PasswordComplexity',
                    'Section': 'System Access',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                },
            },
            'ClearTextPasswords': {
                'Policy': 'Store passwords using reversible encryption',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Password Policy'],
                'Settings': [0, 1],
                'Secedit': {
                    'Option': 'ClearTextPassword',
                    'Section': 'System Access',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                },
            },
            'AdminAccountStatus': {
                'Policy': 'Accounts: Administrator account status',
                'Settings': [0, 1],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Secedit': {
                    'Option': 'EnableAdminAccount',
                    'Section': 'System Access',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                },
            },
            'GuestAccountStatus': {
                'Policy': 'Accounts: Guest account status',
                'Settings': [0, 1],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Secedit': {
                    'Option': 'EnableGuestAccount',
                    'Section': 'System Access',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                },
            },
            'LimitBlankPasswordUse': {
                'Policy': 'Accounts: Limit local account use of blank passwords to console logon only',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Settings': [0, 1],
                'Registry': {
                    'Hive': 'HKEY_LOCAL_MACHINE',
                    'Path': 'SYSTEM\\CurrentControlSet\\Control\\Lsa',
                    'Value': 'limitblankpassworduse',
                    'Type': 'REG_DWORD',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                },
            },
            'RenameAdministratorAccount': {
                'Policy': 'Accounts: Rename administrator account',
                'Settings': None,
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Secedit': {
                    'Option': 'NewAdministratorName',
                    'Section': 'System Access',
                },
                'Transform': {
                    'Get': '_strip_quotes',
                    'Put': '_add_quotes',
                },
            },
            'RenameGuestAccount': {
                'Policy': 'Accounts: Rename guest account',
                'Settings': None,
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Secedit': {
                    'Option': 'NewGuestName',
                    'Section': 'System Access',
                },
                'Transform': {
                    'Get': '_strip_quotes',
                    'Put': '_add_quotes',
                },
            },
            'AuditBaseObjects': {
                'Policy': 'Audit: Audit the access of global system objects',
                'Settings': [0, 1],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Registry': {
                    'Hive': 'HKEY_LOCAL_MACHINE',
                    'Path': 'SYSTEM\\CurrentControlSet\\Control\\Lsa',
                    'Value': 'AuditBaseObjects',
                    'Type': 'REG_DWORD',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                },
            },
            'FullPrivilegeAuditing': {
                'Policy': 'Audit: Audit the use of Backup and Restore privilege',
                'Settings': [chr(0), chr(1)],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Registry': {
                    'Hive': 'HKEY_LOCAL_MACHINE',
                    'Path': 'System\\CurrentControlSet\\Control\\Lsa',
                    'Value': 'FullPrivilegeAuditing',
                    'Type': 'REG_BINARY',
                },
                'Transform': {
                    'Get': '_binary_enable0_disable1_conversion',
                    'Put': '_binary_enable0_disable1_reverse_conversion',
                },
            },
            'CrashOnAuditFail': {
                'Policy': 'Audit: Shut down system immediately if unable to log security audits',
                'Settings': [0, 1],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Registry': {
                    'Hive': 'HKEY_LOCAL_MACHINE',
                    'Path': 'SYSTEM\\CurrentControlSet\\Control\\Lsa',
                    'Value': 'CrashOnAuditFail',
                    'Type': 'REG_DWORD',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                },
            },
            'UndockWithoutLogon': {
                'Policy': 'Devices: Allow undock without having to log on',
                'Settings': [0, 1],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Registry': {
                    'Hive': 'HKEY_LOCAL_MACHINE',
                    'Path': 'Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System',
                    'Value': 'UndockWithoutLogon',
                    'Type': 'REG_DWORD',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                },
            },
            'AllocateDASD': {
                'Policy': 'Devices: Allowed to format and eject removable media',
                'Settings': ["", "0", "1", "2"],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Registry': {
                    'Hive': 'HKEY_LOCAL_MACHINE',
                    'Path': 'Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon',
                    'Value': 'AllocateDASD',
                    'Type': 'REG_SZ',
                },
                'Transform': {
                    'Get': '_dasd_conversion',
                    'Put': '_dasd_reverse_conversion',
                },
            },
            'AllocateCDRoms': {
                'Policy': 'Devices: Restrict CD-ROM access to locally logged-on user only',
                'Settings': ["0", "1"],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Registry': {
                    'Hive': 'HKEY_LOCAL_MACHINE',
                    'Path': 'Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon',
                    'Value': 'AllocateCDRoms',
                    'Type': 'REG_SZ',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                    'PutArgs': {'return_string': True}
                },
            },
            'AllocateFloppies': {
                'Policy': 'Devices: Restrict floppy access to locally logged-on user only',
                'Settings': ["0", "1"],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Registry': {
                    'Hive': 'HKEY_LOCAL_MACHINE',
                    'Path': 'Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon',
                    'Value': 'AllocateFloppies',
                    'Type': 'REG_SZ',
                },
                'Transform': {
                    'Get': '_enable1_disable0_conversion',
                    'Put': '_enable1_disable0_reverse_conversion',
                    'PutArgs': {'return_string': True}
                },
            },
            # see KB298503 why we aren't just doing this one via the registry
            'DriverSigningPolicy': {
                'Policy': 'Devices: Unsigned driver installation behavior',
                'Settings': ['3,0', '3,' + chr(1), '3,' + chr(2)],
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Security Options'],
                'Secedit': {
                    'Option': 'MACHINE\\Software\\Microsoft\\Driver Signing\\Policy',
                    'Section': 'Registry Values',
                },
                'Transform': {
                    'Get': '_driver_signing_reg_conversion',
                    'Put': '_driver_signing_reg_reverse_conversion',
                },
            },
            'LockoutDuration': {
                'Policy': 'Account lockout duration',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Account Lockout Policy'],
                'Settings': {
                    'Function': '_in_range_inclusive',
                    'Args': {'min': 0, 'max': 6000000}
                },
                'NetUserModal': {
                    'Modal': 3,
                    'Option': 'lockout_duration',
                },
                'Transform': {
                    'Get': '_seconds_to_minutes',
                    'Put': '_minutes_to_seconds',
                },
            },
            'LockoutThreshold': {
                'Policy': 'Account lockout threshold',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Account Lockout Policy'],
                'Settings': {
                    'Function': '_in_range_inclusive',
                    'Args': {'min': 0, 'max': 1000}
                },
                'NetUserModal': {
                    'Modal': 3,
                    'Option': 'lockout_threshold',
                }
            },
            'LockoutWindow': {
                'Policy': 'Reset account lockout counter after',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Account Lockout Policy'],
                'Settings': {
                    'Function': '_in_range_inclusive',
                    'Args': {'min': 0, 'max': 6000000}
                },
                'NetUserModal': {
                    'Modal': 3,
                    'Option': 'lockout_observation_window',
                },
                'Transform': {
                    'Get': '_seconds_to_minutes',
                    'Put': '_minutes_to_seconds'
                },
            },
            'AuditAccountLogon': {
                'Policy': 'Audit account logon events',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Account Policies',
                                 'Account Lockout Policy'],
                'Settings': [0, 1, 2, 3],
                'Secedit': {
                    'Option': 'AuditAccountLogon',
                    'Section': 'Event Audit',
                },
                'Transform': {
                    'Get': '_event_audit_conversion',
                    'Put': '_event_audit_reverse_conversion',
                },
            },
            'AuditAccountManage': {
                'Policy': 'Audit account management',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Settings': [0, 1, 2, 3],
                'Secedit': {
                    'Option': 'AuditAccountManage',
                    'Section': 'Event Audit',
                },
                'Transform': {
                    'Get': '_event_audit_conversion',
                    'Put': '_event_audit_reverse_conversion',
                },
            },
            'AuditDSAccess': {
                'Policy': 'Audit directory service access',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Settings': [0, 1, 2, 3],
                'Secedit': {
                    'Option': 'AuditDSAccess',
                    'Section': 'Event Audit',
                },
                'Transform': {
                    'Get': '_event_audit_conversion',
                    'Put': '_event_audit_reverse_conversion',
                },
            },
            'AuditLogonEvents': {
                'Policy': 'Audit logon events',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Settings': [0, 1, 2, 3],
                'Secedit': {
                    'Option': 'AuditLogonEvents',
                    'Section': 'Event Audit',
                },
                'Transform': {
                    'Get': '_event_audit_conversion',
                    'Put': '_event_audit_reverse_conversion',
                },
            },
            'AuditObjectAccess': {
                'Policy': 'Audit object access',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Settings': [0, 1, 2, 3],
                'Secedit': {
                    'Option': 'AuditObjectAccess',
                    'Section': 'Event Audit',
                },
                'Transform': {
                    'Get': '_event_audit_conversion',
                    'Put': '_event_audit_reverse_conversion',
                },
            },
            'AuditPolicyChange': {
                'Policy': 'Audit policy change',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Settings': [0, 1, 2, 3],
                'Secedit': {
                    'Option': 'AuditPolicyChange',
                    'Section': 'Event Audit',
                },
                'Transform': {
                    'Get': '_event_audit_conversion',
                    'Put': '_event_audit_reverse_conversion',
                },
            },
            'AuditPrivilegeUse': {
                'Policy': 'Audit privilege use',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Settings': [0, 1, 2, 3],
                'Secedit': {
                    'Option': 'AuditPrivilegeUse',
                    'Section': 'Event Audit',
                },
                'Transform': {
                    'Get': '_event_audit_conversion',
                    'Put': '_event_audit_reverse_conversion',
                },
            },
            'AuditProcessTracking': {
                'Policy': 'Audit process tracking',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Settings': [0, 1, 2, 3],
                'Secedit': {
                    'Option': 'AuditProcessTracking',
                    'Section': 'Event Audit',
                },
                'Transform': {
                    'Get': '_event_audit_conversion',
                    'Put': '_event_audit_reverse_conversion',
                },
            },
            'AuditSystemEvents': {
                'Policy': 'Audit system events',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'Audit Policy'],
                'Settings': [0, 1, 2, 3],
                'Secedit': {
                    'Option': 'AuditSystemEvents',
                    'Section': 'Event Audit',
                },
                'Transform': {
                    'Get': '_event_audit_conversion',
                    'Put': '_event_audit_reverse_conversion',
                },
            },
            'SeTrustedCredManAccessPrivilege': {
                'Policy': 'Access Credential Manager as a trusted caller',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeTrustedCredManAccessPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeNetworkLogonRight': {
                'Policy': 'Access this computer from the network',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeNetworkLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeTcbPrivilege': {
                'Policy': 'Act as part of the operating system',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeTcbPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeMachineAccountPrivilege': {
                'Policy': 'Add workstations to domain',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeMachineAccountPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeIncreaseQuotaPrivilege': {
                'Policy': 'Adjust memory quotas for a process',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeIncreaseQuotaPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeInteractiveLogonRight': {
                'Policy': 'Allow logon locally',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeInteractiveLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeRemoteInteractiveLogonRight': {
                'Policy': 'Allow logon through Remote Desktop Services',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeRemoteInteractiveLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeBackupPrivilege': {
                'Policy': 'Backup files and directories',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeBackupPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeChangeNotifyPrivilege': {
                'Policy': 'Bypass traverse checking',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeChangeNotifyPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeSystemtimePrivilege': {
                'Policy': 'Change the system time',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeSystemtimePrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeTimeZonePrivilege': {
                'Policy': 'Change the time zone',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeTimeZonePrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeCreatePagefilePrivilege': {
                'Policy': 'Create a pagefile',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeCreatePagefilePrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeCreateTokenPrivilege': {
                'Policy': 'Create a token object',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeCreateTokenPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeCreateGlobalPrivilege': {
                'Policy': 'Create global objects',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeCreateGlobalPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeCreatePermanentPrivilege': {
                'Policy': 'Create permanent shared objects',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeCreatePermanentPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeCreateSymbolicLinkPrivilege': {
                'Policy': 'Create symbolic links',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeCreateSymbolicLinkPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeDebugPrivilege': {
                'Policy': 'Debug programs',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeDebugPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeDenyNetworkLogonRight': {
                'Policy': 'Deny access to this computer from the network',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeDenyNetworkLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeDenyBatchLogonRight': {
                'Policy': 'Deny log on as a batch job',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeDenyBatchLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeDenyServiceLogonRight': {
                'Policy': 'Deny log on as a service',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeDenyServiceLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeDenyInteractiveLogonRight': {
                'Policy': 'Deny log on locally',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeDenyInteractiveLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeDenyRemoteInteractiveLogonRight': {
                'Policy': 'Deny log on through Remote Desktop Services',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeDenyRemoteInteractiveLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeEnableDelegationPrivilege': {
                'Policy': 'Enable computer and user accounts to be trusted for delegation',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeEnableDelegationPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeRemoteShutdownPrivilege': {
                'Policy': 'Force shutdown from a remote system',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeRemoteShutdownPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeAuditPrivilege': {
                'Policy': 'Generate security audits',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeAuditPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeImpersonatePrivilege': {
                'Policy': 'Impersonate a client after authentication',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeImpersonatePrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeIncreaseWorkingSetPrivilege': {
                'Policy': 'Increase a process working set',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeIncreaseWorkingSetPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeIncreaseBasePriorityPrivilege': {
                'Policy': 'Increase scheduling priority',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeIncreaseBasePriorityPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeLoadDriverPrivilege': {
                'Policy': 'Load and unload device drivers',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeLoadDriverPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeLockMemoryPrivilege': {
                'Policy': 'Lock pages in memory',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeLockMemoryPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeBatchLogonRight': {
                'Policy': 'Log on as a batch job',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeBatchLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeServiceLogonRight': {
                'Policy': 'Log on as a service',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeServiceLogonRight'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeSecurityPrivilege': {
                'Policy': 'Manage auditing and security log',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeSecurityPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeRelabelPrivilege': {
                'Policy': 'Modify an object label',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeRelabelPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeSystemEnvironmentPrivilege': {
                'Policy': 'Modify firmware environment values',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeSystemEnvironmentPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeManageVolumePrivilege': {
                'Policy': 'Perform volume maintenance tasks',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeManageVolumePrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeProfileSingleProcessPrivilege': {
                'Policy': 'Profile single process',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeProfileSingleProcessPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeSystemProfilePrivilege': {
                'Policy': 'Profile system performance',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeSystemProfilePrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeUndockPrivilege': {
                'Policy': 'Remove computer from docking station',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeUndockPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeAssignPrimaryTokenPrivilege': {
                'Policy': 'Replace a process level token',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeAssignPrimaryTokenPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeRestorePrivilege': {
                'Policy': 'Restore files and directories',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeRestorePrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeShutdownPrivilege': {
                'Policy': 'Shut down the system',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeShutdownPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeSyncAgentPrivilege': {
                'Policy': 'Synchronize directory service data',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeSyncAgentPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
            'SeTakeOwnershipPrivilege': {
                'Policy': 'Take ownership of files and other objects',
                'lgpo_section': ['Computer Configuration',
                                 'Windows Settings',
                                 'Security Settings',
                                 'Local Policies',
                                 'User Rights Assignment'],
                'Settings': None,
                'LsaRights': {
                    'Option': 'SeTakeOwnershipPrivilege'
                },
                'Transform': {
                    'Get': '_sidConversion',
                    'Put': '_usernamesToSidObjects',
                },
            },
        }
        self.admx_registry_classes = {
            'User': {
                'policy_path': os.path.join(os.getenv('WINDIR'), 'System32', 'GroupPolicy', 'User', 'Registry.pol'),
                'hive': 'HKEY_USERS',
                'lgpo_section': 'User Configuration'
            },
            'Machine': {
                'policy_path': os.path.join(os.getenv('WINDIR'), 'System32', 'GroupPolicy', 'Machine', 'Registry.pol'),
                'hive': 'HKEY_LOCAL_MACHINE',
                'lgpo_section': 'Computer Configuration',
            },
        }
        self.reg_pol_header = u'\u5250\u6765\x01\x00'

    def _admTemplateSimple(self, val, **kwargs):
        '''
        Simple adm template verification for an Enabled/Disabled template setting
        '''
        if isinstance(val, string_types):
            if val.upper() in ['ENABLED', 'DISABLED', 'NOT CONFIGURED']:
                return True
        return False

    def _admTemplateSimpleReverse(self, val, admPolicy=None, **kwargs):
        '''
        Convert an enable value from a template to the string representation
        '''
        if val.upper() == 'DISABLED' or val.upper() == 'NOT CONFIGURED':
            return val
        elif 'EnableValue' in self.policies[admPolicy]['AdmRegistry']:
            if not isinstance(self.policies[admPolicy]['AdmRegistry']['EnableValue'], string_types):
                val = ord(val)
            if self.policies[admPolicy]['AdmRegistry']['EnableValue'] == val:
                return 'Enabled'
        else:
            return 'Unexpected setting of {0}'.format(val)

    def _notEmpty(self, val, **kwargs):
        '''
        ensures a value is not empty
        '''
        if val:
            return True
        else:
            return False

    def _admTemplateParentSetting(self, val, parent_policy_name=None, **kwargs):
        '''
        verifies an adm 'parent' template setting value is either 'enabled', 'disabled', or 'not configured'
        '''
        log.debug('validating {0}'.format(val))
        if isinstance(val, dict):
            log.debug('we have a dict value for the adm template val')
            log.debug('we have parent_policy_name of {0}'.format(parent_policy_name))
            if parent_policy_name:
                if parent_policy_name in self.policies:
                    for _k in self.policies[parent_policy_name]['Children'].keys():
                        if _k not in val:
                            return False
                    log.debug('we have all the required child entries in the dict')
                    return True
                else:
                    return False
        elif isinstance(val, string_types):
            log.debug('we have just a string')
            if val.upper() in ['ENABLED', 'DISABLED', 'NOT CONFIGURED']:
                return True
            else:
                return False
        else:
            return False
        return False

    def _enable1_disable0_conversion(self, val, **kwargs):
        '''
        converts a reg dword 1/0 value to the strings enable/disable
        '''
        if val is not None:
            if val == 1 or val == "1":
                return 'Enabled'
            elif val == 0 or val == "0":
                return 'Disabled'
            elif val == '(value not set)':
                return 'Not Defined'
            else:
                return 'Invalid Value'
        else:
            return 'Not Defined'

    def _enable1_disable0_reverse_conversion(self, val, **kwargs):
        '''
        converts Enable/Disable to 1/0
        '''
        return_string = False
        if 'return_string' in kwargs:
            return_string = True
        if val is not None:
            if val.upper() == 'ENABLED':
                if return_string:
                    return '1'
                else:
                    return 1
            elif val.upper() == 'DISABLED':
                if return_string:
                    return '0'
                else:
                    return 0
            else:
                return None
        else:
            return None

    def _event_audit_conversion(self, val, **kwargs):
        '''
        converts an audit setting # (0, 1, 2, 3) to the string text
        '''
        if val is not None:
            if val == 0 or val == "0":
                return 'No auditing'
            elif val == 1 or val == "1":
                return 'Success'
            elif val == 2 or val == "2":
                return 'Failure'
            elif val == 3 or val == "3":
                return 'Succes, Failure'
            else:
                return 'Invalid Auditing Value'
        else:
            return 'Not Defined'

    def _event_audit_reverse_conversion(self, val, **kwargs):
        '''
        converts audit strings to numerical values
        '''
        if val is not None:
            if val.upper() == 'NO AUDITING':
                return 0
            elif val.upper() == 'SUCCESS':
                return 1
            elif val.upper() == 'FAILURE':
                return 2
            elif val.upper() == 'SUCCESS, FAILURE':
                return 3
        else:
            return 'Not Defined'

    def _seconds_to_days(self, val, **kwargs):
        '''
        converts a number of seconds to days
        '''
        if val is not None:
            return val / 86400
        else:
            return 'Not Defined'

    def _days_to_seconds(self, val, **kwargs):
        '''
        converts a number of days to seconds
        '''
        if val is not None:
            return val * 86400
        else:
            return 'Not Defined'

    def _seconds_to_minutes(self, val, **kwargs):
        '''
        converts a number of seconds to minutes
        '''
        if val is not None:
            return val / 60
        else:
            return 'Not Defined'

    def _minutes_to_seconds(self, val, **kwargs):
        '''
        converts number of minutes to seconds
        '''
        if val is not None:
            return val * 60
        else:
            return 'Not Defined'

    def _strip_quotes(self, val, **kwargs):
        '''
        strips quotes from a string
        '''
        return val.replace('"', '')

    def _add_quotes(self, val, **kwargs):
        '''
        add quotes around the string
        '''
        return '"{0}"'.format(val)

    def _binary_enable0_disable1_conversion(self, val, **kwargs):
        '''
        converts a binary 0/1 to Disabled/Enabled
        '''
        if val is not None:
            if ord(val) == 0:
                return 'Disabled'
            elif ord(val) == 1:
                return 'Enabled'
            else:
                return 'Invalid Value'
        else:
            return 'Not Defined'

    def _binary_enable0_disable1_reverse_conversion(self, val, **kwargs):
        '''
        converts Enabled/Disabled to unicode char to write to a REG_BINARY value
        '''
        if val is not None:
            if val.upper() == 'DISABLED':
                return chr(0)
            elif val.upper() == 'ENABLED':
                return chr(1)
            else:
                return None
        else:
            return None

    def _dasd_conversion(self, val, **kwargs):
        '''
        converts 0/1/2 for dasd reg key
        '''
        if val is not None:
            if val == '0' or val == 0 or val == '':
                return 'Administrtors'
            elif val == '1' or val == 1:
                return 'Administrators and Power Users'
            elif val == '2' or val == 2:
                return 'Administrators and Interactive Users'
            else:
                return 'Not Defined'
        else:
            return 'Not Defined'

    def _dasd_reverse_conversion(self, val, **kwargs):
        '''
        converts DASD String values to the reg_sz value
        '''
        if val is not None:
            if val.upper() == 'ADMINISTRATORS':
                # "" also shows 'administrators' in the gui
                return '0'
            elif val.upper() == 'ADMINISTRATORS AND POWER USERS':
                return '1'
            elif val.upper() == 'ADMINISTRATORS AND INTERACTIVE USERS':
                return '2'
            elif val.upper() == 'NOT DEFINED':
                # a setting of anything other than nothing,0,1,2 or if they doesn't exist shows 'not defined'
                return '9999'
            else:
                return 'Invalid Value'
        else:
            return 'Not Defined'

    def _in_range_inclusive(self, val, **kwargs):
        '''
        checks that a value is in an inclusive range
        '''
        min = 0
        max = 1
        if 'min' in kwargs:
            min = kwargs['min']
        if 'max' in kwargs:
            max = kwargs['max']
        if val is not None:
            if val >= min and val <= max:
                return True
            else:
                return False
        else:
            return False

    def _driver_signing_reg_conversion(self, val, **kwargs):
        '''
        converts the binary value in the registry for driver signing into the correct string representation
        '''
        log.debug('we have {0} for the driver signing value'.format(val))
        if val is not None:
            # since this is from secedit, it should be 3,<value>
            _val = val.split(',')
            if len(_val) == 2:
                if _val[1] == '0':
                    return 'Silently Succeed'
                elif _val[1] == '1':
                    return 'Warn but allow installation'
                elif _val[1] == '2':
                    return 'Do not allow installation'
                elif _val[1] == 'Not Defined':
                    return 'Not Defined'
                else:
                    return 'Invalid Value'
            else:
                return 'Not Defined'
        else:
            return 'Not Defined'

    def _driver_signing_reg_reverse_conversion(self, val, **kwargs):
        '''
        converts the string value seen in the gui to the correct registry value for seceit
        '''
        if val is not None:
            if val.upper() == 'SILENTLY SUCCEED':
                return ','.join(['3', '0'])
            elif val.upper() == 'WARN BUT ALLOW INSTALLATION':
                return ','.join(['3', chr(1)])
            elif val.upper() == 'DO NOT ALLOW INSTALLATION':
                return ','.join(['3', chr(2)])
            else:
                return 'Invalid Value'
        else:
            return 'Not Defined'

    def _sidConversion(self, val, **kwargs):
        '''
        converts a list of pysid objects to string representations
        '''
        if isinstance(val, string_types):
            val = val.split(',')
        usernames = []
        for _sid in val:
            try:
                userSid = win32security.LookupAccountSid('', _sid)
                if userSid[1]:
                    userSid = '{1}\\{0}'.format(userSid[0], userSid[1])
                else:
                    userSid = '{0}'.format(userSid[0])
            except Exception:
                userSid = win32security.ConvertSidToStringSid(_sid)
            usernames.append(userSid)
        return usernames

    def _usernamesToSidObjects(self, val, **kwargs):
        '''
        converts a list of usernames to sid objects
        '''
        if not val:
            return val
        if isinstance(val, string_types):
            val = val.split(',')
        sids = []
        for _user in val:
            try:
                sid = win32security.LookupAccountName('', _user)[0]
                sids.append(sid)
            except Exception as e:
                raise CommandExecutionError((
                    'There was an error obtaining the SID of user "{0}".  Error returned: {1}'
                    ).format(_user, e))
        return sids

    def _powershell_script_order_conversion(self, val, **kwargs):
        '''
        converts true/false/None to the GUI representation of the powershell startup/shutdown script order
        '''
        log.debug('script order value = {0}'.format(val))
        if val is None or val == 'None':
            return 'Not Configured'
        elif val == 'true':
            return 'Run Windows PowerShell scripts first'
        elif val == 'false':
            return 'Run Windows PowerShell scripts last'
        else:
            return 'Invalid Value'

    def _powershell_script_order_reverse_conversion(self, val, **kwargs):
        if val.upper() == 'Run Windows PowerShell scripts first'.upper():
            return 'true'
        elif val.upper() == 'Run Windows PowerShell scripts last'.upper():
            return 'false'
        elif val is 'Not Configured':
            return None
        else:
            return 'Invalid Value'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows() and HAS_WINDOWS_MODULES:
        return __virtualname__
    return False


def _updateNamespace(item, newNamespace):
    '''
    helper function to recursively update the namespaces of an item
    '''
    temp_item = ''
    i = item.tag.find('}')
    if i >= 0:
        temp_item = item.tag[i+1:]
    else:
        temp_item = item.tag
    item.tag = '{{{0}}}{1}'.format(newNamespace, temp_item)
    for child in item.getiterator():
        if isinstance(child.tag, string_types):
            temp_item = ''
            i = child.tag.find('}')
            if i >= 0:
                temp_item = child.tag[i+1:]
            else:
                temp_item = child.tag
            child.tag = '{{{0}}}{1}'.format(newNamespace, temp_item)
    return item


def _updatePolicyElements(policy_item, regkey):
    '''
    helper function to add the reg key to each policies element definitions if the key attribute is not defined to make xpath searching easier
    for each child in the policy <elements> item
    '''
    for child in policy_item.getiterator():
        if 'valueName' in child.attrib:
            if 'key' not in child.attrib:
                child.attrib['key'] = regkey
    return policy_item


def _processPolicyDefinitions(polDefPath='c:\\Windows\\PolicyDefinitions', display_language='en-US'):
    '''
    helper function to process all ADMX files in the specified polDefPath
    and build a single XML doc that we can search/use for admx polic processing
    '''
    display_language_fallback = 'en-US'
    t_PolicyDefinitions = lxml.etree.Element('policyDefinitions')
    t_PolicyDefinitions.append(lxml.etree.Element('categories'))
    t_PolicyDefinitions.append(lxml.etree.Element('policies'))
    t_PolicyDefinitions.append(lxml.etree.Element('policyNamespaces'))
    t_PolicyDefinitionResources = lxml.etree.Element('policyDefinitionResources')
    for root, dirs, files in os.walk(polDefPath):
        if root == polDefPath:
            for t_admFile in files:
                admFile = os.path.join(root, t_admFile)
                xmltree = lxml.etree.parse(admFile)
                namespaces = xmltree.getroot().nsmap
                namespaceString = ''
                if None in namespaces:
                    namespaces['None'] = namespaces[None]
                    namespaces.pop(None)
                    namespaceString = 'None:'
                thisPrefix = xmltree.xpath('/{0}policyDefinitions/{0}policyNamespaces/{0}target/@prefix'.format(namespaceString),
                                           namespaces=namespaces)[0]
                thisNamespace = xmltree.xpath('/{0}policyDefinitions/{0}policyNamespaces/{0}target/@namespace'.format(namespaceString),
                                              namespaces=namespaces)[0]
                categories = xmltree.xpath('/{0}policyDefinitions/{0}categories/{0}category'.format(namespaceString),
                                           namespaces=namespaces)
                for category in categories:
                    tCat = category
                    tCat = _updateNamespace(tCat, thisNamespace)
                    t_PolicyDefinitions.xpath('/policyDefinitions/categories')[0].append(tCat)
                policies = xmltree.xpath('/{0}policyDefinitions/{0}policies/{0}policy'.format(namespaceString),
                                         namespaces=namespaces)
                for policy in policies:
                    tPol = policy
                    tPol = _updateNamespace(tPol, thisNamespace)
                    if 'key' in tPol.attrib:
                        tPol = _updatePolicyElements(tPol, tPol.attrib['key'])
                    t_PolicyDefinitions.xpath('/policyDefinitions/policies')[0].append(tPol)
                policyNamespaces = xmltree.xpath('/{0}policyDefinitions/{0}policyNamespaces/{0}*'.format(namespaceString),
                                                 namespaces=namespaces)
                for policyNamespace in policyNamespaces:
                    tPolNs = policyNamespace
                    tPolNs = _updateNamespace(tPolNs, thisNamespace)
                    t_PolicyDefinitions.xpath('/policyDefinitions/policyNamespaces')[0].append(tPolNs)
                admlFile = os.path.join(root, display_language, os.path.splitext(t_admFile)[0] + '.adml')
                if not __salt__['file.file_exists'](admlFile):
                    log.info('An adml file in the specified adml language "{0}" does not exist for the admx "{1}", the fallback languange will be tried.'.format(display_language, t_admFile))
                    admlFile = os.path.join(root, displayLanguageFallback, os.path.splitext(t_admFile)[0] + '.adml')
                    if not __salt__['file.file_exists'](admlFile):
                        msg = 'An adml file in the specified adml language "{0}" and the fallback language "{1}" do not exist for the admx "{2}".'.format(display_language, displayLanguageFallback, t_admFile)
                        raise SaltInvocationError(msg)
                xmltree = lxml.etree.parse(admlFile)
                if None in namespaces:
                    namespaces['None'] = namespaces[None]
                    namespaces.pop(None)
                    namespaceString = 'None:'
                polDefResources = xmltree.xpath('//*[local-name() = "policyDefinitionResources"]/*')
                for polDefResource in polDefResources:
                    tPolDef = polDefResource
                    tPolDef = _updateNamespace(tPolDef, thisNamespace)
                    t_PolicyDefinitionResources.xpath('/policyDefinitionResources')[0].append(tPolDef)
    return (t_PolicyDefinitions, t_PolicyDefinitionResources)


def _buildElementNsmap(usingElements):
    '''
    build a namespace map for an ADMX element
    '''
    thisMap = {}
    for e in usingElements:
        thisMap[e.attrib['prefix']] = e.attrib['namespace']
    return thisMap


def _findOptionValueInSeceditFile(option):
    '''
    helper function to dump/parse a `secedit /export` file for a particular option
    '''
    try:
        _d = uuid.uuid4().hex
        _tfile = '{0}\\{1}'.format(__salt__['config.get']('cachedir'), 'salt-secedit-dump-{0}.txt'.format(_d))
        _ret = __salt__['cmd.run']('secedit /export /cfg {0}'.format(_tfile))
        if _ret:
            _reader = codecs.open(_tfile, 'r', encoding='utf-16')
            _secdata = _reader.readlines()
            _reader.close()
            _ret = __salt__['file.remove'](_tfile)
            for _line in _secdata:
                if _line.startswith(option):
                    return True, _line.split('=')[1].strip()
        return True, 'Not Defined'
    except:
        log.debug('error occurred while trying to get secedit data')
        return False, None


def _importSeceditConfig(infData):
    '''
    helper function to write data to a temp file/run secedit to import policy/cleanup
    '''
    try:
        _d = uuid.uuid4().hex
        _tSdbfile = '{0}\\{1}'.format(__salt__['config.get']('cachedir'), 'salt-secedit-import-{0}.sdb'.format(_d))
        _tInfFile = '{0}\\{1}'.format(__salt__['config.get']('cachedir'), 'salt-secedit-config-{0}.inf'.format(_d))
        # make sure our temp files don't already exist
        _ret = __salt__['file.remove'](_tSdbfile)
        _ret = __salt__['file.remove'](_tInfFile)
        # add the inf data to the file, win_file sure could use the write() function
        _ret = __salt__['file.touch'](_tInfFile)
        _ret = __salt__['file.append'](_tInfFile, infData)
        # run secedit to make the change
        _ret = __salt__['cmd.run']('secedit /configure /db {0} /cfg {1}'.format(_tSdbfile, _tInfFile))
        # cleanup our temp files
        _ret = __salt__['file.remove'](_tSdbfile)
        _ret = __salt__['file.remove'](_tInfFile)
        return True
    except:
        log.debug('error occurred while trying to import secedit data')
        return False


def _transformValue(value, policy, transformType):
    '''
    helper function to transform the policy value into something that more closely matches how the policy is displayed in the gpedit gui
    '''
    t_kwargs = {}
    if 'Transform' in policy:
        if transformType in policy['Transform']:
            _policydata = _policy_info()
            if transformType + 'Args' in policy['Transform']:
                t_kwargs = policy['Transform'][transformType + 'Args']
            return getattr(_policydata, policy['Transform'][transformType])(value, **t_kwargs)
        else:
            return value
    else:
        return value


def _validateSetting(value, policy):
    '''
    helper function to validate specified value is appropriate for the policy
    if the 'Settings' key is a list, the value will checked that it is in the list
    if the 'Settings' key is a dict
        we will try to execute the function name from the 'Function' key, passing the value and additional arguments from the 'Args' dict
    if the 'Settings' key is None, we won't do any validation and just return True
    if the Policy has 'Children', we'll validate their settings too
    '''
    log.debug('validating {0} for policy {1}'.format(value, policy))
    if 'Settings' in policy:
        if policy['Settings']:
            if isinstance(policy['Settings'], list):
                if value not in policy['Settings']:
                    return False
            elif isinstance(policy['Settings'], dict):
                _policydata = _policy_info()
                if not getattr(_policydata, policy['Settings']['Function'])(value, **policy['Settings']['Args']):
                    return False
    else:
        return True

    return True


def _addAccountRights(sidObject, userRight):
    '''
    helper function to add an account right to a user
    '''
    try:
        if sidObject:
            _polHandle = win32security.LsaOpenPolicy(None, win32security.POLICY_ALL_ACCESS)
            userRightsList = [userRight]
            _ret = win32security.LsaAddAccountRights(_polHandle, sidObject, userRightsList)
        return True
    except Exception as e:
        log.error('Error attempting to add account right, exception was {0}'.format(e))
        return False


def _delAccountRights(sidObject, userRight):
    '''
    helper function to remove an account right from a user
    '''
    try:
        _polHandle = win32security.LsaOpenPolicy(None, win32security.POLICY_ALL_ACCESS)
        userRightsList = [userRight]
        _ret = win32security.LsaRemoveAccountRights(_polHandle, sidObject, False, userRightsList)
        return True
    except Exception as e:
        log.error('Error attempting to delete account right, exception was {0}'.format(e))
        return False


def _getRightsAssignments(userRight):
    '''
    helper function to return all the user rights assignments/users
    '''
    sids = []
    _polHandle = win32security.LsaOpenPolicy(None, win32security.POLICY_ALL_ACCESS)
    _sids = win32security.LsaEnumerateAccountsWithUserRight(_polHandle, userRight)
    return _sids


def _getAdmlDisplayName(admlXmlData, displayNameAttributeValue):
    '''
    helper function to take the 'displayName' attribute of an element and find the value from the ADML data
    '''
    if displayNameAttributeValue.startswith('$(') and displayNameAttributeValue.endswith(')'):
        displayNameAttributeValue = re.sub(r'(^\$\(|\)$)', '', displayNameAttributeValue)
        log.debug('I would search for {0}'.format(displayNameAttributeValue))
        displayNameAttributeValue = displayNameAttributeValue.split('.')
        displayNameType = displayNameAttributeValue[0]
        displayNameId = displayNameAttributeValue[1]
        search_results = admlXmlData.xpath('//*[local-name() = "{0}" and @*[local-name() = "id"] = "{1}"]'.format(displayNameType, displayNameId))
        if search_results:
            for result in search_results:
                return result.text

    return None


def _getFullPolicyName(polItem, policyName, return_full_policy_names, admlPolicyData):
    '''
    helper function to retrieve the full policy name if needed
    '''
    if return_full_policy_names and 'displayName' in polItem.attrib:
        fullPolicyName = _getAdmlDisplayName(admlPolicyData, polItem.attrib['displayName'])
        if fullPolicyName:
            policyName = fullPolicyName
    elif return_full_policy_names and 'valueName' in polItem.attrib:
        # some policies don't have a display name, but instead use the 'valueName' in the gui
        policyName = polItem.attrib['valueName']

    return policyName


def _getAllAdminTemplateSettingsFromRegPolFile(policyClass,
                                               return_full_policy_names=False,
                                               heirarchical_return=False,
                                               display_language='en-US'):
    u'''
    helper function to get all ADM teplate settings from the registry.pol file

    each file begins with REGFILE_SIGNATURE (u'\u5250\u6765') and REGISTRY_FILE_VERSION (u'\x01\00')

    https://msdn.microsoft.com/en-us/library/aa374407(VS.85).aspx
    [Registry Path<NULL>;Reg Value<NULL>;Reg Type<NULL>;SizeInBytes<NULL>;Data<NULL>]
    '''
    _existingData = None
    _policyData = _policy_info()
    admxPolicyDefinitions, admlPolicyResources = _processPolicyDefinitions(display_language=display_language)
    _val = {}
    registry = Registry()
    heirarchy = {}
    try:
        log.debug('working with policyClass :: {0}'.format(policyClass))
        log.debug('reg pol file: {0}'.format(_policyData.admx_registry_classes[policyClass]['policy_path']))
        polFileData = _readRegPolFile(_policyData.admx_registry_classes[policyClass]['policy_path'])
        specialValueRegex = r'(\*\*DeleteValues|\*\*Del\.|\*\*DelVals\.|\*\*DeleteKeys)'
        if polFileData:
            polFileData = re.sub(r'\]$', '', re.sub(r'^\[', '', polFileData.replace(_policyData.reg_pol_header, ''))).split('][')
            if polFileData:
                for polItem in polFileData:
                    if polItem:
                        disabledPolicy = False
                        polItem = polItem.split('{0};'.format(chr(0)))
                        key = polItem[0]
                        value = polItem[1]
                        regtype = polItem[2]
                        log.debug('working with regpol data key :: {0} value :: {1}'.format(key, value))
                        if re.match(specialValueRegex, value, re.IGNORECASE):
                            log.debug('is a special meaning value that the policy is disabled')
                            disabledPolicy = True
                            value = re.sub(specialValueRegex, '', value, flags=re.IGNORECASE)
                            log.debug('value is now {0}'.format(value))
                        search_results = admxPolicyDefinitions.xpath('//*[translate(@*[local-name() = "key"], "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz") = "{0}" and @*[local-name() = "valueName"] = "{1}"]'.format(key.lower(), value))
                        if search_results:
                            for thisPolicyDef in search_results:
                                setting = polItem[4].rstrip(chr(0))
                                parentPolicyName = None
                                parentPolicyElement = None
                                policyName = None
                                if etree.QName(thisPolicyDef.tag).localname == 'policy':
                                    policyName = _getFullPolicyName(thisPolicyDef,
                                                                    thisPolicyDef.attrib['name'],
                                                                    return_full_policy_names,
                                                                    admlPolicyResources)
                                    # this is a value based enable/disable policy
                                    log.debug('value based enabled/disabled policy')
                                    if _checkPolicyEnableDisableElement(thisPolicyDef,
                                                                        '*[local-name() = "enabledValue" or local-name() = "enabledList"]',
                                                                        setting):
                                        _val[policyName] = 'Enabled'
                                    else:
                                        if _checkPolicyEnableDisableElement(thisPolicyDef,
                                                                            '*[local-name() = "disabledValue" or local-name() = "disabledList"]',
                                                                            setting):
                                            _val[policyName] = 'Disabled'
                                        else:
                                            log.debug('unable to match enabled or disabled settings for {0}'.format(policyName))
                                elif etree.QName(thisPolicyDef.tag).localname == 'item':
                                    policyName = _getFullPolicyName(thisPolicyDef,
                                                                    thisPolicyDef.attrib['name'],
                                                                    return_full_policy_names,
                                                                    admlPolicyResources)
                                    # this is a enable/disableList item
                                    log.debug('enabled/disabled list item')
                                    if _checkPolicyEnableDisableElement(thisPolicyDef, '*[local-name() = "value"]', setting):
                                        parentPolicyName, parentPolicyElement = _getParentPolicyName(thisPolicyDef,
                                                                                                     admlPolicyResources,
                                                                                                     return_full_policy_names)
                                        if etree.QName(thisPolicyDef.getparent()).localname == 'enabledList':
                                            setting = 'Enabled'
                                        elif etree.QName(thisPolicyDef.getparent()).localname == 'disabledList':
                                            setting = 'Disabled'
                                        if parentPolicyName not in _val:
                                            _val[parentPolicyName] = setting
                                else:
                                    policyName = _getFullPolicyName(thisPolicyDef,
                                                                    thisPolicyDef.attrib['id'],
                                                                    return_full_policy_names,
                                                                    admlPolicyResources)
                                    log.debug('{0} looks to be an element of a policy:: {1}'.format(policyName,
                                                                                                    thisPolicyDef.tag))
                                    parentPolicyName, parentPolicyElement = _getParentPolicyName(thisPolicyDef,
                                                                                                 admlPolicyResources,
                                                                                                 return_full_policy_names)
                                    if parentPolicyName not in _val:
                                        if disabledPolicy:
                                            _val[parentPolicyName] = 'Disabled'
                                        else:
                                            _val[parentPolicyName] = {'state': 'Enabled'}
                                    log.debug('found policyDefinition :: {0}'.format(thisPolicyDef.attrib))
                                    if not disabledPolicy:
                                        if registry.vtype_reverse[ord(regtype)] == 'REG_DWORD':
                                            if not setting:
                                                setting = chr(0)
                                            setting = ord(setting)
                                        if parentPolicyName:
                                            _val[parentPolicyName][policyName] = setting
                                if heirarchical_return:
                                    # may or may not have a parent policy
                                    if parentPolicyName:
                                        log.debug('building parent list for parent policy {0}'.format(parentPolicyName))
                                        heirarchy[parentPolicyName] = _buildParentList(parentPolicyElement,
                                                                                       admxPolicyDefinitions,
                                                                                       return_full_policy_names,
                                                                                       admlPolicyResources)
                                    else:
                                        log.debug('building heirarcy for policy {0}'.format(policyName))
                                        heirarchy[policyName] = _buildParentList(thisPolicyDef,
                                                                                 admxPolicyDefinitions,
                                                                                 return_full_policy_names,
                                                                                 admlPolicyResources)
                        else:
                            setting = polItem[4].rstrip(chr(0))
                            log.debug('no search results, checking if it is an explicit value list for key {0}'.format(key))
                            # make sure this key doesn't exist in a explicit value list
                            search_results = admxPolicyDefinitions.xpath('//*[translate(@*[local-name() = "key"], "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz") = "{0}" and @*[local-name() = "explicitValue"] = "true"]'.format(key.lower()))

                            log.debug('explicitValue search results == {0}'.format(search_results))
                            for thisPolicyDef in search_results:
                                policyName = _getFullPolicyName(thisPolicyDef,
                                                                thisPolicyDef.attrib['id'],
                                                                return_full_policy_names,
                                                                admlPolicyResources)
                                parentPolicyName, parentPolicyElement = _getParentPolicyName(thisPolicyDef,
                                                                                             admlPolicyResources,
                                                                                             return_full_policy_names)
                                if parentPolicyName not in _val:
                                    # TODO handle disabled policy
                                    _val[parentPolicyName] = {'state': 'Enabled'}
                                else:
                                    if isinstance(_val[parentPolicyName], string_types):
                                        _val[parentPolicyName] = {'state': 'Enabled'}
                                if not disabledPolicy:
                                    if policyName in _val[parentPolicyName]:
                                        _val[parentPolicyName][policyName][value] = setting
                                    else:
                                        _val[parentPolicyName][policyName] = {value: setting}
                                if heirarchical_return:
                                    # only a parent policy is applicable here
                                    log.debug('building parent list for {0}'.format(parentPolicyName))
                                    heirarchy[parentPolicyName] = _buildParentList(parentPolicyElement,
                                                                                   admxPolicyDefinitions,
                                                                                   return_full_policy_names,
                                                                                   admlPolicyResources)
    except Exception as e:
        msg = 'Unhandled exception {0} occurred while attempting to read Adm Template Policy File'.format(e)
        raise CommandExecutionError(msg)
    if _val and heirarchical_return:
        if heirarchy:
            log.debug('heirarchy == {0}'.format(heirarchy))
            for heirarchy_item in heirarchy.keys():
                if heirarchy_item in _val:
                    tdict = {}
                    first_item = True
                    for item in heirarchy[heirarchy_item]:
                        newdict = {}
                        if first_item:
                            newdict[item] = {heirarchy_item: _val.pop(heirarchy_item)}
                            first_item = False
                        else:
                            newdict[item] = tdict
                        tdict = newdict
                    if tdict:
                        _val = dictupdate.update(_val, tdict)
        _val = {_policyData.admx_registry_classes[policyClass]['lgpo_section']: {'Administrative Templates': _val}}

    return _val


def _buildParentList(policy_definition,
                     admxPolicyDefinitions,
                     return_full_policy_names,
                     admlPolicyData):
    '''
    helper functioon to build a list containing parent elements of the ADMX policy
    '''
    parent_list = []
    policy_namespace = policy_definition.nsmap.keys()[0]
    parent_category = policy_definition.xpath('{0}:parentCategory/@ref'.format(policy_namespace),
                                              namespaces=policy_definition.nsmap)
    if parent_category:
        parent_category = parent_category[0]
        this_namespace_map = _buildElementNsmap(admxPolicyDefinitions.xpath('/policyDefinitions/policyNamespaces/{0}:*'.format(policy_namespace),
                                                                            namespaces=policy_definition.nsmap))
        this_namespace_map = dictupdate.update(this_namespace_map, policy_definition.nsmap)
        parent_list = _admxPolicyParentWalk(parent_list,
                                            policy_namespace,
                                            parent_category,
                                            this_namespace_map,
                                            admxPolicyDefinitions,
                                            return_full_policy_names,
                                            admlPolicyData)
    return parent_list


def _admxPolicyParentWalk(path,
                          policy_namespace,
                          parent_category,
                          policy_nsmap,
                          admxPolicyDefinitions,
                          return_full_policy_names,
                          admlPolicyData):
    '''
    helper function to recursively walk up the ADMX namespaces and build the heirarchy for the policy
    '''
    if parent_category.find(':') >= 0:
        # the parent is in another namespace
        policy_namespace = parent_category.split(':')[0]
        parent_category = parent_category.split(':')[1]
        policy_nsmap = dictupdate.update(policy_nsmap,
                                         _buildElementNsmap(admxPolicyDefinitions.xpath('/policyDefinitions/policyNamespaces/{0}:using'.format(policy_namespace), namespaces=policy_nsmap)))
    if admxPolicyDefinitions.xpath('/policyDefinitions/categories/{0}:category[@name="{1}"]'.format(policy_namespace, parent_category), namespaces=policy_nsmap):
        this_parent_category = admxPolicyDefinitions.xpath('/policyDefinitions/categories/{0}:category[@name="{1}"]'.format(policy_namespace, parent_category), namespaces=policy_nsmap)[0]
        this_parent_name = _getFullPolicyName(this_parent_category,
                                              this_parent_category.attrib['name'],
                                              return_full_policy_names,
                                              admlPolicyData)
        path.append(this_parent_name)
        if this_parent_category.xpath('{0}:parentCategory/@ref'.format(policy_namespace), namespaces=policy_nsmap):
            # parent has a parent
            path = _admxPolicyParentWalk(path,
                                         policy_namespace,
                                         this_parent_category.xpath('{0}:parentCategory/@ref'.format(policy_namespace),
                                         namespaces=policy_nsmap)[0],
                                         policy_nsmap,
                                         admxPolicyDefinitions,
                                         return_full_policy_names,
                                         admlPolicyData)
    return path


def _getParentPolicyName(element, admlXmlData, return_full_policy_names=False):
    '''
    helper function to find the policy parent of the element
    '''
    parentPolicy = element.getparent()
    # walk up the xml until we find the parent policy
    while etree.QName(parentPolicy.tag).localname != 'policy':
        parentPolicy = parentPolicy.getparent()
    parentPolicyName = parentPolicy.attrib['name']
    if return_full_policy_names and 'displayName' in parentPolicy.attrib:
        parentPolicyName = _getAdmlDisplayName(admlXmlData, parentPolicy.attrib['displayName'])

    return (parentPolicyName, parentPolicy)


def _checkPolicyEnableDisableElement(policy_element, xpath_query, setting):
    '''
    helper function to query a policy and get the enabled/disable elements
    '''
    element = policy_element.xpath(xpath_query)
    if element and element[0].getchildren():
        log.debug('we have an element matching the xpath query, time to compare the enable/disable value to the registry setting {0}'.format(setting))
        element_type = etree.QName(element[0].getchildren()[0]).localname
#        if element_type != 'item':
#            # enabledValue/disabledValue child
        element_enableDisable_value = element[0].getchildren()[0].attrib['value']
        if element_type == 'decimal':
            log.debug('checking decimal value')
            if not setting:
                setting = chr(0)
            if ord(setting) == int(element_enableDisable_value):
                return True
            # int numeric value
        elif element_type == 'delete':
            log.debug('checking delete value')
            # deleted key/value
        elif element_type == 'longDecimal':
            log.debug('checking longDecimal value')
            # long numeric value
            if not setting:
                setting = chr(0)
            if long(ord(setting)) == long(element_enableDisable_value):
                return True
        elif element_type == 'string':
            log.debug('checking string value')
            if setting.lower() == element_enableDisable_value.lower():
                return True

    return False


def _readRegPolFile(regPolPath):
    '''
    helper function to read a reg policy file and return decoded data
    '''
    returnData = None
    if os.path.exists(regPolPath):
        with open(regPolPath, 'r') as _h:
            returnData = _h.read()
        returnData = returnData.decode('utf-16-le')
    return returnData


def _searchRegPolData(regPolData, policyToSearchFor, searchForDisabledPolicy=False):
    '''
    helper function to do a search of Policy data from a registry.pol file
    '''
    _thisSearch = u'[{1}{0};{3}{2}{0};'.format(
            chr(0),
            policyToSearchFor['AdmRegistry']['Path'],
            policyToSearchFor['AdmRegistry']['Value'],
            '**del.' if searchForDisabledPolicy else '')
    if _thisSearch in regPolData:
        _rData = regPolData[regPolData.index(_thisSearch):(regPolData.index(']', regPolData.index(_thisSearch)) + 1)]
        log.debug(_rData)
        return _rData
    return None


def _writeRegPolicyData(dataToWrite, policyFilePath):
    '''
    helper function to actually write the data to a Registry.pol file
    '''
    try:
        if dataToWrite:
            reg_pol_header = u'\u5250\u6765\x01\x00'
            with open(policyFilePath, 'w') as _h:
                if not dataToWrite.startswith(reg_pol_header):
                    _h.write(reg_pol_header.encode('utf-16-le'))
                _h.write(dataToWrite.encode('utf-16-le'))
    except Exception as e:
        msg = 'An error occurred attempting to write to {0}, the exception was {1}'.format(policyFilePath, e)
        raise CommandExecutionError(msg)


def _writeAdminTemplateRegPolFile(admTemplateData):
    u'''
    helper function to prep/write adm template data to the Registry.pol file

    admin template registry files are ascii encoded files w/utf-16-le data in them from what I can tell:/

    each file begins with REGFILE_SIGNATURE (u'\u5250\u6765') and REGISTRY_FILE_VERSION (u'\x01\00')

    https://msdn.microsoft.com/en-us/library/aa374407(VS.85).aspx
    [Registry Path<NULL>;Reg Value<NULL>;Reg Type<NULL>;SizeInBytes<NULL>;Data<NULL>]
    '''
    _existingMachineData = None
    _existingUserData = None

    registry = Registry()
    _policyData = _policy_info()

    _machinePolicyPath = os.path.join(os.getenv('WINDIR'), 'System32', 'GroupPolicy', 'Machine', 'Registry.pol')
    _userPolicyPath = os.path.join(os.getenv('WINDIR'), 'System32', 'GroupPolicy', 'User', 'Registry.pol')
    try:
        for admTemplate in admTemplateData.keys():
            thisData = None
            if _policyData.policies[admTemplate]['AdmRegistry']['Hive'] == 'HKEY_LOCAL_MACHINE':
                if not _existingMachineData:
                    _existingMachineData = _readRegPolFile(_machinePolicyPath)
                thisData = _existingMachineData
            elif _policyData.policies[admTemplate]['AdmRegistry']['Hive'] == 'HKEY_USERS':
                if not _existingUserData:
                    _existingUserData = _readRegPolFile(_userPolicyPath)
                thisData = _existingUserData
            # if admTemplate[admTemplate] == 'Not Cofigured' we need to remove it from the pol file (regardless of disabled/enabled)
            # if adminTemplate[admTemplate] == 'Disabled' we need to add it to the pol file w/the **del. prepended to the value name and a ' ' for the value
            # otherwise, set the value in the pol file to the passed value
            if str(admTemplateData[admTemplate]).upper() == 'DISABLED':
                # disable it
                # search for it and replace it w/the disabled version or add the disabled version
                _admsToDisable = {}
                if 'Children' in _policyData.policies[admTemplate]:
                    for _child in _policyData.policies[admTemplate]['Children'].keys():
                        _admsToDisable[_child] = _policyData.policies[admTemplate]['Children'][_child]
                else:
                    _admsToDisable[admTemplate] = _policyData.policies[admTemplate]
                for _admToDisable in _admsToDisable.keys():
                    _disabledString = u'[{1}{0};{2}{3}{0};{4}{0};{5}{0};{6}{0}]'.format(
                            chr(0),
                            _admsToDisable[_admToDisable]['AdmRegistry']['Path'],
                            '**del.',
                            _admsToDisable[_admToDisable]['AdmRegistry']['Value'],
                            chr(registry.vtype_reverse(_admsToDisable[admTemplate]['AdmRegistry']['Type'])),
                            chr(len(' {0}'.format(chr(0)).encode('utf-16-le'))),
                            ' ')
                    _searchResult = _searchRegPolData(thisData, _admsToDisable[_admToDisable])
                    if _searchResult:
                        thisData = thisData.replace(_searchResult, _disabledString)
                    else:
                        _searchResult = _searchRegPolData(thisData, _admsToDisable[_admToDisable], True)
                        if not _searchResult:
                            thisData = ''.join([thisData, _disabledString])
            elif str(admTemplateData[admTemplate]).upper() == 'NOT CONFIGURED':
                # search for either disabled or enabled version and remove it
                _admsToNotConfigure = {}
                if 'Children' in _policyData.policies[admTemplate]:
                    for _child in _policyData.policies[admTemplate]['Children'].keys():
                        _admsToNotConfigure[_child] = _policyData.policies[admTemplate]['Children'][_child]
                else:
                    _admsToNotConfigure[admTemplate] = _policyData.policies[admTemplate]
                for _admToNotConfigure in _admsToNotConfigure:
                    _searchResult = _searchRegPolData(thisData, _admsToNotConfigure[_admToNotConfigure])
                    if _searchResult:
                        thisData = thisData.replace(_searchResult, '')
                    else:
                        _searchResult = _searchRegPolData(thisData, _admsToNotConfigure[_admToNotConfigure], True)
                        if _searchResult:
                            thisData = thisData.replace(_searchResult, '')
            else:
                _admsToSet = {}
                _admValues = {}
                if 'Children' in _policyData.policies[admTemplate]:
                    for _child in _policyData.policies[admTemplate]['Children'].keys():
                        _admsToSet[_child] = _policyData.policies[admTemplate]['Children'][_child]
                        _admValues[_child] = admTemplateData[admTemplate][_child]
                else:
                    _admsToSet[admTemplate] = _policyData.policies[admTemplate]
                    if 'EnableValue' not in _policyData.policies[admTemplate]['AdmRegistry']:
                        _admValues[admTemplate] = admTemplateData[admTemplate]
                    else:
                        _admValues[admTemplate] = _policyData.policies[admTemplate]['AdmRegistry']['EnableValue']
                for _admToSet in _admsToSet:
                    if not isinstance(_admValues[_admToSet], string_types):
                        _admValues[_admToSet] = chr(_admValues[_admToSet])
                    log.debug('working with policy setting {0}'.format(_admToSet))
                    _thisString = u'[{1}{0};{2}{0};{3}{0};{4}{0};{5}{0}]'.format(
                            chr(0),
                            _admsToSet[_admToSet]['AdmRegistry']['Path'],
                            _admsToSet[_admToSet]['AdmRegistry']['Value'],
                            # TODO: change to this after upgrading to 2015.5.5+
                            # chr(registry.vtype_reverse(_policyData.policies[admTemplate]['AdmRegistry']['Type'])),
                            chr(registry.vtype_reverse(_policyData.policies[admTemplate]['AdmRegistry']['Type'])),
                            chr(len('{0}{1}'.format(_admValues[_admToSet], chr(0)).encode('utf-16-le'))),
                            _admValues[_admToSet])
                    _searchResult = _searchRegPolData(thisData, _admsToSet[_admToSet])
                    if _searchResult:
                        if _searchResult != _thisString:
                            log.debug('value in the reg pol file for {0} matches what we would insert'.format(_admToSet))
                            thisData = thisData.replace(_searchResult, _thisString)
                    else:
                        _searchResult = _searchRegPolData(thisData, _admsToSet[_admToSet], True)
                        if _searchResult:
                            log.debug('found the setting {0} hard disabled, we will replace that with our new data'.format(_admToSet))
                            thisData = thisData.replace(_searchResult, _thisString)
                        else:
                            log.debug('setting {0} not found in the policy file, we will append it'.format(_admToSet))
                            thisData = ''.join([thisData, _thisString])
            if _policyData.policies[admTemplate]['AdmRegistry']['Hive'] == 'HKEY_LOCAL_MACHINE':
                _existingMachineData = thisData
            elif _policyData.policies[admTemplate]['AdmRegistry']['Hive'] == 'HKEY_USERS':
                _existingUserData = thisData
        _writeRegPolicyData(_existingUserData, _userPolicyPath)
        _writeRegPolicyData(_existingMachineData, _machinePolicyPath)
    except Exception as e:
        log.error('Unhandled exception {0} occurred while attempting to write Adm Template Policy File'.format(e))
        return False
    return True


def _getScriptSettingsFromIniFile(policy_info):
    '''
    helper function to parse/read a GPO Startup/Shutdown script file
    '''
    _existingData = _readRegPolFile(policy_info['ScriptIni']['IniPath'])
    _existingData = _existingData.split('\r\n')
    script_settings = {}
    this_section = None
    for eLine in _existingData:
        if eLine.startswith('[') and eLine.endswith(']'):
            this_section = eLine.replace('[', '').replace(']', '')
            log.debug('adding section {0}'.format(this_section))
            if this_section:
                script_settings[this_section] = {}
        else:
            if '=' in eLine:
                log.debug('working with config line {0}'.format(eLine))
                eLine = eLine.split('=')
                if this_section in script_settings:
                    script_settings[this_section][eLine[0]] = eLine[1]
    if 'SettingName' in policy_info['ScriptIni']:
        log.debug('Setting Name is in policy_info')
        if policy_info['ScriptIni']['SettingName'] in script_settings[policy_info['ScriptIni']['Section']]:
            log.debug('the value is set in the file')
            return script_settings[policy_info['ScriptIni']['Section']][policy_info['ScriptIni']['SettingName']]
        else:
            return None
    elif policy_info['ScriptIni']['Section'] in script_settings:
        log.debug('no setting name')
        return script_settings[policy_info['ScriptIni']['Section']]
    else:
        log.debug('broad else')
        return None


def _writeGpoScript(psscript=False):
    '''
    helper function to write local GPO startup/shutdown script

    scripts are stored in scripts.ini and psscripts.ini files in WINDIR\\System32\\GroupPolicy\\Machine|User\\Scripts
    these files have the hidden attribute set
    files have following format:
        empty line
        [Startup]
        0CmdLine=<path to script 0>
        0Parameters=<script 0 parameters>
        [Shutdown]
        0CmdLine=<path to shutdown script 0>
        0Parameters=<shutdown script 0 parameters>
    Number is incremented for each script added
    psscript file also has the option of a [ScriptsConfig] section, which has the following two parameters:
        StartExecutePSFirst
        EndExecutePSFirst
    these can be set to true/false to denote if the powershell startup/shutdown scripts execute
    first (true) or last (false), if the value isn't set, then it is 'Not Configured' in the GUI
    '''
    _machineScriptPolicyPath = os.path.join(os.getenv('WINDIR'), 'System32', 'GroupPolicy', 'Machine', 'Scripts', 'scripts.ini')
    _machinePowershellScriptPolicyPath = os.path.join(os.getenv('WINDIR'), 'System32', 'GroupPolicy', 'Machine', 'Scripts', 'psscripts.ini')
    _userScriptPolicyPath = os.path.join(os.getenv('WINDIR'), 'System32', 'GroupPolicy', 'User', 'Scripts', 'scripts.ini')
    _userPowershellScriptPolicyPath = os.path.join(os.getenv('WINDIR'), 'System32', 'GroupPolicy', 'User', 'Scripts', 'psscripts.ini')


def get(policy_names=None, return_full_policy_names=False, heirarchical_return=False, adml_language='en-US'):
    '''
    Get a policy value

    :param list policy_names:
        A list of policy_names to display the values of.  A string of policy names will be split on commas

    :param boolean return_full_policy_names:
        True/False to return the policy name as it is seen in the gpedit.msc GUI

    :param boolean heirarchical_return:
        True/False to return the policy data in the heirarchy as seen in the gpedit.msc gui

    :param str adml_language:
        The adml language to use for processing display/descriptive names of admx template data, defaults to en-US

    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' gpedit.get return_full_policy_names=True

        salt '*' gpedit.get RestrictAnonymous,LockoutDuration
    '''

    vals = {}
    modal_returns = {}
    _policydata = _policy_info()

    if policy_names:
        if isinstance(policy_names, string_types):
            policy_names = policy_names.split(',')
    else:
        policy_names = _policydata.policies.keys()

    # handle statically configured policies
    for policy_name in policy_names:
        _pol = None
        if policy_name in _policydata.policies:
            _pol = _policydata.policies[policy_name]
        else:
            for p in _policydata.policies.keys():
                if _policydata.policies[p]['Policy'].upper() == policy_name.upper():
                    _pol = _policydata.policies[p]
                    policy_name = p
        if _pol:
            vals_key_name = policy_name
            if 'Registry' in _pol:
                # get value from registry
                vals[policy_name] = __salt__['reg.read_value'](_pol['Registry']['Hive'],
                                                               _pol['Registry']['Path'],
                                                               _pol['Registry']['Value'])['vdata']
                log.debug('Value {0} found for reg policy {1}'.format(vals[policy_name], policy_name))
            elif 'Secedit' in _pol:
                # get value from secedit
                _ret, _val = _findOptionValueInSeceditFile(_pol['Secedit']['Option'])
                if _ret:
                    vals[policy_name] = _val
                else:
                    msg = 'An error occurred attempting to get the value of policy {0} from secedit.'.format(policy_name)
                    raise CommandExecutionError(msg)
            elif 'NetUserModal' in _pol:
                # get value from UserNetMod
                if _pol['NetUserModal']['Modal'] not in modal_returns:
                    modal_returns[_pol['NetUserModal']['Modal']] = win32net.NetUserModalsGet(None,
                                                                                             _pol['NetUserModal']['Modal'])
                vals[policy_name] = vals[policy_name] = modal_returns[_pol['NetUserModal']['Modal']][_pol['NetUserModal']['Option']]
            elif 'LsaRights' in _pol:
                vals[policy_name] = _getRightsAssignments(_pol['LsaRights']['Option'])
            elif 'ScriptIni' in _pol:
                log.debug('Working with ScriptIni setting {0}'.format(policy_name))
                vals[policy_name] = _getScriptSettingsFromIniFile(_pol)
            if policy_name in vals:
                vals[policy_name] = _transformValue(vals[policy_name], _policydata.policies[policy_name], 'Get')
            if return_full_policy_names:
                vals[_pol['Policy']] = vals.pop(policy_name)
                vals_key_name = _pol['Policy']
            if heirarchical_return:
                if 'lgpo_section' in _pol:
                    firstItem = True
                    tdict = {}
                    for level in reversed(_pol['lgpo_section']):
                        newdict = {}
                        if firstItem:
                            newdict[level] = {vals_key_name: vals.pop(vals_key_name)}
                            firstItem = False
                        else:
                            newdict[level] = tdict
                        tdict = newdict
                    if tdict:
                        vals = dictupdate.update(vals, tdict)
        else:
            msg = 'The specified policy {0} is not currently available to be configured via this module'.format(policy_name)
            raise SaltInvocationError(msg)

    # read registry pol files for current settings
    for regClass in _policydata.admx_registry_classes.keys():
        ret = _getAllAdminTemplateSettingsFromRegPolFile(regClass, return_full_policy_names, heirarchical_return, adml_language)
        vals = dictupdate.update(vals, ret)

    return vals


def set(cumulative_rights_assignments=True, adml_language='en-US', **kwargs):
    '''
    Set a local server policy

    :param boolean cumulative_rights_assignments:
        If True, user right assignment specifications are simply added to the existing policy
        If False, only the users specified will get the right (any existing will have the right revoked

    :param str adml_language:
        Language to use for descriptive/long admx file processing, defaults to en-US

    :param str kwargs:
        policyname=value kwargs for all the policies you want to set
        the 'value' should be how it is displayed in the gpedit gui, i.e. if a setting can be 'Enabled'/'Disabled', then that should be passed

    :rtype: boolean

    CLI Example:

    .. code-block:: bash

        salt '*' gpedit.set LockoutDuration=2 RestrictAnonymous=Enabled AuditProcessTracking='Succes, Failure'
    '''

    if kwargs:
        _secedits = {}
        _modal_sets = {}
        _admTemplateData = {}
        _policydata = _policy_info()
        admxPolicyDefinitions, admlPolicyResources = _processPolicyDefinitions()
        log.debug('KWARGS keys = {0}'.format(kwargs.keys()))
        for policy_name in kwargs.keys():
            if not policy_name.startswith('__pub_'):
                _pol = None
                if policy_name in _policydata.policies:
                    _pol = _policydata.policies[policy_name]
                else:
                    for p in _policydata.policies.keys():
                        if _policydata.policies[p]['Policy'].upper().replace(' ', '_') == policy_name.upper():
                            _pol = _policydata.policies[p]
                            policy_name = p
                if _pol:
                    # transform and validate the setting
                    _value = _transformValue(kwargs[policy_name], _policydata.policies[policy_name], 'Put')
                    if not _validateSetting(_value, _policydata.policies[policy_name]):
                        msg = 'The specified value {0} is not an acceptable setting for policy {1}.'.format(kwargs[policy_name], policy_name)
                        raise SaltInvocationError(msg)
                    if 'Registry' in _pol:
                        # set value in registry
                        log.debug('{0} is a Registry policy'.format(policy_name))
                        _ret = __salt__['reg.set_key'](_pol['Registry']['Hive'], _pol['Registry']['Path'], _pol['Registry']['Value'], _value, _pol['Registry']['Type'])
                        if not _ret:
                            msg = 'Error while attempting to set policy {0} via the registry.  Some changes may not be applied as expected.'.format(policy_name)
                            raise CommandExecutionError(msg)
                    elif 'Secedit' in _pol:
                        # set value with secedit
                        log.debug('{0} is a Secedit policy'.format(policy_name))
                        if _pol['Secedit']['Section'] not in _secedits:
                            _secedits[_pol['Secedit']['Section']] = []
                        _secedits[_pol['Secedit']['Section']].append(' '.join([_pol['Secedit']['Option'], '=', str(_value)]))
                    elif 'NetUserModal' in _pol:
                        # set value via NetUserModal
                        log.debug('{0} is a NetUserModal policy'.format(policy_name))
                        if _pol['NetUserModal']['Modal'] not in _modal_sets:
                            _modal_sets[_pol['NetUserModal']['Modal']] = {}
                        _modal_sets[_pol['NetUserModal']['Modal']][_pol['NetUserModal']['Option']] = _value
                    elif 'LsaRights' in _pol:
                        _existingUsers = None
                        if not cumulative_rights_assignments:
                            _existingUsers = _getRightsAssignments(_pol['LsaRights']['Option'])
                        if _value:
                            for _u in _value:
                                _ret = _addAccountRights(_u, _pol['LsaRights']['Option'])
                                if not _ret:
                                    msg = 'An error occurred attempting to configure the user right {0}.'.format(policy_name)
                                    raise SaltInvocationError(msg)
                        if _existingUsers:
                            for _u in _existingUsers:
                                _ret = _delAccountRights(_u, _pol['LsaRights']['Option'])
                                if not _ret:
                                    msg = 'An error occurred attempting to remove previously configured users with right {0}.'.format(policy_name)
                                    raise SaltInvocationError(msg)
                else:
                    # look in discovered admx data for the policy name
                    admxSearchResults = admxPolicyDefinitions.xpath('//*[@*[local-name() = "id"] = "{0}" or @*[local-name() = "name"] = "{0}"]'.format(policy_name))
                    if admxSearchResults:
                        if len(admxSearchResults) == 1:
                            _admTemplateData[policy_name] = admxSearchResults[0]
                        else:
                            msg = 'Admx policy name/id "{0}" is used in multiple admx files, you should switch to using the descriptive string version from the adml file.'.format(policy_name)
                            raise SaltInvocationError(msg)
                    else:
                        msg = 'The specified policy {0} is not currently available to be configured via this module'.format(policy_name)
                        raise SaltInvocationError(msg)
        if _secedits:
            # we've got secedits to make
            log.debug(_secedits)
            _iniData = '\r\n'.join(['[Unicode]', 'Unicode=yes'])
            _seceditSections = ['System Access', 'Event Audit', 'Registry Values', 'Privilege Rights']
            for _seceditSection in _seceditSections:
                if _seceditSection in _secedits:
                    _iniData = '\r\n'.join([_iniData, ''.join(['[', _seceditSection, ']']), '\r\n'.join(_secedits[_seceditSection])])
            _iniData = '\r\n'.join([_iniData, '[Version]', 'signature="$CHICAGO$"', 'Revision=1'])
            log.debug('_iniData == {0}'.format(_iniData))
            _ret = _importSeceditConfig(_iniData)
            if not _ret:
                msg = 'Error while attempting to set policies via secedit.  Some changes may not be applied as expected.'
                raise CommandExecutionError(msg)
        if _modal_sets:
            # we've got modalsets to make
            log.debug(_modal_sets)
            for _modal_set in _modal_sets.keys():
                try:
                    _existingModalData = win32net.NetUserModalsGet(None, _modal_set)
                    _newModalSetData = dictupdate.update(_existingModalData, _modal_sets[_modal_set])
                    log.debug('NEW MODAL SET = {0}'.format(_newModalSetData))
                    _ret = win32net.NetUserModalsSet(None, _modal_set, _newModalSetData)
                except:
                    msg = 'An unhandled exception occurred while attempting to set policy via NetUserModalSet'
                    raise CommandExecutionError(msg)
        if _admTemplateData:
            _ret = _writeAdminTemplateRegPolFile(_admTemplateData)
            if not _ret:
                msg = 'Error while attempting to write Administrative Template Policy data.  Some changes may not be applied as expected.'
                raise CommandExecutionError(msg)
        return True
    else:
        msg = 'You have to specify something!'
        raise SaltInvocationError(msg)
