# -*- coding: utf-8 -*-
'''
.. versionadded:: Carbon

Manage Local Policy on Windows

This module allows configuring local group policy (i.e. gpedit.msc) on a Windows server.

Administrative Templates
========================
    Administrative template policies are dynamically read from admx/adml files on the server.


Windows Settings
================
    Policies contained in the "Windows Settings" section of the gpedit.msc gui are statically
    defined in this module.  Each policy is configured for the section (Machine/User) in the
    module's _policy_info class.  The _policy_info class contains a policies dict on how the module will
    configure the policy, where the policy resides in the gui (for display purposes), data
    validation data, data transformation data, etc.

Current known limitations
=========================
    At this time, start/shutdown scripts policies are displayed, but are not configurable.

    Not all "Security Settings" policies exist in the _policy_info class


:depends:
  - pywin32 Python module
  - lxml
  - uuid
  - codecs
  - struct
  - salt.modules.reg

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
from salt.ext.six.moves import range

log = logging.getLogger(__name__)
__virtualname__ = 'lgpo'
__func_alias__ = {'set_': 'set'}
adm_policy_name_map = {True: {}, False: {}}
HAS_WINDOWS_MODULES = False
# define some globals XPATH variables that we'll set assuming all our imports are good
TRUE_VALUE_XPATH = None
FALSE_VALUE_XPATH = None
ELEMENTS_XPATH = None
ENABLED_VALUE_XPATH = None
DISABLED_VALUE_XPATH = None
ENABLED_LIST_XPATH = None
DISABLED_LIST_XPATH = None
VALUE_XPATH = None
TRUE_LIST_XPATH = None
FALSE_LIST_XPATH = None
REGKEY_XPATH = None
POLICY_ANCESTOR_XPATH = None
ALL_CLASS_POLICY_XPATH = None
ADML_DISPLAY_NAME_XPATH = None
VALUE_LIST_XPATH = None
ENUM_ITEM_DISPLAY_NAME_XPATH = None
ADMX_SEARCH_XPATH = None
ADML_SEARCH_XPATH = None
ADMX_DISPLAYNAME_SEARCH_XPATH = None
PRESENTATION_ANCESTOR_XPATH = None
TEXT_ELEMENT_XPATH = None

try:
    import win32net
    import win32security
    import uuid
    import codecs
    import lxml
    import struct
    from lxml import etree
    from salt.modules.reg import Registry as Registry
    HAS_WINDOWS_MODULES = True
    TRUE_VALUE_XPATH = etree.XPath('.//*[local-name() = "trueValue"]')
    FALSE_VALUE_XPATH = etree.XPath('.//*[local-name() = "falseValue"]')
    ELEMENTS_XPATH = etree.XPath('.//*[local-name() = "elements"]')
    ENABLED_VALUE_XPATH = etree.XPath('.//*[local-name() = "enabledValue"]')
    DISABLED_VALUE_XPATH = etree.XPath('.//*[local-name() = "disabledValue"]')
    ENABLED_LIST_XPATH = etree.XPath('.//*[local-name() = "enabledList"]')
    DISABLED_LIST_XPATH = etree.XPath('.//*[local-name() = "disabledList"]')
    VALUE_XPATH = etree.XPath('.//*[local-name() = "value"]')
    TRUE_LIST_XPATH = etree.XPath('.//*[local-name() = "trueList"]')
    FALSE_LIST_XPATH = etree.XPath('.//*[local-name() = "falseList"]')
    REGKEY_XPATH = etree.XPath('//*[translate(@*[local-name() = "key"], "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz") = $keyvalue]')
    POLICY_ANCESTOR_XPATH = etree.XPath('ancestor::*[local-name() = "policy"]')
    ALL_CLASS_POLICY_XPATH = etree.XPath('//*[local-name() = "policy" and (@*[local-name() = "class"] = "Both" or @*[local-name() = "class"] = $registry_class)]')
    ADML_DISPLAY_NAME_XPATH = etree.XPath('//*[local-name() = $displayNameType and @*[local-name() = "id"] = $displayNameId]')
    VALUE_LIST_XPATH = etree.XPath('.//*[local-name() = "valueList"]')
    ENUM_ITEM_DISPLAY_NAME_XPATH = etree.XPath('.//*[local-name() = "item" and @*[local-name() = "displayName" = $display_name]]')
    ADMX_SEARCH_XPATH = etree.XPath('//*[local-name() = "policy" and @*[local-name() = "name"] = $policy_name and (@*[local-name() = "class"] = "Both" or @*[local-name() = "class"] = $registry_class)]')
    ADML_SEARCH_XPATH = etree.XPath('//*[text() = $policy_name and @*[local-name() = "id"]]')
    ADMX_DISPLAYNAME_SEARCH_XPATH = etree.XPath('//*[local-name() = "policy" and @*[local-name() = "displayName"] = $display_name and (@*[local-name() = "class"] = "Both" or @*[local-name() = "class"] = $registry_class) ]')
    PRESENTATION_ANCESTOR_XPATH = etree.XPath('ancestor::*[local-name() = "presentation"]')
    TEXT_ELEMENT_XPATH = etree.XPath('.//*[local-name() = "text"]')
except ImportError:
    HAS_WINDOWS_MODULES = False


class _policy_info(object):
    '''
    policy helper stuff

    The format of the policy dict is as follows:
        The top most two key/value pairs in the dict divide the policies object into the two sections
        of local group policy, using the keys "Machine" and "User".  The value make-up of these dicts
        are described below in "Policy Section Definition"

        Policy Section Definition
        -------------------------
        A policy section dict has two required key/value pairs:
            key name: lgpo_section
            value: string matching how the policy section is displayed in the mmc snap-in
                ("Computer Configuration" for "Machine" and "User Configuration" for "User")

            key name: policies
            value: a dict containing the non-Administrative template policy definitions, the key for
                each item is a short/unique identifier for the policy, the value is described below in
                "Policies Definition"

        Policies Definition
        -------------------
        A policies definition item describes the particular policy.
        There are three child key/value pairs shared with all policy types:
            key name: lgpo_section
            value: a list containing the hierarchical path to the policy in the gpedit mmc snap-in.

            key name: Policy
            value: a string containing the name of the policy in the gpedit mmc snap-in

            key name: Settings
            value: An object which describes valid settings for the policy.  This can be None for no validation,
            a list of possible settings, or a dict with the following key/value pairs:
                key name: Function
                value: the class function to use to validate the setting

                key name: Args
                value: a dict of kwargs to pass to the class function

        Additionally, each policies definition will contain a key/value pair that defines the mechanism that
        will be used to configure the policy.  The available mechanisms are:  NetUserModal, Registry, Secedit,
        and LsaRights

        Registry mechanism
        ------------------
        Some policies set simply values in the windows registry, the value of this key is a dict with the
        following make-up:
            key name: Hive
            value: a string containing the Registry hive, such as HKEY_LOCAL_MACHINE

            key name: Path
            value: a string containing the registry key path, such as SYSTEM\\CurrentControlSet\\Control\\Lsa

            key name: Value
            value: a string containing the name of the registry value, such as restrictanonymous

            key name: Type
            value: a string contianing the registry type of the value, such as REG_DWORD

        Secedit mechanism
        -----------------
        Some policies are configurable via the "secedit.exe" executable, the value of this key is a dict with the
        following make-up:
            key name: Option
            value: a string containing the name of the policy as it appears in an export from secedit, such as
                PasswordComplexity

            key name: Section
            value: a string containing the name of the section that the "Option" value appears in in an export
                from secedit, such as "System Access"

        LsaRights mechanism
        -------------------
        LSA Rights policiesare configured via the LsaRights mechansim, the value of this key is a dict with the
        following make-up:
            key name: Option
            value: a string containing the programmatic name of the Lsa Right, such as SeNetworkLogonRight

        NetUserModal mechanism
        ----------------------
        Some policies are configurable by the NetUserModalGet and NetUserModalSet function from pywin32.  The value
        of this key is a dict with the following make-up:
            key name: Modal
            value: The modal "level" that the particular option is specified in (0-3), see
                https://msdn.microsoft.com/en-us/library/windows/desktop/aa370656(v=vs.85).aspx

            key name: Option
            value: The name of the structure member which contains the data for the policy, for example max_passwd_age

        Optionally, each policy definition can contain a 'Transform' key.  The Transform key is used to handle data that is stored
        and viewed differently.  This key's value is a dict with the following key/value pairs:
            key name: Get
            value: the name of the class function to use to transform the data from the stored value to how the value
            is displayed in the GUI

            key name: Put
            value: the name of the class function to use to transfor the data supplied by the user to the correct value
            that the policy is stored in
        For example, "Minimum password age" is stored in seconds, but is displayed in days.  Thus the "Get" and "Put" functions
        for this policy do these conversions so the user is able to set and view the policy using the same data that is shown
        in the GUI
    '''
    def __init__(self):
        self.policies = {
            'Machine': {
                'lgpo_section': 'Computer Configuration',
                'policies': {
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
                        },
                    },
                    'DoNotDisplayLastUserName': {
                        'Policy': 'Interactive logon: Do not display last user name',
                        'Settings': [0, 1],
                        'lgpo_section': ['Computer Configuration',
                                         'Windows Settings',
                                         'Security Settings',
                                         'Local Policies',
                                         'Security Options'],
                        'Registry': {
                            'Hive': 'HKEY_LOCAL_MACHINE',
                            'Path': 'Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System',
                            'Value': 'DontDisplayLastUserName',
                            'Type': 'REG_DWORD',
                        },
                        'Transform': {
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_binary_enable_zero_disable_one_conversion',
                            'Put': '_binary_enable_zero_disable_one_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
                            'Get': '_enable_one_disable_zero_conversion',
                            'Put': '_enable_one_disable_zero_reverse_conversion',
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
            },
            'User': {
                'lgpo_section': 'User Configuration',
                'policies': {}
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

    @classmethod
    def _notEmpty(cls, val, **kwargs):
        '''
        ensures a value is not empty
        '''
        if val:
            return True
        else:
            return False

    @classmethod
    def _enable_one_disable_zero_conversion(cls, val, **kwargs):
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

    @classmethod
    def _enable_one_disable_zero_reverse_conversion(cls, val, **kwargs):
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

    @classmethod
    def _event_audit_conversion(cls, val, **kwargs):
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

    @classmethod
    def _event_audit_reverse_conversion(cls, val, **kwargs):
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

    @classmethod
    def _seconds_to_days(cls, val, **kwargs):
        '''
        converts a number of seconds to days
        '''
        if val is not None:
            return val / 86400
        else:
            return 'Not Defined'

    @classmethod
    def _days_to_seconds(cls, val, **kwargs):
        '''
        converts a number of days to seconds
        '''
        if val is not None:
            return val * 86400
        else:
            return 'Not Defined'

    @classmethod
    def _seconds_to_minutes(cls, val, **kwargs):
        '''
        converts a number of seconds to minutes
        '''
        if val is not None:
            return val / 60
        else:
            return 'Not Defined'

    @classmethod
    def _minutes_to_seconds(cls, val, **kwargs):
        '''
        converts number of minutes to seconds
        '''
        if val is not None:
            return val * 60
        else:
            return 'Not Defined'

    @classmethod
    def _strip_quotes(cls, val, **kwargs):
        '''
        strips quotes from a string
        '''
        return val.replace('"', '')

    @classmethod
    def _add_quotes(cls, val, **kwargs):
        '''
        add quotes around the string
        '''
        return '"{0}"'.format(val)

    @classmethod
    def _binary_enable_zero_disable_one_conversion(cls, val, **kwargs):
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

    @classmethod
    def _binary_enable_zero_disable_one_reverse_conversion(cls, val, **kwargs):
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

    @classmethod
    def _dasd_conversion(cls, val, **kwargs):
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

    @classmethod
    def _dasd_reverse_conversion(cls, val, **kwargs):
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

    @classmethod
    def _in_range_inclusive(cls, val, **kwargs):
        '''
        checks that a value is in an inclusive range
        '''
        minimum = 0
        maximum = 1
        if 'min' in kwargs:
            minimum = kwargs['min']
        if 'max' in kwargs:
            maximum = kwargs['max']
        if val is not None:
            if val >= minimum and val <= maximum:
                return True
            else:
                return False
        else:
            return False

    @classmethod
    def _driver_signing_reg_conversion(cls, val, **kwargs):
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

    @classmethod
    def _driver_signing_reg_reverse_conversion(cls, val, **kwargs):
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

    @classmethod
    def _sidConversion(cls, val, **kwargs):
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

    @classmethod
    def _usernamesToSidObjects(cls, val, **kwargs):
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

    @classmethod
    def _powershell_script_order_conversion(cls, val, **kwargs):
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

    @classmethod
    def _powershell_script_order_reverse_conversion(cls, val, **kwargs):
        '''
        converts powershell script GUI strings representations to True/False/None
        '''
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


def _updateNamespace(item, new_namespace):
    '''
    helper function to recursively update the namespaces of an item
    '''
    temp_item = ''
    i = item.tag.find('}')
    if i >= 0:
        temp_item = item.tag[i+1:]
    else:
        temp_item = item.tag
    item.tag = '{{{0}}}{1}'.format(new_namespace, temp_item)
    for child in item.getiterator():
        if isinstance(child.tag, string_types):
            temp_item = ''
            i = child.tag.find('}')
            if i >= 0:
                temp_item = child.tag[i+1:]
            else:
                temp_item = child.tag
            child.tag = '{{{0}}}{1}'.format(new_namespace, temp_item)
    return item


def _updatePolicyElements(policy_item, regkey):
    '''
    helper function to add the reg key to each policies element definitions if the key
    attribute is not defined to make xpath searching easier
    for each child in the policy <elements> item
    '''
    for child in policy_item.getiterator():
        if 'valueName' in child.attrib:
            if 'key' not in child.attrib:
                child.attrib['key'] = regkey
    return policy_item


def _processPolicyDefinitions(policy_def_path='c:\\Windows\\PolicyDefinitions', display_language='en-US'):
    '''
    helper function to process all ADMX files in the specified policy_def_path
    and build a single XML doc that we can search/use for admx polic processing
    '''
    display_language_fallback = 'en-US'
    t_policy_definitions = lxml.etree.Element('policyDefinitions')
    t_policy_definitions.append(lxml.etree.Element('categories'))
    t_policy_definitions.append(lxml.etree.Element('policies'))
    t_policy_definitions.append(lxml.etree.Element('policyNamespaces'))
    t_policy_definition_resources = lxml.etree.Element('policyDefinitionResources')
    policydefs_policies_xpath = etree.XPath('/policyDefinitions/policies')
    policydefs_categories_xpath = etree.XPath('/policyDefinitions/categories')
    policydefs_policyns_xpath = etree.XPath('/policyDefinitions/policyNamespaces')
    policydefs_resources_localname_xpath = etree.XPath('//*[local-name() = "policyDefinitionResources"]/*')
    policydef_resources_xpath = etree.XPath('/policyDefinitionResources')
    for root, dirs, files in os.walk(policy_def_path):
        if root == policy_def_path:
            for t_admfile in files:
                admfile = os.path.join(root, t_admfile)
                parser = lxml.etree.XMLParser(remove_comments=True)
                xmltree = lxml.etree.parse(admfile, parser=parser)
                namespaces = xmltree.getroot().nsmap
                namespace_string = ''
                if None in namespaces:
                    namespaces['None'] = namespaces[None]
                    namespaces.pop(None)
                    namespace_string = 'None:'
                this_prefix = xmltree.xpath(
                        '/{0}policyDefinitions/{0}policyNamespaces/{0}target/@prefix'.format(namespace_string),
                        namespaces=namespaces)[0]
                this_namespace = xmltree.xpath(
                        '/{0}policyDefinitions/{0}policyNamespaces/{0}target/@namespace'.format(namespace_string),
                        namespaces=namespaces)[0]
                categories = xmltree.xpath(
                        '/{0}policyDefinitions/{0}categories/{0}category'.format(namespace_string),
                        namespaces=namespaces)
                for category in categories:
                    temp_cat = category
                    temp_cat = _updateNamespace(temp_cat, this_namespace)
                    policydefs_categories_xpath(t_policy_definitions)[0].append(temp_cat)
                policies = xmltree.xpath('/{0}policyDefinitions/{0}policies/{0}policy'.format(namespace_string),
                                         namespaces=namespaces)
                for policy in policies:
                    temp_pol = policy
                    temp_pol = _updateNamespace(temp_pol, this_namespace)
                    if 'key' in temp_pol.attrib:
                        temp_pol = _updatePolicyElements(temp_pol, temp_pol.attrib['key'])
                    policydefs_policies_xpath(t_policy_definitions)[0].append(temp_pol)
                policy_namespaces = xmltree.xpath(
                        '/{0}policyDefinitions/{0}policyNamespaces/{0}*'.format(namespace_string),
                        namespaces=namespaces)
                for policy_ns in policy_namespaces:
                    temp_ns = policy_ns
                    temp_ns = _updateNamespace(temp_ns, this_namespace)
                    policydefs_policyns_xpath(t_policy_definitions)[0].append(temp_ns)
                adml_file = os.path.join(root, display_language, os.path.splitext(t_admfile)[0] + '.adml')
                if not __salt__['file.file_exists'](adml_file):
                    msg = ('An adml file in the specified adml language "{0}" does not '
                           'exist for the admx "{1}", the fallback languange will be tried.')
                    log.info(msg.format(display_language, t_admfile))
                    adml_file = os.path.join(root,
                                             display_language_fallback,
                                             os.path.splitext(t_admfile)[0] + '.adml')
                    if not __salt__['file.file_exists'](adml_file):
                        msg = ('An adml file in the specified adml language "{0}" and the fallback '
                               'language "{1}" do not exist for the admx "{2}".')
                        raise SaltInvocationError(msg.format(display_language,
                                                             display_language_fallback,
                                                             t_admfile))
                xmltree = lxml.etree.parse(adml_file)
                if None in namespaces:
                    namespaces['None'] = namespaces[None]
                    namespaces.pop(None)
                    namespace_string = 'None:'
                policydefs_resources = policydefs_resources_localname_xpath(xmltree)
                for policydefs_resource in policydefs_resources:
                    t_poldef = policydefs_resource
                    t_poldef = _updateNamespace(t_poldef, this_namespace)
                    policydef_resources_xpath(t_policy_definition_resources)[0].append(t_poldef)
    return (t_policy_definitions, t_policy_definition_resources)


def _buildElementNsmap(using_elements):
    '''
    build a namespace map for an ADMX element
    '''
    thisMap = {}
    for e in using_elements:
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
    except Exception as e:
        log.debug('error occurred while trying to get secedit data')
        return False, None


def _importSeceditConfig(infdata):
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
        _ret = __salt__['file.append'](_tInfFile, infdata)
        # run secedit to make the change
        _ret = __salt__['cmd.run']('secedit /configure /db {0} /cfg {1}'.format(_tSdbfile, _tInfFile))
        # cleanup our temp files
        _ret = __salt__['file.remove'](_tSdbfile)
        _ret = __salt__['file.remove'](_tInfFile)
        return True
    except Exception as e:
        log.debug('error occurred while trying to import secedit data')
        return False


def _transformValue(value, policy, transform_type):
    '''
    helper function to transform the policy value into something that more closely matches
    how the policy is displayed in the gpedit gui
    '''
    t_kwargs = {}
    if 'Transform' in policy:
        if transform_type in policy['Transform']:
            _policydata = _policy_info()
            if transform_type + 'Args' in policy['Transform']:
                t_kwargs = policy['Transform'][transform_type + 'Args']
            return getattr(_policydata, policy['Transform'][transform_type])(value, **t_kwargs)
        else:
            return value
    else:
        return value


def _validateSetting(value, policy):
    '''
    helper function to validate specified value is appropriate for the policy
    if the 'Settings' key is a list, the value will checked that it is in the list
    if the 'Settings' key is a dict
        we will try to execute the function name from the 'Function' key, passing the value
        and additional arguments from the 'Args' dict
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


def _addAccountRights(sidObject, user_right):
    '''
    helper function to add an account right to a user
    '''
    try:
        if sidObject:
            _polHandle = win32security.LsaOpenPolicy(None, win32security.POLICY_ALL_ACCESS)
            user_rights_list = [user_right]
            _ret = win32security.LsaAddAccountRights(_polHandle, sidObject, user_rights_list)
        return True
    except Exception as e:
        log.error('Error attempting to add account right, exception was {0}'.format(e))
        return False


def _delAccountRights(sidObject, user_right):
    '''
    helper function to remove an account right from a user
    '''
    try:
        _polHandle = win32security.LsaOpenPolicy(None, win32security.POLICY_ALL_ACCESS)
        user_rights_list = [user_right]
        _ret = win32security.LsaRemoveAccountRights(_polHandle, sidObject, False, user_rights_list)
        return True
    except Exception as e:
        log.error('Error attempting to delete account right, exception was {0}'.format(e))
        return False


def _getRightsAssignments(user_right):
    '''
    helper function to return all the user rights assignments/users
    '''
    sids = []
    polHandle = win32security.LsaOpenPolicy(None, win32security.POLICY_ALL_ACCESS)
    sids = win32security.LsaEnumerateAccountsWithUserRight(polHandle, user_right)
    return sids


def _getAdmlDisplayName(adml_xml_data, display_name):
    '''
    helper function to take the 'displayName' attribute of an element and find the value from the ADML data

    adml_xml_data :: XML data of all adml files to search
    display_name :: the value of the displayName attribute from the admx entry to search the adml data for
    '''
    if display_name.startswith('$(') and display_name.endswith(')'):
        display_name = re.sub(r'(^\$\(|\)$)', '', display_name)
        display_name = display_name.split('.')
        displayname_type = display_name[0]
        displayname_id = display_name[1]
        search_results = ADML_DISPLAY_NAME_XPATH(adml_xml_data,
                                                 displayNameType=displayname_type,
                                                 displayNameId=displayname_id)
        if search_results:
            for result in search_results:
                return result.text

    return None


def _getAdmlPresentationRefId(adml_data, ref_id):
    '''
    helper function to check for a presentation label for a policy element
    '''
    search_results = adml_data.xpath('//*[@*[local-name() = "refId"] = "{0}"]'.format(ref_id))
    prepended_text = ''
    if search_results:
        for result in search_results:
            the_localname = etree.QName(result.tag).localname
            presentation_element = PRESENTATION_ANCESTOR_XPATH(result)
            if presentation_element:
                presentation_element = presentation_element[0]
                if TEXT_ELEMENT_XPATH(presentation_element):
                    for p_item in presentation_element.getchildren():
                        if p_item == result:
                            break
                        else:
                            if etree.QName(p_item.tag).localname == 'text':
                                if prepended_text:
                                    prepended_text = ' '.join([prepended_text, p_item.text.rstrip()])
                                else:
                                    prepended_text = p_item.text.rstrip()
                            else:
                                prepended_text = ''
                    if prepended_text.endswith('.'):
                        prepended_text = ''
            if the_localname == 'textBox' \
                    or the_localname == 'comboBox':
                label_items = result.xpath('.//*[local-name() = "label"]')
                for label_item in label_items:
                    if label_item.text:
                        return (prepended_text + ' ' + label_item.text.rstrip().rstrip(':')).lstrip()
            elif the_localname == 'decimalTextBox' \
                    or the_localname == 'longDecimalTextBox' \
                    or the_localname == 'dropdownList' \
                    or the_localname == 'listBox' \
                    or the_localname == 'checkBox' \
                    or the_localname == 'text' \
                    or the_localname == 'multiTextBox':
                if result.text:
                    return (prepended_text + ' ' + result.text.rstrip().rstrip(':')).lstrip()
    return None


def _getFullPolicyName(policy_item, policy_name, return_full_policy_names, adml_data):
    '''
    helper function to retrieve the full policy name if needed
    '''
    if policy_name in adm_policy_name_map[return_full_policy_names]:
        return adm_policy_name_map[return_full_policy_names][policy_name]
    if return_full_policy_names and 'displayName' in policy_item.attrib:
        fullPolicyName = _getAdmlDisplayName(adml_data, policy_item.attrib['displayName'])
        if fullPolicyName:
            adm_policy_name_map[return_full_policy_names][policy_name] = fullPolicyName
            policy_name = fullPolicyName
    elif return_full_policy_names and 'id' in policy_item.attrib:
        fullPolicyName = _getAdmlPresentationRefId(adml_data, policy_item.attrib['id'])
        if fullPolicyName:
            adm_policy_name_map[return_full_policy_names][policy_name] = fullPolicyName
            policy_name = fullPolicyName
    policy_name = policy_name.rstrip(':').rstrip()
    return policy_name


def _regexSearchRegPolData(search_string, policy_data):
    '''
    helper function to do a search of Policy data from a registry.pol file
    returns True if the regex search_string is found, otherwise False
    '''
    if policy_data:
        if search_string:
            match = re.search(search_string, policy_data, re.IGNORECASE)
            if match:
                return True
    return False


def _getDataFromRegPolData(search_string, policy_data, return_value_name=False):
    '''
    helper function to do a search of Policy data from a registry.pol file
    returns the "data" field
    https://msdn.microsoft.com/en-us/library/aa374407(VS.85).aspx
    [key;value;type;size;data]
    '''
    value = None
    values = []
    if return_value_name:
        values = {}
    if search_string:
        registry = Registry()
        if len(search_string.split('{0};'.format(chr(0)))) >= 3:
            vtype = registry.vtype_reverse[ord(search_string.split('{0};'.format(chr(0)))[2])]
        else:
            vtype = None
        search_string = re.escape(search_string)
        matches = re.finditer(search_string, policy_data, re.IGNORECASE)
        matches = [m for m in matches]
        if matches:
            for match in matches:
                pol_entry = policy_data[match.start():(policy_data.index(']',
                                                                         match.end())
                                                       )
                                        ].split('{0};'.format(chr(0)))
                if len(pol_entry) >= 2:
                    valueName = pol_entry[1]
                if len(pol_entry) >= 5:
                    value = pol_entry[4]
                    if vtype == 'REG_DWORD' or vtype == 'REG_QWORD':
                        value = value.replace(chr(0), '')
                        if value:
                            value = ord(value)
                        else:
                            value = 0
                    elif vtype == 'REG_MULTI_SZ':
                        value = value.rstrip(chr(0)).split(chr(0))
                    else:
                        value = value.rstrip(chr(0))
                if return_value_name:
                    log.debug('we want value names and the value')
                    values[valueName] = value
                elif len(matches) > 1:
                    log.debug('we have multiple matches, we will return a list')
                    values.append(value)
    if values:
        value = values

    return value


def _checkListItem(policy_element, policy_name, policy_key, xpath_object, policy_file_data, test_items=True):
    '''
    helper function to process an enabled/Disabled/true/falseList set
    if test_items is True, it will determine if the policy is enabled or disabled
    returning True if all items are configured in the registry.pol file and false if they are not

    if test_items is False, the expected strings for the items will be returned as a list

    returns True if the enabled/disabledList is 100% configured in the registry.pol file, otherwise returns False
    '''
    xpath_string = ('.//*[local-name() = "decimal" or local-name() = "delete"'
                    ' or local-name() = "longDecimal" or local-name() = "string"]')
    value_item_child_xpath = etree.XPath(xpath_string)
    expected_strings = []
    for list_element in xpath_object(policy_element):
        configured_items = 0
        required_items = 0
        for item in list_element.getchildren():
            required_items = required_items + 1
            if 'key' in item.attrib:
                item_key = item.attrib['key']
            else:
                item_key = policy_key
            if 'valueName' in item.attrib:
                item_valuename = item.attrib['valueName']
            else:
                msg = '{2} item with attributes {0} in policy {1} does not have the required "valueName" attribute'
                log.error(msg.format(item.attrib, policy_element.attrib, etree.QName(list_element).localname))
                break
            for value_item in value_item_child_xpath(item):
                search_string = _processValueItem(value_item,
                                                  item_key,
                                                  item_valuename,
                                                  policy_element,
                                                  item)
                if test_items:
                    if _regexSearchRegPolData(re.escape(search_string), policy_file_data):
                        configured_items = configured_items + 1
                        msg = ('found the search string in the pol file, {0} of {1} '
                               'items for policy {2} are configured in registry.pol')
                        log.debug(msg.format(configured_items, required_items, policy_name))
                else:
                    expected_strings.append(search_string)
        if test_items:
            if required_items > 0 and required_items == configured_items:
                log.debug('{0} all items are set'.format(policy_name))
                return True
    if test_items:
        return False
    else:
        return expected_strings


def _checkValueItemParent(policy_element, policy_name, policy_key,
                          policy_valueName, xpath_object, policy_file_data,
                          check_deleted=False, test_item=True):
    '''
    helper function to process the parent of a value item object
    if test_item is True, it will determine if the policy is enabled/disabled
    returns True if the value is configured in the registry.pol file, otherwise returns False

    if test_item is False, the expected search string will be returned

    value type parents:
        boolean: https://msdn.microsoft.com/en-us/library/dn606009(v=vs.85).aspx
        enabledValue: https://msdn.microsoft.com/en-us/library/dn606006(v=vs.85).aspx
        disabledValue: https://msdn.microsoft.com/en-us/library/dn606001(v=vs.85).aspx

    '''
    for element in xpath_object(policy_element):
        for value_item in element.getchildren():
            search_string = _processValueItem(value_item,
                                              policy_key,
                                              policy_valueName,
                                              policy_element,
                                              element,
                                              check_deleted=check_deleted)
            if not test_item:
                return search_string
            if _regexSearchRegPolData(re.escape(search_string), policy_file_data):
                log.debug('found the search string in the pol file, {0} is configured'.format(policy_name))
                return True
    return False


def _buildKnownDataSearchString(reg_key, reg_valueName, reg_vtype, reg_data, check_deleted=False):
    '''
    helper function similar to _processValueItem to build a search string for a known key/value/type/data
    '''
    registry = Registry()
    this_element_value = None
    expected_string = ''
    if reg_data and not check_deleted:
        if reg_vtype == 'REG_DWORD':
            this_element_value = ''
            for v in struct.unpack('2H', struct.pack('I', int(reg_data))):
                this_element_value = this_element_value + unichr(v)
        elif reg_vtype == 'REG_QWORD':
            this_element_value = ''
            for v in struct.unpack('4H', struct.pack('I', int(reg_data))):
                this_element_value = this_element_value + unichr(v)
        elif reg_vtype == 'REG_SZ':
            this_element_value = '{0}{1}'.format(reg_data, chr(0))
    if check_deleted:
        reg_vtype = 'REG_SZ'
        expected_string = u'[{1}{0};**del.{2}{0};{3}{0};{4}{0};{5}{0}]'.format(
                                chr(0),
                                reg_key,
                                reg_valueName,
                                chr(registry.vtype[reg_vtype]),
                                unichr(len(' {0}'.format(chr(0)).encode('utf-16-le'))),
                                ' ')
    else:
        expected_string = u'[{1}{0};{2}{0};{3}{0};{4}{0};{5}]'.format(
                                chr(0),
                                reg_key,
                                reg_valueName,
                                chr(registry.vtype[reg_vtype]),
                                unichr(len(this_element_value.encode('utf-16-le'))),
                                this_element_value)
    return expected_string


def _processValueItem(element, reg_key, reg_valuename, policy, parent_element,
                      check_deleted=False, this_element_value=None):
    '''
    helper function to process an value type item and generate the expected string in the Registry.pol file

    element - the element to process
    reg_key - the registry key associated with the element (some inherit from their parent policy)
    reg_valuename - the registry valueName associated with the element (some inherit from their parent policy)
    policy - the parent policy element
    parent_element - the parent element (primarily passed in to differentiate children of "elements" objects
    check_deleted - if the returned expected string should be for a deleted value
    this_element_value - a specific value to place into the expected string returned
        for "elements" children whose values are specified by the user
    '''
    registry = Registry()
    expected_string = None
    # https://msdn.microsoft.com/en-us/library/dn606006(v=vs.85).aspx
    this_vtype = 'REG_SZ'
    standard_layout = u'[{1}{0};{2}{0};{3}{0};{4}{0};{5}]'
    if etree.QName(element).localname == 'decimal' and etree.QName(parent_element).localname != 'elements':
        this_vtype = 'REG_DWORD'
        if 'value' in element.attrib:
            this_element_value = ''
            for val in struct.unpack('2H', struct.pack('I', int(element.attrib['value']))):
                this_element_value = this_element_value + unichr(val)
        else:
            msg = 'The {2} child {1} element for the policy with attributes: {0} does not have the required'
            msg = ' "value" attribute.  The elment attributes are: {3}'
            log.error(msg.format(policy.attrib,
                                 etree.QName(element).localname,
                                 etree.QName(parent_element).localname,
                                 element.attrib))
            return None
    elif etree.QName(element).localname == 'longDecimal' and etree.QName(parent_element).localname != 'elements':
        # WARNING: no longDecimals in current ADMX files included with 2012 server, so untested/assumed
        this_vtype = 'REG_QWORD'
        if 'value' in element.attrib:
            this_element_value = ''
            for val in struct.unpack('4H', struct.pack('I', int(element.attrib['value']))):
                this_element_value = this_element_value + unichr(val)
        else:
            msg = ('The {2} child {1} element for the policy with attributes: {0} does not have the required'
                   ' "value" attribute.  The elment attributes are: {3}')
            log.error(msg.format(policy.attrib,
                                 etree.QName(element).localname,
                                 etree.QName(parent_element).localname,
                                 element.attrib))
            return None
    elif etree.QName(element).localname == 'string':
        this_vtype = 'REG_SZ'
        this_element_value = '{0}{1}'.format(element.text, chr(0))
    elif etree.QName(parent_element).localname == 'elements':
        standard_element_expected_string = True
        if etree.QName(element).localname == 'boolean':
            # a boolean element that has no children will add a REG_DWORD == 1 on true
            # or delete the value on false
            # https://msdn.microsoft.com/en-us/library/dn605978(v=vs.85).aspx
            if this_element_value is False:
                check_deleted = True
            if not check_deleted:
                this_vtype = 'REG_DWORD'
            this_element_value = chr(1)
            standard_element_expected_string = False
        elif etree.QName(element).localname == 'decimal':
            # https://msdn.microsoft.com/en-us/library/dn605987(v=vs.85).aspx
            this_vtype = 'REG_DWORD'
            if this_element_value is not None:
                temp_val = ''
                for v in struct.unpack('2H', struct.pack('I', int(this_element_value))):
                    temp_val = temp_val + unichr(v)
                this_element_value = temp_val
            if 'storeAsText' in element.attrib:
                if element.attrib['storeAsText'].lower() == 'true':
                    this_vtype = 'REG_SZ'
                    if this_element_value is not None:
                        this_element_value = str(this_element_value)
            if check_deleted:
                this_vtype = 'REG_SZ'
        elif etree.QName(element).localname == 'longDecimal':
            # https://msdn.microsoft.com/en-us/library/dn606015(v=vs.85).aspx
            this_vtype = 'REG_QWORD'
            if this_element_value is not None:
                temp_val = ''
                for v in struct.unpack('4H', struct.pack('I', int(this_element_value))):
                    temp_val = temp_val + unichr(v)
                this_element_value = temp_val
            if 'storeAsText' in element.attrib:
                if element.attrib['storeAsText'].lower() == 'true':
                    this_vtype = 'REG_SZ'
                    if this_element_value is not None:
                        this_element_value = str(this_element_value)
        elif etree.QName(element).localname == 'text':
            # https://msdn.microsoft.com/en-us/library/dn605969(v=vs.85).aspx
            this_vtype = 'REG_SZ'
            if 'expandable' in element.attrib:
                if element.attrib['expandable'].lower() == 'true':
                    this_vtype = 'REG_EXPAND_SZ'
            if this_element_value is not None:
                this_element_value = '{0}{1}'.format(this_element_value, chr(0))
        elif etree.QName(element).localname == 'multiText':
            this_vtype = 'REG_MULTI_SZ'
            if this_element_value is not None:
                this_element_value = '{0}{1}{1}'.format(chr(0).join(this_element_value), chr(0))
        elif etree.QName(element).localname == 'list':
            standard_element_expected_string = False
            del_keys = ''
            element_valuenames = []
            element_values = this_element_value
            if this_element_value is not None:
                element_valuenames = list(range(1, len(this_element_value) + 1))
            if 'additive' in element.attrib:
                if element.attrib['additive'].lower() == 'false':
                    # a delete values will be added before all the other
                    # value = data pairs
                    del_keys = u'[{1}{0};**delvals.{0};{2}{0};{3}{0};{4}{0}]'.format(
                                    chr(0),
                                    reg_key,
                                    chr(registry.vtype[this_vtype]),
                                    chr(len(' {0}'.format(chr(0)).encode('utf-16-le'))),
                                    ' ')
            if 'expandable' in element.attrib:
                this_vtype = 'REG_EXPAND_SZ'
            if 'explicitValue' in element.attrib and element.attrib['explicitValue'].lower() == 'true':
                if this_element_value is not None:
                    element_valuenames = this_element_value.keys()
                    element_values = this_element_value.values()

            if 'valuePrefix' in element.attrib and element.attrib['valuePrefix'] != '':
                if this_element_value is not None:
                    element_valuenames = ['{0}{1}'.format(element.attrib['valuePrefix'],
                                                          k) for k in element_valuenames]
            if not check_deleted:
                if this_element_value is not None:
                    log.debug('_processValueItem has an explicit element_value of {0}'.format(this_element_value))
                    expected_string = del_keys
                    log.debug('element_valuenames == {0} and element_values == {1}'.format(element_valuenames,
                                                                                           element_values))
                    for i, item in enumerate(element_valuenames):
                        expected_string = expected_string + standard_layout.format(
                                                chr(0),
                                                reg_key,
                                                element_valuenames[i],
                                                chr(registry.vtype[this_vtype]),
                                                unichr(len('{0}{1}'.format(element_values[i],
                                                                           chr(0)).encode('utf-16-le'))),
                                                '{0}{1}'.format(element_values[i], chr(0)))
                else:
                    expected_string = del_keys + r'[{1}{0};'.format(chr(0),
                                                                    reg_key)
            else:
                expected_string = u'[{1}{0};**delvals.{0};{2}{0};{3}{0};{4}{0}]'.format(
                                        chr(0),
                                        reg_key,
                                        chr(registry.vtype[this_vtype]),
                                        chr(len(' {0}'.format(chr(0)).encode('utf-16-le'))),
                                        ' ')
        elif etree.QName(element).localname == 'enum':
            if this_element_value is not None:
                pass

        if standard_element_expected_string and not check_deleted:
            if this_element_value is not None:
                expected_string = standard_layout.format(
                                        chr(0),
                                        reg_key,
                                        reg_valuename,
                                        chr(registry.vtype[this_vtype]),
                                        unichr(len(this_element_value.encode('utf-16-le'))),
                                        this_element_value)
            else:
                expected_string = u'[{1}{0};{2}{0};{3}{0};'.format(chr(0),
                                                                   reg_key,
                                                                   reg_valuename,
                                                                   chr(registry.vtype[this_vtype]))

    if not expected_string:
        if etree.QName(element).localname == "delete" or check_deleted:
            # delete value
            expected_string = u'[{1}{0};**del.{2}{0};{3}{0};{4}{0};{5}{0}]'.format(
                                    chr(0),
                                    reg_key,
                                    reg_valuename,
                                    chr(registry.vtype[this_vtype]),
                                    unichr(len(' {0}'.format(chr(0)).encode('utf-16-le'))),
                                    ' ')
        else:
            expected_string = standard_layout.format(
                                    chr(0),
                                    reg_key,
                                    reg_valuename,
                                    chr(registry.vtype[this_vtype]),
                                    unichr(len(this_element_value.encode('utf-16-le'))),
                                    this_element_value)
    return expected_string


def _checkAllAdmxPolicies(policy_class,
                          admx_policy_definitions,
                          adml_policy_resources,
                          return_full_policy_names=False,
                          hierarchical_return=False,
                          return_not_configured=False):
    '''
    rewrite of _getAllAdminTemplateSettingsFromRegPolFile where instead of looking only
    at the contents of the file, we're going to loop through every policy and look
    in the registry.pol file to determine if it is enabled/disabled/not configured
    '''
    log.debug('POLICY CLASS == {0}'.format(policy_class))
    module_policy_data = _policy_info()
    policy_filedata = _read_regpol_file(module_policy_data.admx_registry_classes[policy_class]['policy_path'])
    admx_policies = []
    policy_vals = {}
    hierarchy = {}
    full_names = {}
    if policy_filedata:
        log.debug('POLICY CLASS {0} has file data'.format(policy_class))
        policy_filedata_split = re.sub(r'\]$',
                                       '',
                                       re.sub(r'^\[',
                                              '',
                                              policy_filedata.replace(module_policy_data.reg_pol_header, ''))
                                       ).split('][')

        for policy_item in policy_filedata_split:
            policy_item_key = policy_item.split('{0};'.format(chr(0)))[0]
            if policy_item_key:
                for admx_item in REGKEY_XPATH(admx_policy_definitions, keyvalue=policy_item_key.lower()):
                    if etree.QName(admx_item).localname == 'policy':
                        if admx_item not in admx_policies:
                            admx_policies.append(admx_item)
                    else:
                        for policy_item in POLICY_ANCESTOR_XPATH(admx_item):
                            if policy_item not in admx_policies:
                                admx_policies.append(policy_item)

        log.debug('{0} policies to examine'.format(len(admx_policies)))
        if return_not_configured:
            log.debug('returning non configured policies')
            not_configured_policies = ALL_CLASS_POLICY_XPATH(admx_policy_definitions, registry_class=policy_class)
            for policy_item in admx_policies:
                not_configured_policies.remove(policy_item)

            for not_configured_policy in not_configured_policies:
                policy_vals[not_configured_policy.attrib['name']] = 'Not Configured'
                if return_full_policy_names:
                    full_names[not_configured_policy.attrib['name']] = _getFullPolicyName(
                            not_configured_policy,
                            not_configured_policy.attrib['name'],
                            return_full_policy_names,
                            adml_policy_resources)
        for admx_policy in admx_policies:
            this_key = None
            this_valuename = None
            this_policyname = None
            this_policy_setting = 'Not Configured'
            element_only_enabled_disabled = True
            explicit_enable_disable_value_setting = False

            if 'key' in admx_policy.attrib:
                this_key = admx_policy.attrib['key']
            else:
                log.error('policy item {0} does not have the required "key" attribute'.format(admx_policy.attrib))
                break
            if 'valueName' in admx_policy.attrib:
                this_valuename = admx_policy.attrib['valueName']
            if 'name' in admx_policy.attrib:
                this_policyname = admx_policy.attrib['name']
            else:
                log.error('policy item {0} does not have the required "name" attribute'.format(admx_policy.attrib))
                break
            if ENABLED_VALUE_XPATH(admx_policy) and this_policy_setting == 'Not Configured':
                element_only_enabled_disabled = False
                explicit_enable_disable_value_setting = True
                if _checkValueItemParent(admx_policy,
                                         this_policyname,
                                         this_key,
                                         this_valuename,
                                         ENABLED_VALUE_XPATH,
                                         policy_filedata):
                    this_policy_setting = 'Enabled'
                    log.debug('{0} is enabled'.format(this_policyname))
                    policy_vals[this_policyname] = this_policy_setting
            if DISABLED_VALUE_XPATH(admx_policy) and this_policy_setting == 'Not Configured':
                element_only_enabled_disabled = False
                explicit_enable_disable_value_setting = True
                if _checkValueItemParent(admx_policy,
                                         this_policyname,
                                         this_key,
                                         this_valuename,
                                         DISABLED_VALUE_XPATH,
                                         policy_filedata):
                    this_policy_setting = 'Disabled'
                    log.debug('{0} is disabled'.format(this_policyname))
                    policy_vals[this_policyname] = this_policy_setting
            if ENABLED_LIST_XPATH(admx_policy) and this_policy_setting == 'Not Configured':
                element_only_enabled_disabled = False
                explicit_enable_disable_value_setting = True
                if _checkListItem(admx_policy, this_policyname, this_key, ENABLED_LIST_XPATH, policy_filedata):
                    this_policy_setting = 'Enabled'
                    log.debug('{0} is enabled'.format(this_policyname))
                    policy_vals[this_policyname] = this_policy_setting
            if DISABLED_LIST_XPATH(admx_policy) and this_policy_setting == 'Not Configured':
                element_only_enabled_disabled = False
                explicit_enable_disable_value_setting = True
                if _checkListItem(admx_policy, this_policyname, this_key, DISABLED_LIST_XPATH, policy_filedata):
                    this_policy_setting = 'Disabled'
                    log.debug('{0} is disabled'.format(this_policyname))
                    policy_vals[this_policyname] = this_policy_setting

            if not explicit_enable_disable_value_setting and this_valuename:
                # the policy has a key/valuename but no explicit enabled/Disabled Value or List
                # these seem to default to a REG_DWORD 1 = "Enabled" **del. = "Disabled"
                if _regexSearchRegPolData(re.escape(_buildKnownDataSearchString(this_key,
                                                                                this_valuename,
                                                                                'REG_DWORD',
                                                                                '1')),
                                          policy_filedata):
                    this_policy_setting = 'Enabled'
                    log.debug('{0} is enabled'.format(this_policyname))
                    policy_vals[this_policyname] = this_policy_setting
                elif _regexSearchRegPolData(re.escape(_buildKnownDataSearchString(this_key,
                                                                                  this_valuename,
                                                                                  'REG_DWORD',
                                                                                  None,
                                                                                  check_deleted=True)),
                                            policy_filedata):
                    this_policy_setting = 'Disabled'
                    log.debug('{0} is disabled'.format(this_policyname))
                    policy_vals[this_policyname] = this_policy_setting

            if ELEMENTS_XPATH(admx_policy):
                if element_only_enabled_disabled or this_policy_setting == 'Enabled':
                    # TODO does this need to be modified based on the 'required' attribute?
                    required_elements = {}
                    configured_elements = {}
                    policy_disabled_elements = 0
                    for elements_item in ELEMENTS_XPATH(admx_policy):
                        for child_item in elements_item.getchildren():
                            this_element_name = _getFullPolicyName(child_item,
                                                                   child_item.attrib['id'],
                                                                   return_full_policy_names,
                                                                   adml_policy_resources)
                            required_elements[this_element_name] = None
                            child_key = this_key
                            child_valuename = this_valuename
                            if 'key' in child_item.attrib:
                                child_key = child_item.attrib['key']
                            if 'valueName' in child_item.attrib:
                                child_valuename = child_item.attrib['valueName']

                            if etree.QName(child_item).localname == 'boolean':
                                # https://msdn.microsoft.com/en-us/library/dn605978(v=vs.85).aspx
                                if child_item.getchildren():
                                    if TRUE_VALUE_XPATH(child_item) and this_element_name not in configured_elements:
                                        if _checkValueItemParent(child_item,
                                                                 this_policyname,
                                                                 child_key,
                                                                 child_valuename,
                                                                 TRUE_VALUE_XPATH,
                                                                 policy_filedata):
                                            configured_elements[this_element_name] = True
                                            msg = 'element {0} is configured true'
                                            log.debug(msg.format(child_item.attrib['id']))
                                    if FALSE_VALUE_XPATH(child_item) and this_element_name not in configured_elements:
                                        if _checkValueItemParent(child_item,
                                                                 this_policyname,
                                                                 child_key,
                                                                 child_valuename,
                                                                 FALSE_VALUE_XPATH,
                                                                 policy_filedata):
                                            configured_elements[this_element_name] = False
                                            policy_disabled_elements = policy_disabled_elements + 1
                                            msg = 'element {0} is configured false'
                                            log.debug(msg.format(child_item.attrib['id']))
                                    # WARNING - no standard admx files use true/falseList
                                    # so this hasn't actually been tested
                                    if TRUE_LIST_XPATH(child_item) and this_element_name not in configured_elements:
                                        log.debug('checking trueList')
                                        if _checkListItem(child_item,
                                                          this_policyname,
                                                          this_key,
                                                          TRUE_LIST_XPATH,
                                                          policy_filedata):
                                            configured_elements[this_element_name] = True
                                            msg = 'element {0} is configured true'
                                            log.debug(msg.format(child_item.attrib['id']))
                                    if FALSE_LIST_XPATH(child_item) and this_element_name not in configured_elements:
                                        log.debug('checking falseList')
                                        if _checkListItem(child_item,
                                                          this_policyname,
                                                          this_key,
                                                          FALSE_LIST_XPATH,
                                                          policy_filedata):
                                            configured_elements[this_element_name] = False
                                            policy_disabled_elements = policy_disabled_elements + 1
                                            msg = 'element {0} is configured false'
                                            log.debug(msg.format(child_item.attrib['id']))
                                else:
                                    if _regexSearchRegPolData(re.escape(_processValueItem(child_item,
                                                                                          child_key,
                                                                                          child_valuename,
                                                                                          admx_policy,
                                                                                          elements_item,
                                                                                          check_deleted=True)),
                                                              policy_filedata):
                                        configured_elements[this_element_name] = False
                                        policy_disabled_elements = policy_disabled_elements + 1
                                        log.debug('element {0} is configured false'.format(child_item.attrib['id']))
                                    elif _regexSearchRegPolData(re.escape(_processValueItem(child_item,
                                                                                            child_key,
                                                                                            child_valuename,
                                                                                            admx_policy,
                                                                                            elements_item,
                                                                                            check_deleted=False)),
                                                                policy_filedata):
                                        configured_elements[this_element_name] = True
                                        log.debug('element {0} is configured true'.format(child_item.attrib['id']))
                            elif etree.QName(child_item).localname == 'decimal' \
                                    or etree.QName(child_item).localname == 'text' \
                                    or etree.QName(child_item).localname == 'longDecimal' \
                                    or etree.QName(child_item).localname == 'multiText':
                                # https://msdn.microsoft.com/en-us/library/dn605987(v=vs.85).aspx
                                if _regexSearchRegPolData(re.escape(_processValueItem(child_item,
                                                                                      child_key,
                                                                                      child_valuename,
                                                                                      admx_policy,
                                                                                      elements_item,
                                                                                      check_deleted=True)),
                                                          policy_filedata):
                                    configured_elements[this_element_name] = 'Disabled'
                                    policy_disabled_elements = policy_disabled_elements + 1
                                    log.debug('element {0} is disabled'.format(child_item.attrib['id']))
                                elif _regexSearchRegPolData(re.escape(_processValueItem(child_item,
                                                                                        child_key,
                                                                                        child_valuename,
                                                                                        admx_policy,
                                                                                        elements_item,
                                                                                        check_deleted=False)),
                                                            policy_filedata):
                                    configured_value = _getDataFromRegPolData(_processValueItem(child_item,
                                                                                                child_key,
                                                                                                child_valuename,
                                                                                                admx_policy,
                                                                                                elements_item,
                                                                                                check_deleted=False),
                                                                              policy_filedata)
                                    configured_elements[this_element_name] = configured_value
                                    log.debug('element {0} is enabled, value == {1}'.format(
                                            child_item.attrib['id'],
                                            configured_value))
                            elif etree.QName(child_item).localname == 'enum':
                                if _regexSearchRegPolData(re.escape(_processValueItem(child_item,
                                                                                      child_key,
                                                                                      child_valuename,
                                                                                      admx_policy,
                                                                                      elements_item,
                                                                                      check_deleted=True)),
                                                          policy_filedata):
                                    log.debug('enum element {0} is disabled'.format(child_item.attrib['id']))
                                    configured_elements[this_element_name] = 'Disabled'
                                    policy_disabled_elements = policy_disabled_elements + 1
                                else:
                                    for enum_item in child_item.getchildren():
                                        if _checkValueItemParent(enum_item,
                                                                 child_item.attrib['id'],
                                                                 child_key,
                                                                 child_valuename,
                                                                 VALUE_XPATH,
                                                                 policy_filedata):
                                            if VALUE_LIST_XPATH(enum_item):
                                                log.debug('enum item has a valueList')
                                                if _checkListItem(enum_item,
                                                                  this_policyname,
                                                                  child_key,
                                                                  VALUE_LIST_XPATH,
                                                                  policy_filedata):
                                                    log.debug('all valueList items exist in file')
                                                    configured_elements[this_element_name] = _getAdmlDisplayName(
                                                            adml_policy_resources,
                                                            enum_item.attrib['displayName'])
                                                    break
                                            else:
                                                configured_elements[this_element_name] = _getAdmlDisplayName(
                                                        adml_policy_resources,
                                                        enum_item.attrib['displayName'])
                                                break
                            elif etree.QName(child_item).localname == 'list':
                                return_value_name = False
                                if 'explicitValue' in child_item.attrib \
                                        and child_item.attrib['explicitValue'].lower() == 'true':
                                    log.debug('explicitValue list, we will return value names')
                                    return_value_name = True
                                if _regexSearchRegPolData(re.escape(_processValueItem(child_item,
                                                                                      child_key,
                                                                                      child_valuename,
                                                                                      admx_policy,
                                                                                      elements_item,
                                                                                      check_deleted=False)
                                                                    ) + r'(?!\*\*delvals\.)',
                                                          policy_filedata):
                                    configured_value = _getDataFromRegPolData(_processValueItem(child_item,
                                                                                                child_key,
                                                                                                child_valuename,
                                                                                                admx_policy,
                                                                                                elements_item,
                                                                                                check_deleted=False),
                                                                              policy_filedata,
                                                                              return_value_name=return_value_name)
                                    configured_elements[this_element_name] = configured_value
                                    log.debug('element {0} is enabled values: {1}'.format(child_item.attrib['id'],
                                                                                          configured_value))
                                elif _regexSearchRegPolData(re.escape(_processValueItem(child_item,
                                                                                        child_key,
                                                                                        child_valuename,
                                                                                        admx_policy,
                                                                                        elements_item,
                                                                                        check_deleted=True)),
                                                            policy_filedata):
                                    configured_elements[this_element_name] = "Disabled"
                                    policy_disabled_elements = policy_disabled_elements + 1
                                    log.debug('element {0} is disabled'.format(child_item.attrib['id']))
                    if element_only_enabled_disabled:
                        if len(required_elements.keys()) > 0 \
                                    and len(configured_elements.keys()) == len(required_elements.keys()):
                            if policy_disabled_elements == len(required_elements.keys()):
                                log.debug('{0} is disabled by all enum elements'.format(this_policyname))
                                policy_vals[this_policyname] = 'Disabled'
                            else:
                                policy_vals[this_policyname] = configured_elements
                                log.debug('{0} is enabled by enum elements'.format(this_policyname))
                    else:
                        if this_policy_setting == 'Enabled':
                            policy_vals[this_policyname] = configured_elements
            if return_full_policy_names and this_policyname in policy_vals:
                full_names[this_policyname] = _getFullPolicyName(
                        admx_policy,
                        admx_policy.attrib['name'],
                        return_full_policy_names,
                        adml_policy_resources)
            if this_policyname in policy_vals:
                hierarchy[this_policyname] = _build_parent_list(admx_policy,
                                                                admx_policy_definitions,
                                                                return_full_policy_names,
                                                                adml_policy_resources)
    if policy_vals and return_full_policy_names and not hierarchical_return:
        unpathed_dict = {}
        pathed_dict = {}
        for policy_item in policy_vals.keys():
            if full_names[policy_item] in policy_vals:
                # add this item with the path'd full name
                full_path_list = hierarchy[policy_item]
                full_path_list.reverse()
                full_path_list.append(full_names[policy_item])
                policy_vals['\\'.join(full_path_list)] = policy_vals.pop(policy_item)
                pathed_dict[full_names[policy_item]] = True
            else:
                policy_vals[full_names[policy_item]] = policy_vals.pop(policy_item)
                unpathed_dict[full_names[policy_item]] = policy_item
        # go back and remove any "unpathed" policies that need a full path
        for path_needed in pathed_dict.keys():
            # remove the item with the same full name and re-add it w/a path'd version
            full_path_list = hierarchy[unpathed_dict[path_needed]]
            full_path_list.reverse()
            full_path_list.append(path_needed)
            log.debug('full_path_list == {0}'.format(full_path_list))
            policy_vals['\\'.join(full_path_list)] = policy_vals.pop(path_needed)
    if policy_vals and hierarchical_return:
        if hierarchy:
            for hierarchy_item in hierarchy.keys():
                if hierarchy_item in policy_vals:
                    tdict = {}
                    first_item = True
                    for item in hierarchy[hierarchy_item]:
                        newdict = {}
                        if first_item:
                            h_policy_name = hierarchy_item
                            if return_full_policy_names:
                                h_policy_name = full_names[hierarchy_item]
                            newdict[item] = {h_policy_name: policy_vals.pop(hierarchy_item)}
                            first_item = False
                        else:
                            newdict[item] = tdict
                        tdict = newdict
                    if tdict:
                        policy_vals = dictupdate.update(policy_vals, tdict)
        policy_vals = {
                        module_policy_data.admx_registry_classes[policy_class]['lgpo_section']: {
                            'Administrative Templates': policy_vals
                        }
                      }
    return policy_vals


def _build_parent_list(policy_definition,
                       admx_policy_definitions,
                       return_full_policy_names,
                       adml_policy_resources):
    '''
    helper functioon to build a list containing parent elements of the ADMX policy
    '''
    parent_list = []
    policy_namespace = policy_definition.nsmap.keys()[0]
    parent_category = policy_definition.xpath('{0}:parentCategory/@ref'.format(policy_namespace),
                                              namespaces=policy_definition.nsmap)
    if parent_category:
        parent_category = parent_category[0]
        nsmap_xpath = '/policyDefinitions/policyNamespaces/{0}:*'.format(policy_namespace)
        this_namespace_map = _buildElementNsmap(admx_policy_definitions.xpath(nsmap_xpath,
                                                                              namespaces=policy_definition.nsmap))
        this_namespace_map = dictupdate.update(this_namespace_map, policy_definition.nsmap)
        parent_list = _admx_policy_parent_walk(parent_list,
                                               policy_namespace,
                                               parent_category,
                                               this_namespace_map,
                                               admx_policy_definitions,
                                               return_full_policy_names,
                                               adml_policy_resources)
    return parent_list


def _admx_policy_parent_walk(path,
                             policy_namespace,
                             parent_category,
                             policy_nsmap,
                             admx_policy_definitions,
                             return_full_policy_names,
                             adml_policy_resources):
    '''
    helper function to recursively walk up the ADMX namespaces and build the hierarchy for the policy
    '''
    category_xpath_string = '/policyDefinitions/categories/{0}:category[@name="{1}"]'
    using_xpath_string = '/policyDefinitions/policyNamespaces/{0}:using'
    if parent_category.find(':') >= 0:
        # the parent is in another namespace
        policy_namespace = parent_category.split(':')[0]
        parent_category = parent_category.split(':')[1]
        using_xpath_string = using_xpath_string.format(policy_namespace)
        policy_nsmap = dictupdate.update(policy_nsmap,
                                         _buildElementNsmap(admx_policy_definitions.xpath(using_xpath_string,
                                                                                          namespaces=policy_nsmap)))
    category_xpath_string = category_xpath_string.format(policy_namespace, parent_category)
    if admx_policy_definitions.xpath(category_xpath_string, namespaces=policy_nsmap):
        tparent_category = admx_policy_definitions.xpath(category_xpath_string,
                                                         namespaces=policy_nsmap)[0]
        this_parent_name = _getFullPolicyName(tparent_category,
                                              tparent_category.attrib['name'],
                                              return_full_policy_names,
                                              adml_policy_resources)
        path.append(this_parent_name)
        if tparent_category.xpath('{0}:parentCategory/@ref'.format(policy_namespace), namespaces=policy_nsmap):
            # parent has a parent
            path = _admx_policy_parent_walk(path,
                                            policy_namespace,
                                            tparent_category.xpath('{0}:parentCategory/@ref'.format(policy_namespace),
                                                                   namespaces=policy_nsmap)[0],
                                            policy_nsmap,
                                            admx_policy_definitions,
                                            return_full_policy_names,
                                            adml_policy_resources)
    return path


def _read_regpol_file(reg_pol_path):
    '''
    helper function to read a reg policy file and return decoded data
    '''
    returndata = None
    if os.path.exists(reg_pol_path):
        with open(reg_pol_path, 'rb') as pol_file:
            returndata = pol_file.read()
        returndata = returndata.decode('utf-16-le')
    return returndata


def _regexSearchKeyValueCombo(policy_data, policy_regpath, policy_regkey):
    '''
    helper function to do a search of Policy data from a registry.pol file
    for a policy_regpath and policy_regkey combo
    '''
    if policy_data:
        specialValueRegex = r'(\*\*Del\.|\*\*DelVals\.){0,1}'
        _thisSearch = r'\[{1}{0};{3}{2}{0};'.format(
                chr(0),
                re.escape(policy_regpath),
                re.escape(policy_regkey),
                specialValueRegex)
        match = re.search(_thisSearch, policy_data, re.IGNORECASE)
        if match:
            return policy_data[match.start():(policy_data.index(']', match.end())) + 1]

    return None


def _write_regpol_data(data_to_write, policy_file_path):
    '''
    helper function to actually write the data to a Registry.pol file
    '''
    try:
        if data_to_write:
            reg_pol_header = u'\u5250\u6765\x01\x00'
            with open(policy_file_path, 'wb') as pol_file:
                if not data_to_write.startswith(reg_pol_header):
                    pol_file.write(reg_pol_header.encode('utf-16-le'))
                pol_file.write(data_to_write.encode('utf-16-le'))
    except Exception as e:
        msg = 'An error occurred attempting to write to {0}, the exception was {1}'.format(policy_file_path, e)
        raise CommandExecutionError(msg)


def _policyFileReplaceOrAppendList(string_list, policy_data):
    '''
    helper function to take a list of strings for registry.pol file data
    and update existing strings or append the strings
    '''
    if not policy_data:
        policy_data = ''
    # we are going to clean off the special pre-fixes, so we get only the valuename
    specialValueRegex = r'(\*\*Del\.|\*\*DelVals\.){0,1}'
    for this_string in string_list:
        list_item_key = this_string.split('{0};'.format(chr(0)))[0].lstrip('[')
        list_item_value_name = re.sub(specialValueRegex,
                                      '', this_string.split('{0};'.format(chr(0)))[1],
                                      flags=re.IGNORECASE)
        log.debug('item value name is {0}'.format(list_item_value_name))
        data_to_replace = _regexSearchKeyValueCombo(policy_data,
                                                    list_item_key,
                                                    list_item_value_name)
        if data_to_replace:
            log.debug('replacing {0} with {1}'.format([data_to_replace], [this_string]))
            policy_data = policy_data.replace(data_to_replace, this_string)
        else:
            log.debug('appending {0}'.format([this_string]))
            policy_data = ''.join([policy_data, this_string])
    return policy_data


def _policyFileReplaceOrAppend(this_string, policy_data, append_only=False):
    '''
    helper function to take a admx policy string for registry.pol file data
    and update existing string or append the string to the data
    '''
    # we are going to clean off the special pre-fixes, so we get only the valuename
    if not policy_data:
        policy_data = ''
    specialValueRegex = r'(\*\*Del\.|\*\*DelVals\.){0,1}'
    item_key = None
    item_value_name = None
    data_to_replace = None
    if not append_only:
        item_key = this_string.split('{0};'.format(chr(0)))[0].lstrip('[')
        item_value_name = re.sub(specialValueRegex,
                                 '',
                                 this_string.split('{0};'.format(chr(0)))[1],
                                 flags=re.IGNORECASE)
        log.debug('item value name is {0}'.format(item_value_name))
        data_to_replace = _regexSearchKeyValueCombo(policy_data, item_key, item_value_name)
    if data_to_replace:
        log.debug('replacing {0} with {1}'.format([data_to_replace], [this_string]))
        policy_data = policy_data.replace(data_to_replace, this_string)
    else:
        log.debug('appending {0}'.format([this_string]))
        policy_data = ''.join([policy_data, this_string])

    return policy_data


def _writeAdminTemplateRegPolFile(admtemplate_data,
                                  admx_policy_definitions=None,
                                  adml_policy_resources=None,
                                  display_language='en-US',
                                  registry_class='Machine'):
    u'''
    helper function to prep/write adm template data to the Registry.pol file

    each file begins with REGFILE_SIGNATURE (u'\u5250\u6765') and REGISTRY_FILE_VERSION (u'\x01\00')

    https://msdn.microsoft.com/en-us/library/aa374407(VS.85).aspx
    [Registry Path<NULL>;Reg Value<NULL>;Reg Type<NULL>;SizeInBytes<NULL>;Data<NULL>]
    '''
    existing_data = ''
    base_policy_settings = {}
    policy_data = _policy_info()
    policySearchXpath = etree.XPath('//*[@*[local-name() = "id"] = $id or @*[local-name() = "name"] = $id]')
    try:
        if admx_policy_definitions is None or adml_policy_resources is None:
            admx_policy_definitions, adml_policy_resources = _processPolicyDefinitions(
                    display_language=display_language)
        base_policy_settings = _checkAllAdmxPolicies(registry_class,
                                                     admx_policy_definitions,
                                                     adml_policy_resources,
                                                     return_full_policy_names=False,
                                                     hierarchical_return=False,
                                                     return_not_configured=False)
        log.debug('preparing to loop through policies requested to be configured')
        for adm_policy in admtemplate_data.keys():
            if str(admtemplate_data[adm_policy]).lower() == 'not configured':
                if adm_policy in base_policy_settings:
                    base_policy_settings.pop(adm_policy)
            else:
                log.debug('adding {0} to base_policy_settings'.format(adm_policy))
                base_policy_settings[adm_policy] = admtemplate_data[adm_policy]
        for admPolicy in base_policy_settings.keys():
            log.debug('working on admPolicy {0}'.format(admPolicy))
            explicit_enable_disable_value_setting = False
            this_key = None
            this_valuename = None
            if str(base_policy_settings[admPolicy]).lower() == 'disabled':
                log.debug('time to disable {0}'.format(admPolicy))
                this_policy = policySearchXpath(admx_policy_definitions, id=admPolicy)
                if this_policy:
                    this_policy = this_policy[0]
                    if 'class' in this_policy.attrib:
                        if this_policy.attrib['class'] == registry_class or this_policy.attrib['class'] == 'Both':
                            if 'key' in this_policy.attrib:
                                this_key = this_policy.attrib['key']
                            else:
                                msg = 'policy item {0} does not have the required "key" attribute'
                                log.error(msg.format(this_policy.attrib))
                                break
                            if 'valueName' in this_policy.attrib:
                                this_valuename = this_policy.attrib['valueName']
                            if DISABLED_VALUE_XPATH(this_policy):
                                # set the disabled value in the registry.pol file
                                explicit_enable_disable_value_setting = True
                                disabled_value_string = _checkValueItemParent(this_policy,
                                                                              admPolicy,
                                                                              this_key,
                                                                              this_valuename,
                                                                              DISABLED_VALUE_XPATH,
                                                                              None,
                                                                              check_deleted=False,
                                                                              test_item=False)
                                existing_data = _policyFileReplaceOrAppend(disabled_value_string,
                                                                           existing_data)
                            if DISABLED_LIST_XPATH(this_policy):
                                explicit_enable_disable_value_setting = True
                                disabled_list_strings = _checkListItem(this_policy,
                                                                       admPolicy,
                                                                       this_key,
                                                                       DISABLED_LIST_XPATH,
                                                                       None,
                                                                       test_items=False)
                                log.debug('working with disabledList portion of {0}'.format(admPolicy))
                                existing_data = _policyFileReplaceOrAppendList(disabled_list_strings,
                                                                               existing_data)
                            if not explicit_enable_disable_value_setting and this_valuename:
                                disabled_value_string = _buildKnownDataSearchString(this_key,
                                                                                    this_valuename,
                                                                                    'REG_DWORD',
                                                                                    None,
                                                                                    check_deleted=True)
                                existing_data = _policyFileReplaceOrAppend(disabled_value_string,
                                                                           existing_data)
                            if ELEMENTS_XPATH(this_policy):
                                log.debug('checking elements of {0}'.format(admPolicy))
                                for elements_item in ELEMENTS_XPATH(this_policy):
                                    for child_item in elements_item.getchildren():
                                        child_key = this_key
                                        child_valuename = this_valuename
                                        if 'key' in child_item.attrib:
                                            child_key = child_item.attrib['key']
                                        if 'valueName' in child_item.attrib:
                                            child_valuename = child_item.attrib['valueName']
                                        if etree.QName(child_item).localname == 'boolean' \
                                                and (TRUE_LIST_XPATH(child_item) or FALSE_LIST_XPATH(child_item)):
                                            # WARNING: no OOB adm files use true/falseList items
                                            # this has not been fully vetted
                                            temp_dict = {'trueList': TRUE_LIST_XPATH, 'falseList': FALSE_LIST_XPATH}
                                            for this_list in temp_dict.keys():
                                                disabled_list_strings = _checkListItem(
                                                        child_item,
                                                        admPolicy,
                                                        child_key,
                                                        temp_dict[this_list],
                                                        None,
                                                        test_items=False)
                                                log.debug('working with {1} portion of {0}'.format(
                                                        admPolicy,
                                                        this_list))
                                                existing_data = _policyFileReplaceOrAppendList(
                                                        disabled_list_strings,
                                                        existing_data)
                                        elif etree.QName(child_item).localname == 'boolean' \
                                                or etree.QName(child_item).localname == 'decimal' \
                                                or etree.QName(child_item).localname == 'text' \
                                                or etree.QName(child_item).localname == 'longDecimal' \
                                                or etree.QName(child_item).localname == 'multiText' \
                                                or etree.QName(child_item).localname == 'enum':
                                            disabled_value_string = _processValueItem(child_item,
                                                                                      child_key,
                                                                                      child_valuename,
                                                                                      this_policy,
                                                                                      elements_item,
                                                                                      check_deleted=True)
                                            msg = 'I have disabled value string of {0}'
                                            log.debug(msg.format(disabled_value_string))
                                            existing_data = _policyFileReplaceOrAppend(
                                                    disabled_value_string,
                                                    existing_data)
                                        elif etree.QName(child_item).localname == 'list':
                                            disabled_value_string = _processValueItem(child_item,
                                                                                      child_key,
                                                                                      child_valuename,
                                                                                      this_policy,
                                                                                      elements_item,
                                                                                      check_deleted=True)
                                            msg = 'I have disabled value string of {0}'
                                            log.debug(msg.format(disabled_value_string))
                                            existing_data = _policyFileReplaceOrAppend(
                                                    disabled_value_string,
                                                    existing_data)
                        else:
                            msg = 'policy {0} was found but it does not appear to be valid for the class {1}'
                            log.error(msg.format(admPolicy, registry_class))
                    else:
                        msg = 'policy item {0} does not have the requried "class" attribute'
                        log.error(msg.format(this_policy.attrib))
            else:
                log.debug('time to enable and set the policy "{0}"'.format(admPolicy))
                this_policy = policySearchXpath(admx_policy_definitions, id=admPolicy)
                if this_policy:
                    this_policy = this_policy[0]
                    if 'class' in this_policy.attrib:
                        if this_policy.attrib['class'] == registry_class or this_policy.attrib['class'] == 'Both':
                            if 'key' in this_policy.attrib:
                                this_key = this_policy.attrib['key']
                            else:
                                msg = 'policy item {0} does not have the required "key" attribute'
                                log.error(msg.format(this_policy.attrib))
                                break
                            if 'valueName' in this_policy.attrib:
                                this_valuename = this_policy.attrib['valueName']

                            if ENABLED_VALUE_XPATH(this_policy):
                                explicit_enable_disable_value_setting = True
                                enabled_value_string = _checkValueItemParent(this_policy,
                                                                             admPolicy,
                                                                             this_key,
                                                                             this_valuename,
                                                                             ENABLED_VALUE_XPATH,
                                                                             None,
                                                                             check_deleted=False,
                                                                             test_item=False)
                                existing_data = _policyFileReplaceOrAppend(
                                        enabled_value_string,
                                        existing_data)
                            if ENABLED_LIST_XPATH(this_policy):
                                explicit_enable_disable_value_setting = True
                                enabled_list_strings = _checkListItem(this_policy,
                                                                      admPolicy,
                                                                      this_key,
                                                                      ENABLED_LIST_XPATH,
                                                                      None,
                                                                      test_items=False)
                                log.debug('working with enabledList portion of {0}'.format(admPolicy))
                                existing_data = _policyFileReplaceOrAppendList(
                                        enabled_list_strings,
                                        existing_data)
                            if not explicit_enable_disable_value_setting and this_valuename:
                                enabled_value_string = _buildKnownDataSearchString(this_key,
                                                                                   this_valuename,
                                                                                   'REG_DWORD',
                                                                                   '1',
                                                                                   check_deleted=False)
                                existing_data = _policyFileReplaceOrAppend(
                                        enabled_value_string,
                                        existing_data)
                            if ELEMENTS_XPATH(this_policy):
                                for elements_item in ELEMENTS_XPATH(this_policy):
                                    for child_item in elements_item.getchildren():
                                        child_key = this_key
                                        child_valuename = this_valuename
                                        if 'key' in child_item.attrib:
                                            child_key = child_item.attrib['key']
                                        if 'valueName' in child_item.attrib:
                                            child_valuename = child_item.attrib['valueName']
                                        if child_item.attrib['id'] in base_policy_settings[admPolicy]:
                                            if etree.QName(child_item).localname == 'boolean' and (
                                                    TRUE_LIST_XPATH(child_item) or FALSE_LIST_XPATH(child_item)):
                                                list_strings = []
                                                if base_policy_settings[admPolicy][child_item.attrib['id']]:
                                                    list_strings = _checkListItem(child_item,
                                                                                  admPolicy,
                                                                                  child_key,
                                                                                  TRUE_LIST_XPATH,
                                                                                  None,
                                                                                  test_items=False)
                                                    log.debug('working with trueList portion of {0}'.format(admPolicy))
                                                else:
                                                    list_strings = _checkListItem(child_item,
                                                                                  admPolicy,
                                                                                  child_key,
                                                                                  FALSE_LIST_XPATH,
                                                                                  None,
                                                                                  test_items=False)
                                                existing_data = _policyFileReplaceOrAppendList(
                                                        list_strings,
                                                        existing_data)
                                            if etree.QName(child_item).localname == 'boolean' and (
                                                    TRUE_VALUE_XPATH(child_item) or FALSE_VALUE_XPATH(child_item)):
                                                value_string = ''
                                                if base_policy_settings[admPolicy][child_item.attrib['id']]:
                                                    value_string = _checkValueItemParent(child_item,
                                                                                         admPolicy,
                                                                                         child_key,
                                                                                         child_valuename,
                                                                                         TRUE_VALUE_XPATH,
                                                                                         None,
                                                                                         check_deleted=False,
                                                                                         test_item=False)
                                                else:
                                                    value_string = _checkValueItemParent(child_item,
                                                                                         admPolicy,
                                                                                         child_key,
                                                                                         child_valuename,
                                                                                         FALSE_VALUE_XPATH,
                                                                                         None,
                                                                                         check_deleted=False,
                                                                                         test_item=False)
                                                existing_data = _policyFileReplaceOrAppend(
                                                        value_string,
                                                        existing_data)
                                            if etree.QName(child_item).localname == 'boolean' \
                                                    or etree.QName(child_item).localname == 'decimal' \
                                                    or etree.QName(child_item).localname == 'text' \
                                                    or etree.QName(child_item).localname == 'longDecimal' \
                                                    or etree.QName(child_item).localname == 'multiText':
                                                enabled_value_string = _processValueItem(
                                                        child_item,
                                                        child_key,
                                                        child_valuename,
                                                        this_policy,
                                                        elements_item,
                                                        check_deleted=False,
                                                        this_element_value=base_policy_settings[admPolicy][child_item.attrib['id']])
                                                msg = 'I have enabled value string of {0}'
                                                log.debug(msg.format([enabled_value_string]))
                                                existing_data = _policyFileReplaceOrAppend(
                                                        enabled_value_string,
                                                        existing_data)
                                            elif etree.QName(child_item).localname == 'enum':
                                                for enum_item in child_item.getchildren():
                                                    if base_policy_settings[admPolicy][child_item.attrib['id']] == \
                                                            _getAdmlDisplayName(adml_policy_resources,
                                                                                enum_item.attrib['displayName']
                                                                                ).strip():
                                                        enabled_value_string = _checkValueItemParent(
                                                                enum_item,
                                                                child_item.attrib['id'],
                                                                child_key,
                                                                child_valuename,
                                                                VALUE_XPATH,
                                                                None,
                                                                check_deleted=False,
                                                                test_item=False)
                                                        existing_data = _policyFileReplaceOrAppend(
                                                                enabled_value_string,
                                                                existing_data)
                                                        if VALUE_LIST_XPATH(enum_item):
                                                            enabled_list_strings = _checkListItem(enum_item,
                                                                                                  admPolicy,
                                                                                                  child_key,
                                                                                                  VALUE_LIST_XPATH,
                                                                                                  None,
                                                                                                  test_items=False)
                                                            msg = 'working with valueList portion of {0}'
                                                            log.debug(msg.format(child_item.attrib['id']))
                                                            existing_data = _policyFileReplaceOrAppendList(
                                                                    enabled_list_strings,
                                                                    existing_data)
                                                        break
                                            elif etree.QName(child_item).localname == 'list':
                                                enabled_value_string = _processValueItem(
                                                        child_item,
                                                        child_key,
                                                        child_valuename,
                                                        this_policy,
                                                        elements_item,
                                                        check_deleted=False,
                                                        this_element_value=base_policy_settings[admPolicy][child_item.attrib['id']])
                                                msg = 'I have enabled value string of {0}'
                                                log.debug(msg.format([enabled_value_string]))
                                                existing_data = _policyFileReplaceOrAppend(
                                                        enabled_value_string,
                                                        existing_data,
                                                        append_only=True)
        _write_regpol_data(existing_data, policy_data.admx_registry_classes[registry_class]['policy_path'])
    except Exception as e:
        log.error('Unhandled exception {0} occurred while attempting to write Adm Template Policy File'.format(e))
        return False
    return True


def _getScriptSettingsFromIniFile(policy_info):
    '''
    helper function to parse/read a GPO Startup/Shutdown script file
    '''
    _existingData = _read_regpol_file(policy_info['ScriptIni']['IniPath'])
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
    _machineScriptPolicyPath = os.path.join(os.getenv('WINDIR'),
                                            'System32',
                                            'GroupPolicy',
                                            'Machine',
                                            'Scripts',
                                            'scripts.ini')
    _machinePowershellScriptPolicyPath = os.path.join(os.getenv('WINDIR'),
                                                      'System32',
                                                      'GroupPolicy',
                                                      'Machine',
                                                      'Scripts',
                                                      'psscripts.ini')
    _userScriptPolicyPath = os.path.join(os.getenv('WINDIR'),
                                         'System32',
                                         'GroupPolicy',
                                         'User',
                                         'Scripts',
                                         'scripts.ini')
    _userPowershellScriptPolicyPath = os.path.join(os.getenv('WINDIR'),
                                                   'System32',
                                                   'GroupPolicy',
                                                   'User',
                                                   'Scripts',
                                                   'psscripts.ini')


def _lookup_admin_template(policy_name,
                           policy_class,
                           adml_language='en-US',
                           admx_policy_definitions=None,
                           adml_policy_resources=None):
    '''
    (success_flag, policy_xml_item, policy_name_list, message)
    '''
    policy_aliases = []
    if admx_policy_definitions is None or adml_policy_resources is None:
        admx_policy_definitions, adml_policy_resources = _processPolicyDefinitions(
                display_language=adml_language)
    admx_search_results = ADMX_SEARCH_XPATH(admx_policy_definitions,
                                            policy_name=policy_name,
                                            registry_class=policy_class)
    the_policy = None
    if admx_search_results:
        if len(admx_search_results) == 1:
            the_policy = admx_search_results[0]
            policy_display_name = _getFullPolicyName(
                    the_policy,
                    the_policy.attrib['name'],
                    True,
                    adml_policy_resources)
            policy_aliases.append(policy_display_name)
            policy_aliases.append(the_policy.attrib['name'])
            full_path_list = _build_parent_list(the_policy,
                                                admx_policy_definitions,
                                                True,
                                                adml_policy_resources)
            full_path_list.reverse()
            full_path_list.append(policy_display_name)
            policy_aliases.append('\\'.join(full_path_list))
            return (True, the_policy, policy_aliases, None)
        else:
            msg = 'Admx policy name/id "{0}" is used in multiple admx files'
            return (False, None, [], msg)
    else:
        adml_search_results = ADML_SEARCH_XPATH(adml_policy_resources,
                                                policy_name=policy_name)
        hierarchy = []
        hierarchy_policy_name = policy_name
        if not adml_search_results:
            if '\\' in policy_name:
                hierarchy = policy_name.split('\\')
                policy_name = hierarchy.pop()
                adml_search_results = ADML_SEARCH_XPATH(adml_policy_resources,
                                                        policy_name=policy_name)
        if adml_search_results:
            multiple_adml_entries = False
            suggested_policies = ''
            if len(adml_search_results) > 1:
                multiple_adml_entries = True
            for adml_search_result in adml_search_results:
                dmsg = 'found an adml entry matching the string! {0} -- {1}'
                log.debug(dmsg.format(adml_search_result.tag,
                                      adml_search_result.attrib))
                display_name_searchval = '$({0}.{1})'.format(
                        adml_search_result.tag.split('}')[1],
                        adml_search_result.attrib['id'])
                log.debug('searching for displayName == {0}'.format(display_name_searchval))
                admx_search_results = ADMX_DISPLAYNAME_SEARCH_XPATH(
                        admx_policy_definitions,
                        display_name=display_name_searchval,
                        registry_class=policy_class)
                if admx_search_results:
                    if len(admx_search_results) == 1 or hierarchy and not multiple_adml_entries:
                        found = False
                        for search_result in admx_search_results:
                            found = False
                            if hierarchy:
                                this_hierarchy = _build_parent_list(search_result,
                                                                    admx_policy_definitions,
                                                                    True,
                                                                    adml_policy_resources)
                                this_hierarchy.reverse()
                                if hierarchy == this_hierarchy:
                                    found = True
                            else:
                                found = True
                            if found:
                                dmsg = ('found the admx policy matching '
                                        'the display name {1} -- {0}')
                                log.debug(dmsg.format(search_result, policy_name))
                                if 'name' in search_result.attrib:
                                    policy_display_name = _getFullPolicyName(
                                            search_result,
                                            search_result.attrib['name'],
                                            True,
                                            adml_policy_resources)
                                    policy_aliases.append(policy_display_name)
                                    policy_aliases.append(search_result.attrib['name'])
                                    full_path_list = _build_parent_list(search_result,
                                                                        admx_policy_definitions,
                                                                        True,
                                                                        adml_policy_resources)
                                    full_path_list.reverse()
                                    full_path_list.append(policy_display_name)
                                    policy_aliases.append('\\'.join(full_path_list))
                                    return (True, search_result, policy_aliases, None)
                                else:
                                    msg = ('Admx policy with the display name {0} does not'
                                           'have the required name attribtue')
                                    msg = msg.format(policy_name)
                                    return (False, None, [], msg)
                        if not found:
                            msg = 'Unable to correlate {0} to any policy'.format(hierarchy_policy_name)
                            return (False, None, [], msg)
                    else:
                        for possible_policy in admx_search_results:
                            this_parent_list = _build_parent_list(possible_policy,
                                                                  admx_policy_definitions,
                                                                  True,
                                                                  adml_policy_resources)
                            this_parent_list.reverse()
                            this_parent_list.append(policy_name)
                            if suggested_policies:
                                suggested_policies = ', '.join([suggested_policies,
                                                               '\\'.join(this_parent_list)])
                            else:
                                suggested_policies = '\\'.join(this_parent_list)
                else:
                    msg = 'Unable to find a policy with the name "{0}".'.format(policy_name)
                    return (False, None, [], msg)
            if suggested_policies:
                msg = ('Adml policy name "{0}" is used as the display name'
                       ' for multiple policies.'
                       '  These policies matched: {1}'
                       '.  You can utilize these long names to'
                       ' specify the correct policy')
                return (False, None, [], msg.format(policy_name, suggested_policies))
    return (False, None, [], 'Unable to find {0} policy {1}'.format(policy_class, policy_name))


def list_configurable_policies(policy_class='Machine',
                               include_administrative_templates=True,
                               adml_language='en-US'):
    '''
    list the policies that the execution module can configure
    '''


def get_policy_info(policy_name,
                    policy_class,
                    adml_language='en-US'):
    '''
    returns information about a specified policy

    :str: policy_name
        the name of the policy to lookup

    :str: policy_class
        the class of policy, i.e. machine, user, both

    :str: adml_language
        the adml language to use for Administrative Template data lookup
    '''
    # return the possible policy names and element names
    ret = {'policy_name': policy_name,
           'policy_class': policy_class,
           'policy_aliases': [],
           'policy_found': False,
           'rights_assignment': False,
           'policy_elements': [],
           'message': 'policy not found'}
    policy_class = policy_class.title()
    policy_data = _policy_info()
    admx_policy_definitions, adml_policy_resources = _processPolicyDefinitions(
            display_language=adml_language)
    if policy_class not in policy_data.policies.keys():
        ret['message'] = 'The requested policy class "{0}" is invalid, policy_class should be one of: {1}'.format(
                policy_class,
                ', '.join(policy_data.policies.keys()))
        return ret
    if policy_name in policy_data.policies[policy_class]:
        ret['policy_aliases'].append(policy_data.policies[policy_class]['policies'][policy_name]['Policy'])
        ret['policy_found'] = True
        ret['message'] = ''
        if 'LsaRights' in policy_data.policies[policy_class]['policies'][policy_name]:
            ret['rights_assignment'] = True
        return ret
    else:
        for pol in policy_data.policies[policy_class]['policies'].keys():
            if policy_data.policies[policy_class]['policies'][pol]['Policy'].lower() == policy_name.lower():
                ret['policy_aliases'].append(pol)
                ret['policy_found'] = True
                ret['message'] = ''
                if 'LsaRights' in policy_data.policies[policy_class]['policies'][pol]:
                    ret['rights_assignment'] = True
                return ret
    success, policy_xml_item, policy_name_list, message = _lookup_admin_template(
            policy_name,
            policy_class,
            adml_language=adml_language,
            admx_policy_definitions=admx_policy_definitions,
            adml_policy_resources=adml_policy_resources)
    if success:
        for elements_item in ELEMENTS_XPATH(policy_xml_item):
            for child_item in elements_item.getchildren():
                this_element_name = _getFullPolicyName(child_item,
                                                       child_item.attrib['id'],
                                                       True,
                                                       adml_policy_resources)
                ret['policy_elements'].append(
                        {'element_id': child_item.attrib['id'],
                         'element_aliases': [child_item.attrib['id'], this_element_name]})
        ret['policy_aliases'] = policy_name_list
        ret['policy_found'] = True
        ret['message'] = ''
        return ret
    else:
        ret['message'] = message

    return ret


def get(policy_class=None, return_full_policy_names=True,
        hierarchical_return=False, adml_language='en-US',
        return_not_configured=False):
    '''
    Get a policy value

    :param string policy_class:
        Some policies are both user and computer, by default all policies will be pulled,
        but this can be used to retrieve only a specific policy class
        User/USER/user = retrieve user policies
        Machine/MACHINE/machine/Computer/COMPUTER/computer = retrieve machine/computer policies

    :param boolean return_full_policy_names:
        True/False to return the policy name as it is seen in the gpedit.msc GUI or
        to only return the policy key/id.

    :param boolean hierarchical_return:
        True/False to return the policy data in the hierarchy as seen in the gpedit.msc gui
        The default of False will return data split only into User/Computer configuration sections

    :param str adml_language:
        The adml language to use for processing display/descriptive names
        and enumeration values of admx template data, defaults to en-US

    :param boolean return_not_configured:
        Include Administrative Template policies that are 'Not Configured' in the return data

    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' lgpo.get return_full_policy_names=True
    '''

    vals = {}
    modal_returns = {}
    _policydata = _policy_info()

    if policy_class:
        if policy_class.lower() == 'both':
            policy_class = _policydata.policies.keys()
        elif policy_class.lower() not in [z.lower() for z in _policydata.policies.keys()]:
            msg = 'The policy_class {0} is not an available policy class, please use one of the following: {1}, Both'
            raise SaltInvocationError(msg.format(policy_class,
                                                 ', '.join(_policydata.policies.keys())))
        else:
            policy_class = [policy_class.title()]
    else:
        policy_class = _policydata.policies.keys()
    admxPolicyDefinitions, admlPolicyResources = _processPolicyDefinitions(display_language=adml_language)

    # handle policies statically defined in this module
    for p_class in policy_class:
        this_class_policy_names = _policydata.policies[p_class]['policies']
        class_vals = {}
        for policy_name in this_class_policy_names:
            _pol = None
            if policy_name in _policydata.policies[p_class]['policies']:
                _pol = _policydata.policies[p_class]['policies'][policy_name]
            else:
                for policy in _policydata.policies[p_class]['policies'].keys():
                    if _policydata.policies[p_class]['policies'][policy]['Policy'].upper() == policy_name.upper():
                        _pol = _policydata.policies[p_class]['policies'][policy]
                        policy_name = policy
            if _pol:
                vals_key_name = policy_name
                if 'Registry' in _pol:
                    # get value from registry
                    class_vals[policy_name] = __salt__['reg.read_value'](_pol['Registry']['Hive'],
                                                                         _pol['Registry']['Path'],
                                                                         _pol['Registry']['Value'])['vdata']
                    log.debug('Value {0} found for reg policy {1}'.format(class_vals[policy_name], policy_name))
                elif 'Secedit' in _pol:
                    # get value from secedit
                    _ret, _val = _findOptionValueInSeceditFile(_pol['Secedit']['Option'])
                    if _ret:
                        class_vals[policy_name] = _val
                    else:
                        msg = 'An error occurred attempting to get the value of policy {0} from secedit'
                        raise CommandExecutionError(msg.format(policy_name))
                elif 'NetUserModal' in _pol:
                    # get value from UserNetMod
                    if _pol['NetUserModal']['Modal'] not in modal_returns:
                        modal_returns[_pol['NetUserModal']['Modal']] = win32net.NetUserModalsGet(
                                None,
                                _pol['NetUserModal']['Modal'])
                    class_vals[policy_name] = modal_returns[_pol['NetUserModal']['Modal']][_pol['NetUserModal']['Option']]
                elif 'LsaRights' in _pol:
                    class_vals[policy_name] = _getRightsAssignments(_pol['LsaRights']['Option'])
                elif 'ScriptIni' in _pol:
                    log.debug('Working with ScriptIni setting {0}'.format(policy_name))
                    class_vals[policy_name] = _getScriptSettingsFromIniFile(_pol)
                if policy_name in class_vals:
                    class_vals[policy_name] = _transformValue(class_vals[policy_name],
                                                              _policydata.policies[p_class]['policies'][policy_name],
                                                              'Get')
                if return_full_policy_names:
                    class_vals[_pol['Policy']] = class_vals.pop(policy_name)
                    vals_key_name = _pol['Policy']
                if hierarchical_return:
                    if 'lgpo_section' in _pol:
                        firstItem = True
                        tdict = {}
                        for level in reversed(_pol['lgpo_section']):
                            newdict = {}
                            if firstItem:
                                newdict[level] = {vals_key_name: class_vals.pop(vals_key_name)}
                                firstItem = False
                            else:
                                newdict[level] = tdict
                            tdict = newdict
                        if tdict:
                            class_vals = dictupdate.update(class_vals, tdict)
            else:
                msg = 'The specified policy {0} is not currently available to be configured via this module'
                raise SaltInvocationError(msg.format(policy_name))
        class_vals = dictupdate.update(class_vals,
                                       _checkAllAdmxPolicies(p_class,
                                                             admxPolicyDefinitions,
                                                             admlPolicyResources,
                                                             return_full_policy_names=return_full_policy_names,
                                                             hierarchical_return=hierarchical_return,
                                                             return_not_configured=return_not_configured))
        if _policydata.policies[p_class]['lgpo_section'] not in class_vals:
            temp_dict = {}
            temp_dict[_policydata.policies[p_class]['lgpo_section']] = class_vals
            class_vals = temp_dict
        vals = dictupdate.update(vals, class_vals)

    return vals


def set_computer_policy(name,
                        setting,
                        cumulative_rights_assignments=True,
                        adml_language='en-US'):
    '''
    Set a single computer policy

    :param string name
        the name of the policy to configure

    :param object setting
        the setting to configure the named policy with

    :param bool cumulative_rights_assignments
        Determine how user rights assignment policies are configured.

        If True, user right assignment specifications are simply added to the existing policy
        If False, only the users specified will get the right (any existing will have the right revoked)

    :param str adml_language:
        The language files to use for looking up Administrative Template policy data (i.e. how the policy is
        displayed in the GUI).  Defaults to 'en-US' (U.S. English).

    .. code-block:: bash

        salt '*' lgpo.set_computer_policy LockoutDuration 1440
    '''
    pol = {}
    pol[name] = setting
    ret = set(computer_policy=pol,
              user_policy=None,
              cumulative_rights_assignments=cumulative_rights_assignments,
              adml_language=adml_language)
    return ret


def set_user_policy(name,
                    setting,
                    adml_language='en-US'):
    '''
    Set a single user policy

    :param string name
        the name of the policy to configure

    :param object setting
        the setting to configure the named policy with

    :param str adml_language:
        The language files to use for looking up Administrative Template policy data (i.e. how the policy is
        displayed in the GUI).  Defaults to 'en-US' (U.S. English).

    .. code-block:: bash

        salt '*' lgpo.set_user_policy "Control Panel\\Display\\Disable the Display Control Panel" Enabled
    '''
    pol = {}
    pol[name] = setting
    ret = set(user_policy=pol,
              computer_policy=None,
              cumulative_rights_assignments=True,
              adml_language=adml_language)
    return ret


def set_(computer_policy=None, user_policy=None,
         cumulative_rights_assignments=True,
         adml_language='en-US'):
    '''
    Set a local server policy.

    :param dict computer_policy:
        A dictionary of "policyname: value" pairs of computer policies to set
        'value' should be how it is displayed in the gpedit gui, i.e. if a setting can
        be 'Enabled'/'Disabled', then that should be passed

        Administrative Template data may require dicts within dicts, to specify each element
        of the Administrative Template policy.  Administrative Templates policies are always cumulative.

        Policy names can be specified in a number of ways based on the type of policy:
            Windows Settings Policies:
                These policies can be specified using the GUI display name or the key name from
                the _policy_info class in this module.  The GUI display name is also contained in
                the _policy_info class in this module.
            Administrative Template Policies:
                These can be specified using the policy name as displayed in the GUI (case sensitive).
                Some policies have the same name, but a different location (for example, "Access data
                sources across domains").  These can be differentiated by the "path" in the GUI
                (for example, "Windows Components\\Internet Explorer\\Internet Control Panel\\Security Page\\Internet Zone\\Access data sources across domains").
                Additionally, policies can be specified using the "name" and "id" attributes from the
                admx files.

                For Administrative Templates that have policy elements, each element can be specified using the text string
                as seen in the GUI or using the ID attribute from the admx file.  Due to the way some of the GUI text is laid out,
                some policy element names could include descriptive text that appears before the policy element in the gui.

                Use the get_policy_info function for the policy name to view the element ID/names that the module will accept.

    :param dict user_policy:
       The same setup as the computer_policy, except with data to configure the local
       user policy.

    :param boolean cumulative_rights_assignments:
        Determine how user rights assignment policies are configured.

        If True, user right assignment specifications are simply added to the existing policy
        If False, only the users specified will get the right (any existing will have the right revoked)

    :param str adml_language:
        The language files to use for looking up Administrative Template policy data (i.e. how the policy is
        displayed in the GUI).  Defaults to 'en-US' (U.S. English).

    :rtype: boolean

    CLI Example:

    .. code-block:: bash

        salt '*' lgpo.set computer_policy="{'LockoutDuration': 2, 'RestrictAnonymous': 'Enabled', 'AuditProcessTracking': 'Succes, Failure'}"
    '''

    if computer_policy and not isinstance(computer_policy, dict):
        msg = 'computer_policy must be specified as a dict'
        raise SaltInvocationError(msg)
    if user_policy and not isinstance(user_policy, dict):
        msg = 'user_policy must be specified as a dict'
        raise SaltInvocationError(msg)
    policies = {}
    policies['User'] = user_policy
    policies['Machine'] = computer_policy
    if policies:
        for p_class in policies.keys():
            _secedits = {}
            _modal_sets = {}
            _admTemplateData = {}
            _regedits = {}
            _lsarights = {}
            _policydata = _policy_info()
            admxPolicyDefinitions, admlPolicyResources = _processPolicyDefinitions(display_language=adml_language)
            if policies[p_class]:
                for policy_name in policies[p_class].keys():
                    _pol = None
                    policy_key_name = policy_name
                    if policy_name in _policydata.policies[p_class]['policies']:
                        _pol = _policydata.policies[p_class]['policies'][policy_name]
                    else:
                        for policy in _policydata.policies[p_class]['policies'].keys():
                            if _policydata.policies[p_class]['policies'][policy]['Policy'].upper() == \
                                    policy_name.upper():
                                _pol = _policydata.policies[p_class]['policies'][policy]
                                policy_key_name = policy
                    if _pol:
                        # transform and validate the setting
                        _value = _transformValue(policies[p_class][policy_name],
                                                 _policydata.policies[p_class]['policies'][policy_key_name],
                                                 'Put')
                        if not _validateSetting(_value, _policydata.policies[p_class]['policies'][policy_key_name]):
                            msg = 'The specified value {0} is not an acceptable setting for policy {1}.'
                            raise SaltInvocationError(msg.format(policies[p_class][policy_name], policy_name))
                        if 'Registry' in _pol:
                            # set value in registry
                            log.debug('{0} is a registry policy'.format(policy_name))
                            _regedits[policy_name] = {'policy': _pol, 'value': _value}
                        elif 'Secedit' in _pol:
                            # set value with secedit
                            log.debug('{0} is a Secedit policy'.format(policy_name))
                            if _pol['Secedit']['Section'] not in _secedits:
                                _secedits[_pol['Secedit']['Section']] = []
                            _secedits[_pol['Secedit']['Section']].append(
                                    ' '.join([_pol['Secedit']['Option'],
                                             '=', str(_value)]))
                        elif 'NetUserModal' in _pol:
                            # set value via NetUserModal
                            log.debug('{0} is a NetUserModal policy'.format(policy_name))
                            if _pol['NetUserModal']['Modal'] not in _modal_sets:
                                _modal_sets[_pol['NetUserModal']['Modal']] = {}
                            _modal_sets[_pol['NetUserModal']['Modal']][_pol['NetUserModal']['Option']] = _value
                        elif 'LsaRights' in _pol:
                            log.debug('{0} is a LsaRights policy'.format(policy_name))
                            _lsarights[policy_name] = {'policy': _pol, 'value': _value}
                    else:
                        _value = policies[p_class][policy_name]
                        log.debug('searching for "{0}" in admx data'.format(policy_name))
                        success, the_policy, policy_name_list, msg = _lookup_admin_template(
                                policy_name,
                                p_class,
                                adml_language=adml_language,
                                admx_policy_definitions=admxPolicyDefinitions,
                                adml_policy_resources=admlPolicyResources)
                        if success:
                            policy_name = the_policy.attrib['name']
                            _admTemplateData[policy_name] = _value
                        else:
                            raise SaltInvocationError(msg)
                        if policy_name in _admTemplateData and the_policy is not None:
                            log.debug('setting == {0}'.format(_admTemplateData[policy_name]).lower())
                            log.debug('{0}'.format(str(_admTemplateData[policy_name]).lower()))
                            if str(_admTemplateData[policy_name]).lower() != 'disabled' \
                                    and str(_admTemplateData[policy_name]).lower() != 'not configured':
                                if ELEMENTS_XPATH(the_policy):
                                    if isinstance(_admTemplateData[policy_name], dict):
                                        for elements_item in ELEMENTS_XPATH(the_policy):
                                            for child_item in elements_item.getchildren():
                                                # check each element
                                                log.debug('checking element {0}'.format(child_item.attrib['id']))
                                                temp_element_name = None
                                                this_element_name = _getFullPolicyName(child_item,
                                                                                       child_item.attrib['id'],
                                                                                       True,
                                                                                       admlPolicyResources)
                                                log.debug('id attribute == "{0}"  this_element_name == "{1}"'.format(child_item.attrib['id'], this_element_name))
                                                if this_element_name in _admTemplateData[policy_name]:
                                                    temp_element_name = this_element_name
                                                elif child_item.attrib['id'] in _admTemplateData[policy_name]:
                                                    temp_element_name = child_item.attrib['id']
                                                else:
                                                    msg = ('Element "{0}" must be included'
                                                           ' in the policy configuration for policy {1}')
                                                    raise SaltInvocationError(msg.format(this_element_name, policy_name))
                                                if 'required' in child_item.attrib \
                                                        and child_item.attrib['required'].lower() == 'true':
                                                    if not _admTemplateData[policy_name][temp_element_name]:
                                                        msg = 'Element "{0}" requires a value to be specified'
                                                        raise SaltInvocationError(msg.format(temp_element_name))
                                                if etree.QName(child_item).localname == 'boolean':
                                                    if not isinstance(
                                                            _admTemplateData[policy_name][temp_element_name],
                                                            bool):
                                                        msg = 'Element {0} requires a boolean True or False'
                                                        raise SaltInvocationError(msg.format(temp_element_name))
                                                elif etree.QName(child_item).localname == 'decimal' or \
                                                        etree.QName(child_item).localname == 'longDecimal':
                                                    min_val = 0
                                                    max_val = 9999
                                                    if 'minValue' in child_item.attrib:
                                                        min_val = int(child_item.attrib['minValue'])
                                                    if 'maxValue' in child_item.attrib:
                                                        max_val = int(child_item.attrib['maxValue'])
                                                    if int(_admTemplateData[policy_name][temp_element_name]) \
                                                            < min_val or \
                                                            int(_admTemplateData[policy_name][temp_element_name]) \
                                                            > max_val:
                                                        msg = 'Element "{0}" value must be between {1} and {2}'
                                                        raise SaltInvocationError(msg.format(temp_element_name,
                                                                                             min_val,
                                                                                             max_val))
                                                elif etree.QName(child_item).localname == 'enum':
                                                    # make sure the value is in the enumeration
                                                    found = False
                                                    for enum_item in child_item.getchildren():
                                                        if _admTemplateData[policy_name][temp_element_name] == \
                                                                _getAdmlDisplayName(
                                                                admlPolicyResources,
                                                                enum_item.attrib['displayName']).strip():
                                                            found = True
                                                            break
                                                    if not found:
                                                        msg = 'Element "{0}" does not have a valid value'
                                                        raise SaltInvocationError(msg.format(temp_element_name))
                                                elif etree.QName(child_item).localname == 'list':
                                                    if 'explicitValue' in child_item.attrib \
                                                                and child_item.attrib['explicitValue'].lower() == \
                                                                'true':
                                                        if not isinstance(
                                                                _admTemplateData[policy_name][temp_element_name],
                                                                dict):
                                                            msg = ('Each list item of element "{0}" '
                                                                   'requires a dict value')
                                                            msg = msg.format(temp_element_name)
                                                            raise SaltInvocationError(msg)
                                                    elif not isinstance(
                                                            _admTemplateData[policy_name][temp_element_name],
                                                            list):
                                                        msg = 'Element "{0}" requires a list value'
                                                        msg = msg.format(temp_element_name)
                                                        raise SaltInvocationError(msg)
                                                elif etree.QName(child_item).localname == 'multiText':
                                                    if not isinstance(
                                                            _admTemplateData[policy_name][temp_element_name],
                                                            list):
                                                        msg = 'Element "{0}" requires a list value'
                                                        msg = msg.format(temp_element_name)
                                                        raise SaltInvocationError(msg)
                                                _admTemplateData[policy_name][child_item.attrib['id']] = \
                                                    _admTemplateData[policy_name].pop(temp_element_name)
                                    else:
                                        msg = 'The policy "{0}" has elements which must be configured'
                                        msg = msg.format(policy_name)
                                        raise SaltInvocationError(msg)
                                else:
                                    if str(_admTemplateData[policy_name]).lower() != 'enabled':
                                        msg = ('The policy {0} must either be "Enabled", '
                                               '"Disabled", or "Not Configured"')
                                        msg = msg.format(policy_name)
                                        raise SaltInvocationError(msg)
                if _regedits:
                    for regedit in _regedits.keys():
                        log.debug('{0} is a Registry policy'.format(regedit))
                        _ret = __salt__['reg.set_value'](
                                _regedits[regedit]['policy']['Registry']['Hive'],
                                _regedits[regedit]['policy']['Registry']['Path'],
                                _regedits[regedit]['policy']['Registry']['Value'],
                                _regedits[regedit]['value'],
                                _regedits[regedit]['policy']['Registry']['Type'])
                        if not _ret:
                            msg = ('Error while attempting to set policy {0} via the registry.'
                                   '  Some changes may not be applied as expected')
                            raise CommandExecutionError(msg.format(regedit))
                if _lsarights:
                    for lsaright in _lsarights.keys():
                        _existingUsers = None
                        if not cumulative_rights_assignments:
                            _existingUsers = _getRightsAssignments(
                                    _lsarights[lsaright]['policy']['LsaRights']['Option'])
                        if _lsarights[lsaright]['value']:
                            for acct in _lsarights[lsaright]['value']:
                                _ret = _addAccountRights(acct, _lsarights[lsaright]['policy']['LsaRights']['Option'])
                                if not _ret:
                                    msg = 'An error occurred attempting to configure the user right {0}.'
                                    raise SaltInvocationError(msg.format(lsaright))
                        if _existingUsers:
                            for acct in _existingUsers:
                                if acct not in _lsarights[lsaright]['value']:
                                    _ret = _delAccountRights(
                                            acct, _lsarights[lsaright]['policy']['LsaRights']['Option'])
                                    if not _ret:
                                        msg = ('An error occurred attempting to remove previously'
                                               'configured users with right {0}.')
                                        raise SaltInvocationError(msg.format(lsaright))
                if _secedits:
                    # we've got secedits to make
                    log.debug(_secedits)
                    _iniData = '\r\n'.join(['[Unicode]', 'Unicode=yes'])
                    _seceditSections = ['System Access', 'Event Audit', 'Registry Values', 'Privilege Rights']
                    for _seceditSection in _seceditSections:
                        if _seceditSection in _secedits:
                            _iniData = '\r\n'.join([_iniData, ''.join(['[', _seceditSection, ']']),
                                                   '\r\n'.join(_secedits[_seceditSection])])
                    _iniData = '\r\n'.join([_iniData, '[Version]', 'signature="$CHICAGO$"', 'Revision=1'])
                    log.debug('_iniData == {0}'.format(_iniData))
                    _ret = _importSeceditConfig(_iniData)
                    if not _ret:
                        msg = ('Error while attempting to set policies via secedit.'
                               '  Some changes may not be applied as expected')
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
                    _ret = False
                    log.debug('going to write some adm template data :: {0}'.format(_admTemplateData))
                    _ret = _writeAdminTemplateRegPolFile(_admTemplateData,
                                                         admxPolicyDefinitions,
                                                         admlPolicyResources,
                                                         registry_class=p_class)
                    if not _ret:
                        msg = ('Error while attempting to write Administrative Template Policy data.'
                               '  Some changes may not be applied as expected')
                        raise CommandExecutionError(msg)
        return True
    else:
        msg = 'You have to specify something!'
        raise SaltInvocationError(msg)
