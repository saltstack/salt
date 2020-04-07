# -*- coding: utf-8 -*-
"""
Manage Local Policy on Windows

This module allows configuring local group policy (i.e. ``gpedit.msc``) on a
Windows server.

.. versionadded:: 2016.11.0

Administrative Templates
========================

Administrative template policies are dynamically read from ADMX/ADML files on
the server.

Windows Settings
================

Policies contained in the "Windows Settings" section of the ``gpedit.msc`` GUI
are statically defined in this module. Each policy is configured for the section
(Machine/User) in the module's _policy_info class. The ``_policy_info`` class
contains a "policies" dict on how the module will configure the policy, where
the policy resides in the GUI (for display purposes), data validation data, data
transformation data, etc.

Current known limitations
=========================

- At this time, start/shutdown scripts policies are displayed, but are not
  configurable.
- Not all "Security Settings" policies exist in the _policy_info class

:depends:
  - pywin32 Python module
  - lxml
  - uuid
  - struct
  - salt.utils.win_reg
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import csv
import ctypes
import glob
import io
import locale
import logging
import os
import re
import tempfile
import time
import uuid
import zlib

import salt.utils.dictupdate as dictupdate
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.win_lgpo_netsh

# Import Salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range
from salt.serializers.configparser import deserialize

log = logging.getLogger(__name__)

__virtualname__ = "lgpo"
__func_alias__ = {"set_": "set"}

UUID = uuid.uuid4().hex
adm_policy_name_map = {True: {}, False: {}}
HAS_WINDOWS_MODULES = False
# define some global XPATH variables that we'll set assuming all our imports are
# good
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
    import lxml
    import struct
    from lxml import etree
    from salt.utils.win_reg import Registry

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
    REGKEY_XPATH = etree.XPath("//*[@key = $keyvalue]")
    POLICY_ANCESTOR_XPATH = etree.XPath('ancestor::*[local-name() = "policy"]')
    ALL_CLASS_POLICY_XPATH = etree.XPath(
        '//*[local-name() = "policy" and (@*[local-name() = "class"] = "Both" or @*[local-name() = "class"] = $registry_class)]'
    )
    ADML_DISPLAY_NAME_XPATH = etree.XPath(
        '//*[local-name() = $displayNameType and @*[local-name() = "id"] = $displayNameId]'
    )
    VALUE_LIST_XPATH = etree.XPath('.//*[local-name() = "valueList"]')
    ENUM_ITEM_DISPLAY_NAME_XPATH = etree.XPath(
        './/*[local-name() = "item" and @*[local-name() = "displayName" = $display_name]]'
    )
    ADMX_SEARCH_XPATH = etree.XPath(
        '//*[local-name() = "policy" and @*[local-name() = "name"] = $policy_name and (@*[local-name() = "class"] = "Both" or @*[local-name() = "class"] = $registry_class)]'
    )
    ADML_SEARCH_XPATH = etree.XPath(
        '//*[starts-with(text(), $policy_name) and @*[local-name() = "id"]]'
    )
    ADMX_DISPLAYNAME_SEARCH_XPATH = etree.XPath(
        '//*[local-name() = "policy" and @*[local-name() = "displayName"] = $display_name and (@*[local-name() = "class"] = "Both" or @*[local-name() = "class"] = $registry_class) ]'
    )
    PRESENTATION_ANCESTOR_XPATH = etree.XPath(
        'ancestor::*[local-name() = "presentation"]'
    )
    TEXT_ELEMENT_XPATH = etree.XPath('.//*[local-name() = "text"]')
    # Get the System Install Language
    # https://msdn.microsoft.com/en-us/library/dd318123(VS.85).aspx
    # local.windows_locale is a dict
    # GetSystemDefaultUILanguage() returns a 4 digit language code that
    # corresponds to an entry in the dict
    # Not available in win32api, so we have to use ctypes
    # Default to `en-US` (1033)
    windll = ctypes.windll.kernel32
    INSTALL_LANGUAGE = locale.windows_locale.get(
        windll.GetSystemDefaultUILanguage(), "en_US"
    ).replace("_", "-")
except ImportError:
    HAS_WINDOWS_MODULES = False


class _policy_info(object):
    r"""
    Policy Helper Class
    ===================

    The format of the policy dict is as follows:

    The top most two key/value pairs in the dict divide the policies object into
    the two sections of local group policy, using the keys "Machine" and "User".
    The value make-up of these dicts are described below in "Policy Section
    Definition"

    Policy Section Definition
    -------------------------

    A policy section dict has two required key/value pairs:

    ============  ==============================================================
    Key
    ============  ==============================================================
    lgpo_section  String matching how the policy section is displayed in the mmc
                  snap-in ("Computer Configuration" for "Machine" and "User
                  Configuration" for "User")
    policies      a dict containing the non-Administrative template policy
                  definitions, the key for each item is a short/unique
                  identifier for the policy, the value is described below in
                  "Policies Definition"
    ============  ==============================================================

    Policies Definition
    -------------------

    A policies definition item describes the particular policy. There are three
    child key/value pairs shared with all policy types:

    ============  ==============================================================
    Key           Value
    ============  ==============================================================
    lgpo_section  A list containing the hierarchical path to the policy in the
                  gpedit mmc snap-in.
    Policy        A string containing the name of the policy in the gpedit mmc
                  snap-in
    Settings      An object which describes valid settings for the policy. This
                  can be None for no validation, a list of possible settings, or
                  a dict with the following key/value pairs:

                  - **Function:** The class function to use to validate the
                    setting
                  - **Args:** A dict of kwargs to pass to the class function
    ============  ==============================================================

    Additionally, each policies definition will contain a key/value pair that
    defines the mechanism that will be used to configure the policy. The
    available mechanisms are:  NetUserModal, Registry, Secedit, and LsaRights

    Registry Mechanism
    ------------------

    Some policies simply set values in the Windows registry. The value of this
    key is a dict with the following make-up:

    =====  =====================================================================
    Key    Value
    =====  =====================================================================
    Hive   A string containing the Registry hive, such as ``HKEY_LOCAL_MACHINE``
    Path   A string containing the registry key path, such as
           ``SYSTEM\\CurrentControlSet\\Control\\Lsa``
    Value  A string containing the name of the registry value, such as
           **restrictanonymous**
    Type   A string containing the registry type of the value, such as
           ``REG_DWORD``
    =====  =====================================================================

    Secedit Mechanism
    -----------------

    Some policies are configurable via the "secedit.exe" executable. The value
    of this key is a dict with the following make-up:

    =======  ===================================================================
    Key      Value
    =======  ===================================================================
    Option   A string containing the name of the policy as it appears in an
             export from secedit, such as **PasswordComplexity**
    Section  A string containing the name of the section in which the "Option"
             value appears in an export from ``secedit``, such as "System
             Access"
    =======  ===================================================================

    LsaRights Mechanism
    -------------------

    LSA Rights policies are configured via the LsaRights mechanism. The value of
    this key is a dict with the following make-up:

    ======  ====================================================================
    Key     Value
    ======  ====================================================================
    Option  A string containing the programmatic name of the Lsa Right, such as
            **SeNetworkLogonRight**
    ======  ====================================================================

    NetUserModal Mechanism
    ----------------------

    Some policies are configurable by the **NetUserModalGet** and
    **NetUserModalSet** function from pywin32.  The value of this key is a dict
    with the following make-up:

    ======  ====================================================================
    Key     Value
    ======  ====================================================================
    Modal   The modal "level" that the particular option is specified in (0-3),
            see `here <https://msdn.microsoft.com/en-us/library/windows/desktop/
            aa370656(v=vs.85).aspx>`_
    Option  The name of the structure member which contains the data for the
            policy, for example **max_passwd_age**
    ======  ====================================================================

    NetSH Mechanism
    ---------------

    The firewall policies are configured by the ``netsh.exe`` executable. The
    value of this key is a dict with the following make-up:

    =======  ===================================================================
    Key      Value
    =======  ===================================================================
    Profile  The firewall profile to modify. Can be one of Domain, Private, or
             Public
    Section  The section of the firewall to modify. Can be one of state,
             firewallpolicy, settings, or logging.
    Option   The setting within that section
    Value    The value of the setting
    =======  ===================================================================

    More information can be found in the advfirewall context in netsh. This can
    be access by opening a netsh prompt. At a command prompt type the following:

    c:\>netsh
    netsh>advfirewall
    netsh advfirewall>set help
    netsh advfirewall>set domain help

    AdvAudit Mechanism
    ------------------

    The Advanced Audit Policies are configured using a combination of the
    auditpol command-line utility and modifying the audit.csv file in two
    locations. The value of this key is a dict with the following make-up:

    ======  ===================================
    Key     Value
    ======  ===================================
    Option  The Advanced Audit Policy to modify
    ======  ===================================

    Transforms
    ----------

    Optionally, each policy definition can contain a "Transform" key. The
    Transform key is used to handle data that is stored and viewed differently.
    This key's value is a dict with the following key/value pairs:

    ===  =======================================================================
    Key  Value
    ===  =======================================================================
    Get  The name of the class function to use to transform the data from the
         stored value to how the value is displayed in the GUI
    Put The name of the class function to use to transform the data supplied by
        the user to the correct value that the policy is stored in
    ===  =======================================================================

    For example, "Minimum password age" is stored in seconds, but is displayed
    in days.  Thus the "Get" and "Put" functions for this policy do these
    conversions so the user is able to set and view the policy using the same
    data that is shown in the GUI.
    """

    def __init__(self):
        self.audit_lookup = {
            0: "No auditing",
            1: "Success",
            2: "Failure",
            3: "Success, Failure",
            "Not Defined": "Not Defined",
            None: "Not Defined",
        }
        self.advanced_audit_lookup = {
            0: "No Auditing",
            1: "Success",
            2: "Failure",
            3: "Success and Failure",
            None: "Not Configured",
        }
        self.sc_removal_lookup = {
            0: "No Action",
            1: "Lock Workstation",
            2: "Force Logoff",
            3: "Disconnect if a Remote Desktop Services session",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.uac_admin_prompt_lookup = {
            0: "Elevate without prompting",
            1: "Prompt for credentials on the secure desktop",
            2: "Prompt for consent on the secure desktop",
            3: "Prompt for credentials",
            4: "Prompt for consent",
            5: "Prompt for consent for non-Windows binaries",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.uac_user_prompt_lookup = {
            0: "Automatically deny elevation requests",
            1: "Prompt for credentials on the secure desktop",
            3: "Prompt for credentials",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.enabled_one_disabled_zero = {
            0: "Disabled",
            1: "Enabled",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.enabled_one_disabled_zero_transform = {
            "Get": "_dict_lookup",
            "Put": "_dict_lookup",
            "GetArgs": {
                "lookup": self.enabled_one_disabled_zero,
                "value_lookup": False,
            },
            "PutArgs": {
                "lookup": self.enabled_one_disabled_zero,
                "value_lookup": True,
            },
        }
        self.s4u2self_options = {
            0: "Default",
            1: "Enabled",
            2: "Disabled",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.audit_transform = {
            "Get": "_dict_lookup",
            "Put": "_dict_lookup",
            "GetArgs": {"lookup": self.audit_lookup, "value_lookup": False},
            "PutArgs": {"lookup": self.audit_lookup, "value_lookup": True},
        }
        self.advanced_audit_transform = {
            "Get": "_dict_lookup",
            "Put": "_dict_lookup",
            "GetArgs": {"lookup": self.advanced_audit_lookup, "value_lookup": False},
            "PutArgs": {"lookup": self.advanced_audit_lookup, "value_lookup": True},
        }
        self.enabled_one_disabled_zero_strings = {
            "0": "Disabled",
            "1": "Enabled",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.enabled_one_disabled_zero_strings_transform = {
            "Get": "_dict_lookup",
            "Put": "_dict_lookup",
            "GetArgs": {
                "lookup": self.enabled_one_disabled_zero_strings,
                "value_lookup": False,
            },
            "PutArgs": {
                "lookup": self.enabled_one_disabled_zero_strings,
                "value_lookup": True,
            },
        }
        self.security_options_gpedit_path = [
            "Computer Configuration",
            "Windows Settings",
            "Security Settings",
            "Local Policies",
            "Security Options",
        ]
        self.windows_firewall_gpedit_path = [
            "Computer Configuration",
            "Windows Settings",
            "Security Settings",
            "Windows Firewall with Advanced Security",
            "Windows Firewall with Advanced Security - Local Group Policy Object",
        ]
        self.password_policy_gpedit_path = [
            "Computer Configuration",
            "Windows Settings",
            "Security Settings",
            "Account Policies",
            "Password Policy",
        ]
        self.audit_policy_gpedit_path = [
            "Computer Configuration",
            "Windows Settings",
            "Security Settings",
            "Local Policies",
            "Audit Policy",
        ]
        self.advanced_audit_policy_gpedit_path = [
            "Computer Configuration",
            "Windows Settings",
            "Security Settings",
            "Advanced Audit Policy Configuration",
            "System Audit Policies - Local Group Policy Object",
        ]
        self.account_lockout_policy_gpedit_path = [
            "Computer Configuration",
            "Windows Settings",
            "Security Settings",
            "Account Policies",
            "Account Lockout Policy",
        ]
        self.user_rights_assignment_gpedit_path = [
            "Computer Configuration",
            "Windows Settings",
            "Security Settings",
            "Local Policies",
            "User Rights Assignment",
        ]
        self.block_ms_accounts = {
            0: "This policy is disabled",
            1: "Users can't add Microsoft accounts",
            3: "Users can't add or log on with Microsoft accounts",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.ldap_server_signing_requirements = {
            1: "None",
            2: "Require signing",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.smb_server_name_hardening_levels = {
            0: "Off",
            1: "Accept if provided by client",
            2: "Required from client",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.locked_session_user_info = {
            1: "User display name, domain and user names",
            2: "User display name only",
            3: "Do not display user information",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.force_guest = {
            0: "Classic - local users authenticate as themselves",
            1: "Guest only - local users authenticate as Guest",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.force_key_protection = {
            0: "User input is not required when new keys are stored and used",
            1: "User is prompted when the key is first used",
            2: "User must enter a password each time they use a key",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.firewall_inbound_connections = {
            "blockinbound": "Block (default)",
            "blockinboundalways": "Block all connections",
            "allowinbound": "Allow",
            "notconfigured": "Not configured",
        }
        self.firewall_outbound_connections = {
            "blockoutbound": "Block",
            "allowoutbound": "Allow (default)",
            "notconfigured": "Not configured",
        }
        self.firewall_rule_merging = {
            "enable": "Yes (default)",
            "disable": "No",
            "notconfigured": "Not configured",
        }
        self.firewall_log_packets_connections = {
            "enable": "Yes",
            "disable": "No (default)",
            "notconfigured": "Not configured",
        }
        self.firewall_notification = {
            "enable": "Yes",
            "disable": "No",
            "notconfigured": "Not configured",
        }
        self.firewall_state = {
            "on": "On (recommended)",
            "off": "Off",
            "notconfigured": "Not configured",
        }
        self.krb_encryption_types = {
            0: "No minimum",
            1: "DES_CBC_CRC",
            2: "DES_CBD_MD5",
            4: "RC4_HMAC_MD5",
            8: "AES128_HMAC_SHA1",
            16: "AES256_HMAC_SHA1",
            2147483616: "Future Encryption Types",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.lm_compat_levels = {
            0: "Send LM & NTLM response",
            1: "Send LM & NTLM - use NTLMv2 session security if negotiated",
            2: "Send NTLM response only",
            3: "Send NTLMv2 response only",
            4: "Send NTLMv2 response only. Refuse LM",
            5: "Send NTLMv2 response only. Refuse LM & NTLM",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.ldap_signing_reqs = {
            0: "None",
            1: "Negotiate signing",
            2: "Require signing",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.ntlm_session_security_levels = {
            0: "No minimum",
            524288: "Require NTLMv2 session security",
            536870912: "Require 128-bit encryption",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.ntlm_audit_settings = {
            0: "Disable",
            1: "Enable auditing for domain accounts",
            2: "Enable auditing for all accounts",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.ntlm_domain_audit_settings = {
            0: "Disable",
            1: "Enable for domain accounts to domain servers",
            3: "Enable for domain accounts",
            5: "Enable for domain servers",
            7: "Enable all",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.incoming_ntlm_settings = {
            0: "Allow all",
            1: "Deny all domain accounts",
            2: "Deny all accounts",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.ntlm_domain_auth_settings = {
            0: "Disable",
            1: "Deny for domain accounts to domain servers",
            3: "Deny for domain accounts",
            5: "Deny for domain servers",
            7: "Deny all",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.outgoing_ntlm_settings = {
            0: "Allow all",
            1: "Audit all",
            2: "Deny all",
            None: "Not Defined",
            "(value not set)": "Not Defined",
        }
        self.enabled_one_disabled_zero_no_not_defined = {
            0: "Disabled",
            1: "Enabled",
        }
        self.enabled_one_disabled_zero_no_not_defined_transform = {
            "Get": "_dict_lookup",
            "Put": "_dict_lookup",
            "GetArgs": {
                "lookup": self.enabled_one_disabled_zero_no_not_defined,
                "value_lookup": False,
            },
            "PutArgs": {
                "lookup": self.enabled_one_disabled_zero_no_not_defined,
                "value_lookup": True,
            },
        }
        self.policies = {
            "Machine": {
                "lgpo_section": "Computer Configuration",
                "policies": {
                    "StartupScripts": {
                        "Policy": "Startup Scripts",
                        "lgpo_section": [
                            "Computer Configuration",
                            "Windows Settings",
                            "Scripts (Startup/Shutdown)",
                            "Startup",
                        ],
                        "ScriptIni": {
                            "Section": "Startup",
                            "IniPath": os.path.join(
                                os.getenv("WINDIR"),
                                "System32",
                                "GroupPolicy",
                                "Machine",
                                "Scripts",
                                "scripts.ini",
                            ),
                        },
                    },
                    "StartupPowershellScripts": {
                        "Policy": "Startup Powershell Scripts",
                        "lgpo_section": [
                            "Computer Configuration",
                            "Windows Settings",
                            "Scripts (Startup/Shutdown)",
                            "Startup",
                        ],
                        "ScriptIni": {
                            "Section": "Startup",
                            "IniPath": os.path.join(
                                os.getenv("WINDIR"),
                                "System32",
                                "GroupPolicy",
                                "Machine",
                                "Scripts",
                                "psscripts.ini",
                            ),
                        },
                    },
                    "StartupPowershellScriptOrder": {
                        "Policy": "Startup - For this GPO, run scripts in the "
                        "following order",
                        "lgpo_section": [
                            "Computer Configuration",
                            "Windows Settings",
                            "Scripts (Startup/Shutdown)",
                            "Startup",
                        ],
                        "ScriptIni": {
                            "IniPath": os.path.join(
                                os.getenv("WINDIR"),
                                "System32",
                                "GroupPolicy",
                                "Machine",
                                "Scripts",
                                "psscripts.ini",
                            ),
                            "Section": "ScriptsConfig",
                            "SettingName": "StartExecutePSFirst",
                            "Settings": ["true", "false", None],
                        },
                        "Transform": {
                            "Get": "_powershell_script_order_conversion",
                            "Put": "_powershell_script_order_reverse_conversion",
                        },
                    },
                    "ShutdownScripts": {
                        "Policy": "Shutdown Scripts",
                        "lgpo_section": [
                            "Computer Configuration",
                            "Windows Settings",
                            "Scripts (Startup/Shutdown)",
                            "Shutdown",
                        ],
                        "ScriptIni": {
                            "Section": "Shutdown",
                            "IniPath": os.path.join(
                                os.getenv("WINDIR"),
                                "System32",
                                "GroupPolicy",
                                "Machine",
                                "Scripts",
                                "scripts.ini",
                            ),
                        },
                    },
                    "ShutdownPowershellScripts": {
                        "Policy": "Shutdown Powershell Scripts",
                        "lgpo_section": [
                            "Computer Configuration",
                            "Windows Settings",
                            "Scripts (Startup/Shutdown)",
                            "Shutdown",
                        ],
                        "ScriptIni": {
                            "Section": "Shutdown",
                            "IniPath": os.path.join(
                                os.getenv("WINDIR"),
                                "System32",
                                "GroupPolicy",
                                "Machine",
                                "Scripts",
                                "psscripts.ini",
                            ),
                        },
                    },
                    "ShutdownPowershellScriptOrder": {
                        "Policy": "Shutdown - For this GPO, run scripts in the "
                        "following order",
                        "lgpo_section": [
                            "Computer Configuration",
                            "Windows Settings",
                            "Scripts (Startup/Shutdown)",
                            "Shutdown",
                        ],
                        "ScriptIni": {
                            "IniPath": os.path.join(
                                os.getenv("WINDIR"),
                                "System32",
                                "GroupPolicy",
                                "Machine",
                                "Scripts",
                                "psscripts.ini",
                            ),
                            "Section": "ScriptsConfig",
                            "SettingName": "EndExecutePSFirst",
                            "Settings": ["true", "false", None],
                        },
                        "Transform": {
                            "Get": "_powershell_script_order_conversion",
                            "Put": "_powershell_script_order_reverse_conversion",
                        },
                    },
                    "LSAAnonymousNameLookup": {
                        "Policy": "Network access: Allow anonymous SID/Name "
                        "translation",
                        "lgpo_section": self.password_policy_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero_no_not_defined.keys(),
                        "Secedit": {
                            "Option": "LSAAnonymousNameLookup",
                            "Section": "System Access",
                        },
                        "Transform": self.enabled_one_disabled_zero_no_not_defined_transform,
                    },
                    "RestrictAnonymousSam": {
                        "Policy": "Network access: Do not allow anonymous "
                        "enumeration of SAM accounts",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "RestrictAnonymousSam",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "RestrictRemoteSAM": {
                        "Policy": "Network access: Restrict clients allowed to "
                        "make remote calls to SAM",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\Lsa",
                            "Value": "RestrictRemoteSAM",
                            "Type": "REG_SZ",
                        },
                        "Transform": {"Put": "_string_put_transform"},
                    },
                    "RestrictAnonymous": {
                        "Policy": "Network access: Do not allow anonymous "
                        "enumeration of SAM accounts and shares",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "RestrictAnonymous",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "DisableDomainCreds": {
                        "Policy": "Network access: Do not allow storage of "
                        "passwords and credentials for network "
                        "authentication",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "DisableDomainCreds",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "EveryoneIncludesAnonymous": {
                        "Policy": "Network access: Let Everyone permissions "
                        "apply to anonymous users",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "everyoneincludesanonymous",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "NullSessionPipes": {
                        "Policy": "Network access: Named Pipes that can be "
                        "accessed anonymously",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\"
                            "LanmanServer\\Parameters",
                            "Value": "NullSessionPipes",
                            "Type": "REG_MULTI_SZ",
                        },
                        "Transform": {
                            "Put": "_multi_string_put_transform",
                            "Get": "_multi_string_get_transform",
                        },
                    },
                    "RemoteRegistryExactPaths": {
                        "Policy": "Network access: Remotely accessible "
                        "registry paths",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\"
                            "SecurePipeServers\\winreg\\"
                            "AllowedExactPaths",
                            "Value": "Machine",
                            "Type": "REG_MULTI_SZ",
                        },
                        "Transform": {
                            "Put": "_multi_string_put_transform",
                            "Get": "_multi_string_get_transform",
                        },
                    },
                    "RemoteRegistryPaths": {
                        "Policy": "Network access: Remotely accessible "
                        "registry paths and sub-paths",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\"
                            "SecurePipeServers\\winreg\\AllowedPaths",
                            "Value": "Machine",
                            "Type": "REG_MULTI_SZ",
                        },
                        "Transform": {
                            "Put": "_multi_string_put_transform",
                            "Get": "_multi_string_get_transform",
                        },
                    },
                    "RestrictNullSessAccess": {
                        "Policy": "Network access: Restrict anonymous access "
                        "to Named Pipes and Shares",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "LanmanServer\\Parameters",
                            "Value": "RestrictNullSessAccess",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "NullSessionShares": {
                        "Policy": "Network access: Shares that can be accessed "
                        "anonymously",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\"
                            "LanmanServer\\Parameters",
                            "Value": "NullSessionShares",
                            "Type": "REG_MULTI_SZ",
                        },
                        "Transform": {
                            "Put": "_multi_string_put_transform",
                            "Get": "_multi_string_get_transform",
                        },
                    },
                    "ForceGuest": {
                        "Policy": "Network access: Sharing and security model "
                        "for local accounts",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Settings": self.force_guest.keys(),
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "ForceGuest",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.force_guest,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.force_guest,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwDomainState": {
                        "Policy": "Network firewall: Domain: State",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - On (recommended)
                        # - Off
                        # - Not configured
                        "Settings": self.firewall_state.keys(),
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "state",
                            "Option": "State",  # Unused, but needed
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_state,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_state,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPrivateState": {
                        "Policy": "Network firewall: Private: State",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - On (recommended)
                        # - Off
                        # - Not configured
                        "Settings": self.firewall_state.keys(),
                        "NetSH": {
                            "Profile": "private",
                            "Section": "state",
                            "Option": "State",  # Unused, but needed
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_state,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_state,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPublicState": {
                        "Policy": "Network firewall: Public: State",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - On (recommended)
                        # - Off
                        # - Not configured
                        "Settings": self.firewall_state.keys(),
                        "NetSH": {
                            "Profile": "public",
                            "Section": "state",
                            "Option": "State",  # Unused, but needed
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_state,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_state,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwDomainInboundConnections": {
                        "Policy": "Network firewall: Domain: Inbound connections",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Block (default)
                        # - Block all connections
                        # - Allow
                        # - Not configured
                        "Settings": self.firewall_inbound_connections.keys(),
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "firewallpolicy",
                            "Option": "Inbound",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_inbound_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_inbound_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPrivateInboundConnections": {
                        "Policy": "Network firewall: Private: Inbound connections",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Block (default)
                        # - Block all connections
                        # - Allow
                        # - Not configured
                        "Settings": self.firewall_inbound_connections.keys(),
                        "NetSH": {
                            "Profile": "private",
                            "Section": "firewallpolicy",
                            "Option": "Inbound",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_inbound_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_inbound_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPublicInboundConnections": {
                        "Policy": "Network firewall: Public: Inbound connections",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Block (default)
                        # - Block all connections
                        # - Allow
                        # - Not configured
                        "Settings": self.firewall_inbound_connections.keys(),
                        "NetSH": {
                            "Profile": "public",
                            "Section": "firewallpolicy",
                            "Option": "Inbound",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_inbound_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_inbound_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwDomainOutboundConnections": {
                        "Policy": "Network firewall: Domain: Outbound connections",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Block
                        # - Allow (default)
                        # - Not configured
                        "Settings": self.firewall_outbound_connections.keys(),
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "firewallpolicy",
                            "Option": "Outbound",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_outbound_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_outbound_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPrivateOutboundConnections": {
                        "Policy": "Network firewall: Private: Outbound connections",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Block
                        # - Allow (default)
                        # - Not configured
                        "Settings": self.firewall_outbound_connections.keys(),
                        "NetSH": {
                            "Profile": "private",
                            "Section": "firewallpolicy",
                            "Option": "Outbound",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_outbound_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_outbound_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPublicOutboundConnections": {
                        "Policy": "Network firewall: Public: Outbound connections",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Block
                        # - Allow (default)
                        # - Not configured
                        "Settings": self.firewall_outbound_connections.keys(),
                        "NetSH": {
                            "Profile": "public",
                            "Section": "firewallpolicy",
                            "Option": "Outbound",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_outbound_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_outbound_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwDomainSettingsNotification": {
                        "Policy": "Network firewall: Domain: Settings: Display a notification",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes
                        # - No
                        # - Not configured
                        "Settings": self.firewall_notification.keys(),
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "settings",
                            "Option": "InboundUserNotification",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_notification,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_notification,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPrivateSettingsNotification": {
                        "Policy": "Network firewall: Private: Settings: Display a notification",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes
                        # - No
                        # - Not configured
                        "Settings": self.firewall_notification.keys(),
                        "NetSH": {
                            "Profile": "private",
                            "Section": "settings",
                            "Option": "InboundUserNotification",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_notification,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_notification,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPublicSettingsNotification": {
                        "Policy": "Network firewall: Public: Settings: Display a notification",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes
                        # - No
                        # - Not configured
                        "Settings": self.firewall_notification.keys(),
                        "NetSH": {
                            "Profile": "public",
                            "Section": "settings",
                            "Option": "InboundUserNotification",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_notification,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_notification,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwDomainSettingsLocalFirewallRules": {
                        "Policy": "Network firewall: Domain: Settings: Apply "
                        "local firewall rules",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes (default)
                        # - No
                        # - Not configured
                        "Settings": self.firewall_rule_merging.keys(),
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "settings",
                            "Option": "LocalFirewallRules",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPrivateSettingsLocalFirewallRules": {
                        "Policy": "Network firewall: Private: Settings: Apply "
                        "local firewall rules",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes (default)
                        # - No
                        # - Not configured
                        "Settings": self.firewall_rule_merging.keys(),
                        "NetSH": {
                            "Profile": "private",
                            "Section": "settings",
                            "Option": "LocalFirewallRules",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPublicSettingsLocalFirewallRules": {
                        "Policy": "Network firewall: Public: Settings: Apply "
                        "local firewall rules",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes (default)
                        # - No
                        # - Not configured
                        "Settings": self.firewall_rule_merging.keys(),
                        "NetSH": {
                            "Profile": "public",
                            "Section": "settings",
                            "Option": "LocalFirewallRules",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwDomainSettingsLocalConnectionRules": {
                        "Policy": "Network firewall: Domain: Settings: Apply "
                        "local connection security rules",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes (default)
                        # - No
                        # - Not configured
                        "Settings": self.firewall_rule_merging.keys(),
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "settings",
                            "Option": "LocalConSecRules",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPrivateSettingsLocalConnectionRules": {
                        "Policy": "Network firewall: Private: Settings: Apply "
                        "local connection security rules",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes (default)
                        # - No
                        # - Not configured
                        "Settings": self.firewall_rule_merging.keys(),
                        "NetSH": {
                            "Profile": "private",
                            "Section": "settings",
                            "Option": "LocalConSecRules",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPublicSettingsLocalConnectionRules": {
                        "Policy": "Network firewall: Public: Settings: Apply "
                        "local connection security rules",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes (default)
                        # - No
                        # - Not configured
                        "Settings": self.firewall_rule_merging.keys(),
                        "NetSH": {
                            "Profile": "public",
                            "Section": "settings",
                            "Option": "LocalConSecRules",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_rule_merging,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwDomainLoggingName": {
                        "Policy": "Network firewall: Domain: Logging: Name",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - <a full path to a file>
                        # - Not configured
                        "Settings": None,
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "logging",
                            "Option": "FileName",
                        },
                    },
                    "WfwPrivateLoggingName": {
                        "Policy": "Network firewall: Private: Logging: Name",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - <a full path to a file>
                        # - Not configured
                        "Settings": None,
                        "NetSH": {
                            "Profile": "private",
                            "Section": "logging",
                            "Option": "FileName",
                        },
                    },
                    "WfwPublicLoggingName": {
                        "Policy": "Network firewall: Public: Logging: Name",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - <a full path to a file>
                        # - Not configured
                        "Settings": None,
                        "NetSH": {
                            "Profile": "public",
                            "Section": "logging",
                            "Option": "FileName",
                        },
                    },
                    "WfwDomainLoggingMaxFileSize": {
                        "Policy": "Network firewall: Domain: Logging: Size limit (KB)",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - <int between 1 and 32767>
                        # - Not configured
                        "Settings": None,
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "logging",
                            "Option": "MaxFileSize",
                        },
                    },
                    "WfwPrivateLoggingMaxFileSize": {
                        "Policy": "Network firewall: Private: Logging: Size limit (KB)",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - <int between 1 and 32767>
                        # - Not configured
                        "Settings": None,
                        "NetSH": {
                            "Profile": "private",
                            "Section": "logging",
                            "Option": "MaxFileSize",
                        },
                    },
                    "WfwPublicLoggingMaxFileSize": {
                        "Policy": "Network firewall: Public: Logging: Size limit (KB)",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - <int between 1 and 32767>
                        # - Not configured
                        "Settings": None,
                        "NetSH": {
                            "Profile": "public",
                            "Section": "logging",
                            "Option": "MaxFileSize",
                        },
                    },
                    "WfwDomainLoggingAllowedConnections": {
                        "Policy": "Network firewall: Domain: Logging: Log successful connections",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes
                        # - No (default)
                        # - Not configured
                        "Settings": self.firewall_log_packets_connections.keys(),
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "logging",
                            "Option": "LogAllowedConnections",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPrivateLoggingAllowedConnections": {
                        "Policy": "Network firewall: Private: Logging: Log successful connections",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes
                        # - No (default)
                        # - Not configured
                        "Settings": self.firewall_log_packets_connections.keys(),
                        "NetSH": {
                            "Profile": "private",
                            "Section": "logging",
                            "Option": "LogAllowedConnections",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPublicLoggingAllowedConnections": {
                        "Policy": "Network firewall: Public: Logging: Log successful connections",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes
                        # - No (default)
                        # - Not configured
                        "Settings": self.firewall_log_packets_connections.keys(),
                        "NetSH": {
                            "Profile": "public",
                            "Section": "logging",
                            "Option": "LogAllowedConnections",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwDomainLoggingDroppedConnections": {
                        "Policy": "Network firewall: Domain: Logging: Log dropped packets",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes
                        # - No (default)
                        # - Not configured
                        "Settings": self.firewall_log_packets_connections.keys(),
                        "NetSH": {
                            "Profile": "domain",
                            "Section": "logging",
                            "Option": "LogDroppedConnections",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPrivateLoggingDroppedConnections": {
                        "Policy": "Network firewall: Private: Logging: Log dropped packets",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes
                        # - No (default)
                        # - Not configured
                        "Settings": self.firewall_log_packets_connections.keys(),
                        "NetSH": {
                            "Profile": "private",
                            "Section": "logging",
                            "Option": "LogDroppedConnections",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "WfwPublicLoggingDroppedConnections": {
                        "Policy": "Network firewall: Public: Logging: Log dropped packets",
                        "lgpo_section": self.windows_firewall_gpedit_path,
                        # Settings available are:
                        # - Yes
                        # - No (default)
                        # - Not configured
                        "Settings": self.firewall_log_packets_connections.keys(),
                        "NetSH": {
                            "Profile": "public",
                            "Section": "logging",
                            "Option": "LogDroppedConnections",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.firewall_log_packets_connections,
                                "value_lookup": True,
                            },
                        },
                    },
                    "PasswordHistory": {
                        "Policy": "Enforce password history",
                        "lgpo_section": self.password_policy_gpedit_path,
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 24},
                        },
                        "NetUserModal": {"Modal": 0, "Option": "password_hist_len"},
                    },
                    "MaxPasswordAge": {
                        "Policy": "Maximum password age",
                        "lgpo_section": self.password_policy_gpedit_path,
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {
                                "min": 1,
                                "max": 86313600,
                                "zero_value": 0xFFFFFFFF,
                            },
                        },
                        "NetUserModal": {"Modal": 0, "Option": "max_passwd_age"},
                        "Transform": {
                            "Get": "_seconds_to_days",
                            "Put": "_days_to_seconds",
                            "GetArgs": {"zero_value": 0xFFFFFFFF},
                            "PutArgs": {"zero_value": 0xFFFFFFFF},
                        },
                    },
                    "MinPasswordAge": {
                        "Policy": "Minimum password age",
                        "lgpo_section": self.password_policy_gpedit_path,
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 86313600},
                        },
                        "NetUserModal": {"Modal": 0, "Option": "min_passwd_age"},
                        "Transform": {
                            "Get": "_seconds_to_days",
                            "Put": "_days_to_seconds",
                        },
                    },
                    "MinPasswordLen": {
                        "Policy": "Minimum password length",
                        "lgpo_section": self.password_policy_gpedit_path,
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 14},
                        },
                        "NetUserModal": {"Modal": 0, "Option": "min_passwd_len"},
                    },
                    "PasswordComplexity": {
                        "Policy": "Password must meet complexity requirements",
                        "lgpo_section": self.password_policy_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero_no_not_defined.keys(),
                        "Secedit": {
                            "Option": "PasswordComplexity",
                            "Section": "System Access",
                        },
                        "Transform": self.enabled_one_disabled_zero_no_not_defined_transform,
                    },
                    "ClearTextPasswords": {
                        "Policy": "Store passwords using reversible encryption",
                        "lgpo_section": self.password_policy_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero_no_not_defined.keys(),
                        "Secedit": {
                            "Option": "ClearTextPassword",
                            "Section": "System Access",
                        },
                        "Transform": self.enabled_one_disabled_zero_no_not_defined_transform,
                    },
                    "AdminAccountStatus": {
                        "Policy": "Accounts: Administrator account status",
                        "Settings": self.enabled_one_disabled_zero_no_not_defined.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Secedit": {
                            "Option": "EnableAdminAccount",
                            "Section": "System Access",
                        },
                        "Transform": self.enabled_one_disabled_zero_no_not_defined_transform,
                    },
                    "NoConnectedUser": {
                        "Policy": "Accounts: Block Microsoft accounts",
                        "Settings": self.block_ms_accounts.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SOFTWARE\\Microsoft\\Windows\\"
                            "CurrentVersion\\policies\\system",
                            "Value": "NoConnectedUser",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.block_ms_accounts,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.block_ms_accounts,
                                "value_lookup": True,
                            },
                        },
                    },
                    "GuestAccountStatus": {
                        "Policy": "Accounts: Guest account status",
                        "Settings": self.enabled_one_disabled_zero_no_not_defined.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Secedit": {
                            "Option": "EnableGuestAccount",
                            "Section": "System Access",
                        },
                        "Transform": self.enabled_one_disabled_zero_no_not_defined_transform,
                    },
                    "LimitBlankPasswordUse": {
                        "Policy": "Accounts: Limit local account use of blank "
                        "passwords to console logon only",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "limitblankpassworduse",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "RenameAdministratorAccount": {
                        "Policy": "Accounts: Rename administrator account",
                        "Settings": None,
                        "lgpo_section": self.security_options_gpedit_path,
                        "Secedit": {
                            "Option": "NewAdministratorName",
                            "Section": "System Access",
                        },
                        "Transform": {"Get": "_strip_quotes", "Put": "_add_quotes"},
                    },
                    "RenameGuestAccount": {
                        "Policy": "Accounts: Rename guest account",
                        "Settings": None,
                        "lgpo_section": self.security_options_gpedit_path,
                        "Secedit": {
                            "Option": "NewGuestName",
                            "Section": "System Access",
                        },
                        "Transform": {"Get": "_strip_quotes", "Put": "_add_quotes"},
                    },
                    "AuditBaseObjects": {
                        "Policy": "Audit: Audit the access of global system " "objects",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "AuditBaseObjects",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "SceNoApplyLegacyAuditPolicy": {
                        "Policy": "Audit: Force audit policy subcategory "
                        "settings (Windows Vista or later) to "
                        "override audit policy category settings",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "AuditBaseObjects",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "DontDisplayLastUserName": {
                        "Policy": "Interactive logon: Do not display last user " "name",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "DontDisplayLastUserName",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "CachedLogonsCount": {
                        "Policy": "Interactive logon: Number of previous "
                        "logons to cache (in case domain controller "
                        "is not available)",
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 50},
                        },
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows NT\\"
                            "CurrentVersion\\Winlogon",
                            "Value": "CachedLogonsCount",
                            "Type": "REG_SZ",
                        },
                    },
                    "ForceUnlockLogon": {
                        "Policy": "Interactive logon: Require Domain "
                        "Controller authentication to unlock "
                        "workstation",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows NT\\"
                            "CurrentVersion\\Winlogon",
                            "Value": "ForceUnlockLogon",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "ScRemoveOption": {
                        "Policy": "Interactive logon: Smart card removal " "behavior",
                        "Settings": self.sc_removal_lookup.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows NT\\"
                            "CurrentVersion\\Winlogon",
                            "Value": "ScRemoveOption",
                            "Type": "REG_SZ",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.sc_removal_lookup,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.sc_removal_lookup,
                                "value_lookup": True,
                            },
                        },
                    },
                    "DisableCAD": {
                        "Policy": "Interactive logon: Do not require " "CTRL+ALT+DEL",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "DisableCAD",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "FilterAdministratorToken": {
                        "Policy": "User Account Control: Admin Approval Mode "
                        "for the built-in Administrator account",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "FilterAdministratorToken",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "EnableUIADesktopToggle": {
                        "Policy": "User Account Control: Allow UIAccess "
                        "applications to prompt for elevation "
                        "without using the secure desktop",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "EnableUIADesktopToggle",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "ConsentPromptBehaviorAdmin": {
                        "Policy": "User Account Control: Behavior of the "
                        "elevation prompt for administrators in "
                        "Admin Approval Mode",
                        "Settings": self.uac_admin_prompt_lookup.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "ConsentPromptBehaviorAdmin",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.uac_admin_prompt_lookup,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.uac_admin_prompt_lookup,
                                "value_lookup": True,
                            },
                        },
                    },
                    "ConsentPromptBehaviorUser": {
                        "Policy": "User Account Control: Behavior of the "
                        "elevation prompt for standard users",
                        "Settings": self.uac_user_prompt_lookup.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "ConsentPromptBehaviorUser",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.uac_user_prompt_lookup,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.uac_user_prompt_lookup,
                                "value_lookup": True,
                            },
                        },
                    },
                    "EnableInstallerDetection": {
                        "Policy": "User Account Control: Detect application "
                        "installations and prompt for elevation",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "EnableInstallerDetection",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "ValidateAdminCodeSignatures": {
                        "Policy": "User Account Control: Only elevate "
                        "executables that are signed and validated",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "ValidateAdminCodeSignatures",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "EnableSecureUIAPaths": {
                        "Policy": "User Account Control: Only elevate UIAccess "
                        "applications that are installed in secure "
                        "locations",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "EnableSecureUIAPaths",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "EnableLUA": {
                        "Policy": "User Account Control: Run all "
                        "administrators in Admin Approval Mode",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "EnableLUA",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "PromptOnSecureDesktop": {
                        "Policy": "User Account Control: Switch to the secure "
                        "desktop when prompting for elevation",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "PromptOnSecureDesktop",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "EnableVirtualization": {
                        "Policy": "User Account Control: Virtualize file and "
                        "registry write failures to per-user "
                        "locations",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "EnableVirtualization",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "PasswordExpiryWarning": {
                        "Policy": "Interactive logon: Prompt user to change "
                        "password before expiration",
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 999},
                        },
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows NT\\"
                            "CurrentVersion\\Winlogon",
                            "Value": "PasswordExpiryWarning",
                            "Type": "REG_DWORD",
                        },
                    },
                    "MaxDevicePasswordFailedAttempts": {
                        "Policy": "Interactive logon: Machine account lockout "
                        "threshold",
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 999},
                        },
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SOFTWARE\\Microsoft\\Windows\\"
                            "CurrentVersion\\policies\\system",
                            "Value": "MaxDevicePasswordFailedAttempts",
                            "Type": "REG_DWORD",
                        },
                    },
                    "InactivityTimeoutSecs": {
                        "Policy": "Interactive logon: Machine inactivity limit",
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 599940},
                        },
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SOFTWARE\\Microsoft\\Windows\\"
                            "CurrentVersion\\policies\\system",
                            "Value": "InactivityTimeoutSecs",
                            "Type": "REG_DWORD",
                        },
                    },
                    "legalnoticetext": {
                        "Policy": "Interactive logon: Message text for users "
                        "attempting to log on",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SOFTWARE\\Microsoft\\Windows\\"
                            "CurrentVersion\\policies\\system",
                            "Value": "legalnoticetext",
                            "Type": "REG_SZ",
                        },
                        "Transform": {"Put": "_string_put_transform"},
                    },
                    "legalnoticecaption": {
                        "Policy": "Interactive logon: Message title for users "
                        "attempting to log on",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SOFTWARE\\Microsoft\\Windows\\"
                            "CurrentVersion\\policies\\system",
                            "Value": "legalnoticecaption",
                            "Type": "REG_SZ",
                        },
                        "Transform": {"Put": "_string_put_transform"},
                    },
                    "DontDisplayLockedUserId": {
                        "Policy": "Interactive logon: Display user information "
                        "when the session is locked",
                        "Settings": self.locked_session_user_info.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SOFTWARE\\Microsoft\\Windows\\"
                            "CurrentVersion\\policies\\system",
                            "Value": "DontDisplayLockedUserId",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.locked_session_user_info,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.locked_session_user_info,
                                "value_lookup": True,
                            },
                        },
                    },
                    "ScForceOption": {
                        "Policy": "Interactive logon: Require smart card",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "ScForceOption",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "Client_RequireSecuritySignature": {
                        "Policy": "Microsoft network client: Digitally sign "
                        "communications (always)",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\"
                            "LanmanWorkstation\\Parameters",
                            "Value": "RequireSecuritySignature",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "Client_EnableSecuritySignature": {
                        "Policy": "Microsoft network client: Digitally sign "
                        "communications (if server agrees)",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\"
                            "LanmanWorkstation\\Parameters",
                            "Value": "EnableSecuritySignature",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "EnablePlainTextPassword": {
                        "Policy": "Microsoft network client: Send unencrypted "
                        "password to third-party SMB servers",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\"
                            "LanmanWorkstation\\Parameters",
                            "Value": "EnablePlainTextPassword",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "AutoDisconnect": {
                        "Policy": "Microsoft network server: Amount of idle "
                        "time required before suspending session",
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 99999},
                        },
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "LanmanServer\\Parameters",
                            "Value": "AutoDisconnect",
                            "Type": "REG_DWORD",
                        },
                    },
                    "EnableS4U2SelfForClaims": {
                        "Policy": "Microsoft network server: Attempt S4U2Self "
                        "to obtain claim information",
                        "Settings": self.s4u2self_options.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "LanmanServer\\Parameters",
                            "Value": "EnableS4U2SelfForClaims",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.s4u2self_options,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.s4u2self_options,
                                "value_lookup": True,
                            },
                        },
                    },
                    "Server_RequireSecuritySignature": {
                        "Policy": "Microsoft network server: Digitally sign "
                        "communications (always)",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\"
                            "LanmanServer\\Parameters",
                            "Value": "RequireSecuritySignature",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "Server_EnableSecuritySignature": {
                        "Policy": "Microsoft network server: Digitally sign "
                        "communications (if client agrees)",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\"
                            "LanmanServer\\Parameters",
                            "Value": "EnableSecuritySignature",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "EnableForcedLogoff": {
                        "Policy": "Microsoft network server: Disconnect "
                        "clients when logon hours expire",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\"
                            "LanmanServer\\Parameters",
                            "Value": "EnableForcedLogoff",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "SmbServerNameHardeningLevel": {
                        "Policy": "Microsoft network server: Server SPN target "
                        "name validation level",
                        "Settings": self.smb_server_name_hardening_levels.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "LanmanServer\\Parameters",
                            "Value": "SmbServerNameHardeningLevel",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.smb_server_name_hardening_levels,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.smb_server_name_hardening_levels,
                                "value_lookup": True,
                            },
                        },
                    },
                    "FullPrivilegeAuditing": {
                        "Policy": "Audit: Audit the use of Backup and Restore "
                        "privilege",
                        "Settings": [chr(0), chr(1)],
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\Lsa",
                            "Value": "FullPrivilegeAuditing",
                            "Type": "REG_BINARY",
                        },
                        "Transform": {
                            "Get": "_binary_enable_zero_disable_one_conversion",
                            "Put": "_binary_enable_zero_disable_one_reverse_conversion",
                        },
                    },
                    "CrashOnAuditFail": {
                        "Policy": "Audit: Shut down system immediately if "
                        "unable to log security audits",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "CrashOnAuditFail",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "UndockWithoutLogon": {
                        "Policy": "Devices: Allow undock without having to log " "on",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows\\"
                            "CurrentVersion\\Policies\\System",
                            "Value": "UndockWithoutLogon",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "AddPrinterDrivers": {
                        "Policy": "Devices: Prevent users from installing "
                        "printer drivers",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\"
                            "Print\\Providers\\LanMan Print Services\\"
                            "Servers",
                            "Value": "AddPrinterDrivers",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    "AllocateDASD": {
                        "Policy": "Devices: Allowed to format and eject "
                        "removable media",
                        "Settings": ["9999", "0", "1", "2"],
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows NT\\"
                            "CurrentVersion\\Winlogon",
                            "Value": "AllocateDASD",
                            "Type": "REG_SZ",
                        },
                        "Transform": {
                            "Get": "_dasd_conversion",
                            "Put": "_dasd_reverse_conversion",
                        },
                    },
                    "AllocateCDRoms": {
                        "Policy": "Devices: Restrict CD-ROM access to locally "
                        "logged-on user only",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows NT\\"
                            "CurrentVersion\\Winlogon",
                            "Value": "AllocateCDRoms",
                            "Type": "REG_SZ",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    "AllocateFloppies": {
                        "Policy": "Devices: Restrict floppy access to locally "
                        "logged-on user only",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows NT\\"
                            "CurrentVersion\\Winlogon",
                            "Value": "AllocateFloppies",
                            "Type": "REG_SZ",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    # see KB298503 why we aren't just doing this one via the
                    # registry
                    "DriverSigningPolicy": {
                        "Policy": "Devices: Unsigned driver installation " "behavior",
                        "Settings": ["3,0", "3," + chr(1), "3," + chr(2)],
                        "lgpo_section": self.security_options_gpedit_path,
                        "Secedit": {
                            "Option": "MACHINE\\Software\\Microsoft\\Driver "
                            "Signing\\Policy",
                            "Section": "Registry Values",
                        },
                        "Transform": {
                            "Get": "_driver_signing_reg_conversion",
                            "Put": "_driver_signing_reg_reverse_conversion",
                        },
                    },
                    "SubmitControl": {
                        "Policy": "Domain controller: Allow server operators "
                        "to schedule tasks",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\Lsa",
                            "Value": "SubmitControl",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    "LDAPServerIntegrity": {
                        "Policy": "Domain controller: LDAP server signing "
                        "requirements",
                        "Settings": self.ldap_server_signing_requirements.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\NTDS"
                            "\\Parameters",
                            "Value": "LDAPServerIntegrity",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.ldap_server_signing_requirements,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.ldap_server_signing_requirements,
                                "value_lookup": True,
                            },
                        },
                    },
                    "RefusePasswordChange": {
                        "Policy": "Domain controller: Refuse machine account "
                        "password changes",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\"
                            "Netlogon\\Parameters",
                            "Value": "RefusePasswordChange",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    "RequireSignOrSeal": {
                        "Policy": "Domain member: Digitally encrypt or sign "
                        "secure channel data (always)",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "Netlogon\\Parameters",
                            "Value": "RequireSignOrSeal",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    "SealSecureChannel": {
                        "Policy": "Domain member: Digitally encrypt secure "
                        "channel data (when possible)",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "Netlogon\\Parameters",
                            "Value": "SealSecureChannel",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    "SignSecureChannel": {
                        "Policy": "Domain member: Digitally sign secure "
                        "channel data (when possible)",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "Netlogon\\Parameters",
                            "Value": "SignSecureChannel",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    "DisablePasswordChange": {
                        "Policy": "Domain member: Disable machine account "
                        "password changes",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "Netlogon\\Parameters",
                            "Value": "DisablePasswordChange",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    "MaximumPasswordAge": {
                        "Policy": "Domain member: Maximum machine account "
                        "password age",
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 999},
                        },
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "Netlogon\\Parameters",
                            "Value": "MaximumPasswordAge",
                            "Type": "REG_DWORD",
                        },
                    },
                    "RequireStrongKey": {
                        "Policy": "Domain member: Require strong (Windows 2000 "
                        "or later) session key",
                        "Settings": self.enabled_one_disabled_zero_strings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\"
                            "Netlogon\\Parameters",
                            "Value": "RequireStrongKey",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_strings_transform,
                    },
                    "LockoutDuration": {
                        "Policy": "Account lockout duration",
                        "lgpo_section": self.account_lockout_policy_gpedit_path,
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 6000000},
                        },
                        "NetUserModal": {"Modal": 3, "Option": "lockout_duration"},
                        "Transform": {
                            "Get": "_seconds_to_minutes",
                            "Put": "_minutes_to_seconds",
                        },
                    },
                    "LockoutThreshold": {
                        "Policy": "Account lockout threshold",
                        "lgpo_section": self.account_lockout_policy_gpedit_path,
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 1000},
                        },
                        "NetUserModal": {"Modal": 3, "Option": "lockout_threshold"},
                    },
                    "LockoutWindow": {
                        "Policy": "Reset account lockout counter after",
                        "lgpo_section": self.account_lockout_policy_gpedit_path,
                        "Settings": {
                            "Function": "_in_range_inclusive",
                            "Args": {"min": 0, "max": 6000000},
                        },
                        "NetUserModal": {
                            "Modal": 3,
                            "Option": "lockout_observation_window",
                        },
                        "Transform": {
                            "Get": "_seconds_to_minutes",
                            "Put": "_minutes_to_seconds",
                        },
                    },
                    ########## LEGACY AUDIT POLICIES ##########
                    # To use these set the following policy to DISABLED
                    # "Audit: Force audit policy subcategory settings (Windows Vista or later) to override audit policy category settings"
                    # or it's alias...
                    # SceNoApplyLegacyAuditPolicy
                    "AuditAccountLogon": {
                        "Policy": "Audit account logon events",
                        "lgpo_section": self.audit_policy_gpedit_path,
                        "Settings": self.audit_lookup.keys(),
                        "Secedit": {
                            "Option": "AuditAccountLogon",
                            "Section": "Event Audit",
                        },
                        "Transform": self.audit_transform,
                    },
                    "AuditAccountManage": {
                        "Policy": "Audit account management",
                        "lgpo_section": self.audit_policy_gpedit_path,
                        "Settings": self.audit_lookup.keys(),
                        "Secedit": {
                            "Option": "AuditAccountManage",
                            "Section": "Event Audit",
                        },
                        "Transform": self.audit_transform,
                    },
                    "AuditDSAccess": {
                        "Policy": "Audit directory service access",
                        "lgpo_section": self.audit_policy_gpedit_path,
                        "Settings": self.audit_lookup.keys(),
                        "Secedit": {
                            "Option": "AuditDSAccess",
                            "Section": "Event Audit",
                        },
                        "Transform": self.audit_transform,
                    },
                    "AuditLogonEvents": {
                        "Policy": "Audit logon events",
                        "lgpo_section": self.audit_policy_gpedit_path,
                        "Settings": self.audit_lookup.keys(),
                        "Secedit": {
                            "Option": "AuditLogonEvents",
                            "Section": "Event Audit",
                        },
                        "Transform": self.audit_transform,
                    },
                    "AuditObjectAccess": {
                        "Policy": "Audit object access",
                        "lgpo_section": self.audit_policy_gpedit_path,
                        "Settings": self.audit_lookup.keys(),
                        "Secedit": {
                            "Option": "AuditObjectAccess",
                            "Section": "Event Audit",
                        },
                        "Transform": self.audit_transform,
                    },
                    "AuditPolicyChange": {
                        "Policy": "Audit policy change",
                        "lgpo_section": self.audit_policy_gpedit_path,
                        "Settings": self.audit_lookup.keys(),
                        "Secedit": {
                            "Option": "AuditPolicyChange",
                            "Section": "Event Audit",
                        },
                        "Transform": self.audit_transform,
                    },
                    "AuditPrivilegeUse": {
                        "Policy": "Audit privilege use",
                        "lgpo_section": self.audit_policy_gpedit_path,
                        "Settings": self.audit_lookup.keys(),
                        "Secedit": {
                            "Option": "AuditPrivilegeUse",
                            "Section": "Event Audit",
                        },
                        "Transform": self.audit_transform,
                    },
                    "AuditProcessTracking": {
                        "Policy": "Audit process tracking",
                        "lgpo_section": self.audit_policy_gpedit_path,
                        "Settings": self.audit_lookup.keys(),
                        "Secedit": {
                            "Option": "AuditProcessTracking",
                            "Section": "Event Audit",
                        },
                        "Transform": self.audit_transform,
                    },
                    "AuditSystemEvents": {
                        "Policy": "Audit system events",
                        "lgpo_section": self.audit_policy_gpedit_path,
                        "Settings": self.audit_lookup.keys(),
                        "Secedit": {
                            "Option": "AuditSystemEvents",
                            "Section": "Event Audit",
                        },
                        "Transform": self.audit_transform,
                    },
                    ########## END OF LEGACY AUDIT POLICIES ##########
                    ########## ADVANCED AUDIT POLICIES ##########
                    # Advanced Audit Policies
                    # To use these set the following policy to ENABLED
                    # "Audit: Force audit policy subcategory settings (Windows
                    # Vista or later) to override audit policy category
                    # settings"
                    # or it's alias...
                    # SceNoApplyLegacyAuditPolicy
                    # Account Logon Section
                    "AuditCredentialValidation": {
                        "Policy": "Audit Credential Validation",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Credential Validation"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditKerberosAuthenticationService": {
                        "Policy": "Audit Kerberos Authentication Service",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {
                            "Option": "Audit Kerberos Authentication Service",
                        },
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditKerberosServiceTicketOperations": {
                        "Policy": "Audit Kerberos Service Ticket Operations",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {
                            "Option": "Audit Kerberos Service Ticket Operations",
                        },
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditOtherAccountLogonEvents": {
                        "Policy": "Audit Other Account Logon Events",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Other Account Logon Events"},
                        "Transform": self.advanced_audit_transform,
                    },
                    # Account Management Section
                    "AuditApplicationGroupManagement": {
                        "Policy": "Audit Application Group Management",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Application Group Management"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditComputerAccountManagement": {
                        "Policy": "Audit Computer Account Management",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Computer Account Management"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditDistributionGroupManagement": {
                        "Policy": "Audit Distribution Group Management",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Distribution Group Management"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditOtherAccountManagementEvents": {
                        "Policy": "Audit Other Account Management Events",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {
                            "Option": "Audit Other Account Management Events",
                        },
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditSecurityGroupManagement": {
                        "Policy": "Audit Security Group Management",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Security Group Management"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditUserAccountManagement": {
                        "Policy": "Audit User Account Management",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit User Account Management"},
                        "Transform": self.advanced_audit_transform,
                    },
                    # Detailed Tracking Settings
                    "AuditDPAPIActivity": {
                        "Policy": "Audit DPAPI Activity",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit DPAPI Activity"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditPNPActivity": {
                        "Policy": "Audit PNP Activity",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit PNP Activity"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditProcessCreation": {
                        "Policy": "Audit Process Creation",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Process Creation"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditProcessTermination": {
                        "Policy": "Audit Process Termination",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Process Termination"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditRPCEvents": {
                        "Policy": "Audit RPC Events",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit RPC Events"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditTokenRightAdjusted": {
                        "Policy": "Audit Token Right Adjusted",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Token Right Adjusted"},
                        "Transform": self.advanced_audit_transform,
                    },
                    # DS Access Section
                    "AuditDetailedDirectoryServiceReplication": {
                        "Policy": "Audit Detailed Directory Service Replication",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {
                            "Option": "Audit Detailed Directory Service Replication",
                        },
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditDirectoryServiceAccess": {
                        "Policy": "Audit Directory Service Access",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Directory Service Access"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditDirectoryServiceChanges": {
                        "Policy": "Audit Directory Service Changes",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Directory Service Changes"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditDirectoryServiceReplication": {
                        "Policy": "Audit Directory Service Replication",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Directory Service Replication"},
                        "Transform": self.advanced_audit_transform,
                    },
                    # Logon/Logoff Section
                    "AuditAccountLockout": {
                        "Policy": "Audit Account Lockout",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Account Lockout"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditUserDeviceClaims": {
                        "Policy": "Audit User / Device Claims",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit User / Device Claims"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditGroupMembership": {
                        "Policy": "Audit Group Membership",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Group Membership"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditIPsecExtendedMode": {
                        "Policy": "Audit IPsec Extended Mode",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit IPsec Extended Mode"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditIPsecMainMode": {
                        "Policy": "Audit IPsec Main Mode",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit IPsec Main Mode"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditIPsecQuickMode": {
                        "Policy": "Audit IPsec Quick Mode",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit IPsec Quick Mode"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditLogoff": {
                        "Policy": "Audit Logoff",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Logoff"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditLogon": {
                        "Policy": "Audit Logon",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Logon"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditNetworkPolicyServer": {
                        "Policy": "Audit Network Policy Server",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Network Policy Server"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditOtherLogonLogoffEvents": {
                        "Policy": "Audit Other Logon/Logoff Events",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Other Logon/Logoff Events"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditSpecialLogon": {
                        "Policy": "Audit Special Logon",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Special Logon"},
                        "Transform": self.advanced_audit_transform,
                    },
                    # Object Access Section
                    "AuditApplicationGenerated": {
                        "Policy": "Audit Application Generated",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Application Generated"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditCertificationServices": {
                        "Policy": "Audit Certification Services",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Certification Services"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditDetailedFileShare": {
                        "Policy": "Audit Detailed File Share",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Detailed File Share"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditFileShare": {
                        "Policy": "Audit File Share",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit File Share"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditFileSystem": {
                        "Policy": "Audit File System",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit File System"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditFilteringPlatformConnection": {
                        "Policy": "Audit Filtering Platform Connection",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Filtering Platform Connection"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditFilteringPlatformPacketDrop": {
                        "Policy": "Audit Filtering Platform Packet Drop",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Filtering Platform Packet Drop"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditHandleManipulation": {
                        "Policy": "Audit Handle Manipulation",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Handle Manipulation"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditKernelObject": {
                        "Policy": "Audit Kernel Object",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Kernel Object"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditOtherObjectAccessEvents": {
                        "Policy": "Audit Other Object Access Events",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Other Object Access Events"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditRegistry": {
                        "Policy": "Audit Registry",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Registry"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditRemovableStorage": {
                        "Policy": "Audit Removable Storage",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Removable Storage"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditSAM": {
                        "Policy": "Audit SAM",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit SAM"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditCentralAccessPolicyStaging": {
                        "Policy": "Audit Central Access Policy Staging",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Central Access Policy Staging"},
                        "Transform": self.advanced_audit_transform,
                    },
                    # Policy Change Section
                    "AuditAuditPolicyChange": {
                        "Policy": "Audit Audit Policy Change",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Audit Policy Change"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditAuthenticationPolicyChange": {
                        "Policy": "Audit Authentication Policy Change",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Authentication Policy Change"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditAuthorizationPolicyChange": {
                        "Policy": "Audit Authorization Policy Change",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Authorization Policy Change"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditFilteringPlatformPolicyChange": {
                        "Policy": "Audit Filtering Platform Policy Change",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {
                            "Option": "Audit Filtering Platform Policy Change",
                        },
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditMPSSVCRuleLevelPolicyChange": {
                        "Policy": "Audit MPSSVC Rule-Level Policy Change",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {
                            "Option": "Audit MPSSVC Rule-Level Policy Change",
                        },
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditOtherPolicyChangeEvents": {
                        "Policy": "Audit Other Policy Change Events",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Other Policy Change Events"},
                        "Transform": self.advanced_audit_transform,
                    },
                    # Privilege Use Section
                    "AuditNonSensitivePrivilegeUse": {
                        "Policy": "Audit Non Sensitive Privilege Use",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Non Sensitive Privilege Use"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditOtherPrivilegeUseEvents": {
                        "Policy": "Audit Other Privilege Use Events",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Other Privilege Use Events"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditSensitivePrivilegeUse": {
                        "Policy": "Audit Sensitive Privilege Use",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Sensitive Privilege Use"},
                        "Transform": self.advanced_audit_transform,
                    },
                    # System Section
                    "AuditIPsecDriver": {
                        "Policy": "Audit IPsec Driver",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit IPsec Driver"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditOtherSystemEvents": {
                        "Policy": "Audit Other System Events",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Other System Events"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditSecurityStateChange": {
                        "Policy": "Audit Security State Change",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Security State Change"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditSecuritySystemExtension": {
                        "Policy": "Audit Security System Extension",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit Security System Extension"},
                        "Transform": self.advanced_audit_transform,
                    },
                    "AuditSystemIntegrity": {
                        "Policy": "Audit System Integrity",
                        "lgpo_section": self.advanced_audit_policy_gpedit_path,
                        "Settings": self.advanced_audit_lookup.keys(),
                        "AdvAudit": {"Option": "Audit System Integrity"},
                        "Transform": self.advanced_audit_transform,
                    },
                    ########## END OF ADVANCED AUDIT POLICIES ##########
                    "SeTrustedCredManAccessPrivilege": {
                        "Policy": "Access Credential Manager as a trusted " "caller",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeTrustedCredManAccessPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeNetworkLogonRight": {
                        "Policy": "Access this computer from the network",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeNetworkLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeTcbPrivilege": {
                        "Policy": "Act as part of the operating system",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeTcbPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeMachineAccountPrivilege": {
                        "Policy": "Add workstations to domain",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeMachineAccountPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeIncreaseQuotaPrivilege": {
                        "Policy": "Adjust memory quotas for a process",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeIncreaseQuotaPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeInteractiveLogonRight": {
                        "Policy": "Allow log on locally",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeInteractiveLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeRemoteInteractiveLogonRight": {
                        "Policy": "Allow log on through Remote Desktop Services",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeRemoteInteractiveLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeBackupPrivilege": {
                        "Policy": "Backup files and directories",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeBackupPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeChangeNotifyPrivilege": {
                        "Policy": "Bypass traverse checking",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeChangeNotifyPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeSystemtimePrivilege": {
                        "Policy": "Change the system time",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeSystemtimePrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeTimeZonePrivilege": {
                        "Policy": "Change the time zone",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeTimeZonePrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeCreatePagefilePrivilege": {
                        "Policy": "Create a pagefile",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeCreatePagefilePrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeCreateTokenPrivilege": {
                        "Policy": "Create a token object",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeCreateTokenPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeCreateGlobalPrivilege": {
                        "Policy": "Create global objects",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeCreateGlobalPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeCreatePermanentPrivilege": {
                        "Policy": "Create permanent shared objects",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeCreatePermanentPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeCreateSymbolicLinkPrivilege": {
                        "Policy": "Create symbolic links",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeCreateSymbolicLinkPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeDebugPrivilege": {
                        "Policy": "Debug programs",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeDebugPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeDenyNetworkLogonRight": {
                        "Policy": "Deny access to this computer from the " "network",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeDenyNetworkLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeDenyBatchLogonRight": {
                        "Policy": "Deny log on as a batch job",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeDenyBatchLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeDenyServiceLogonRight": {
                        "Policy": "Deny log on as a service",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeDenyServiceLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeDenyInteractiveLogonRight": {
                        "Policy": "Deny log on locally",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeDenyInteractiveLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeDenyRemoteInteractiveLogonRight": {
                        "Policy": "Deny log on through Remote Desktop Services",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeDenyRemoteInteractiveLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeEnableDelegationPrivilege": {
                        "Policy": "Enable computer and user accounts to be "
                        "trusted for delegation",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeEnableDelegationPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeRemoteShutdownPrivilege": {
                        "Policy": "Force shutdown from a remote system",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeRemoteShutdownPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeAuditPrivilege": {
                        "Policy": "Generate security audits",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeAuditPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeImpersonatePrivilege": {
                        "Policy": "Impersonate a client after authentication",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeImpersonatePrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeIncreaseWorkingSetPrivilege": {
                        "Policy": "Increase a process working set",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeIncreaseWorkingSetPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeIncreaseBasePriorityPrivilege": {
                        "Policy": "Increase scheduling priority",
                        "rights_assignment": True,
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "Settings": None,
                        "LsaRights": {"Option": "SeIncreaseBasePriorityPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeLoadDriverPrivilege": {
                        "Policy": "Load and unload device drivers",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeLoadDriverPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeLockMemoryPrivilege": {
                        "Policy": "Lock pages in memory",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeLockMemoryPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeBatchLogonRight": {
                        "Policy": "Log on as a batch job",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeBatchLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeServiceLogonRight": {
                        "Policy": "Log on as a service",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeServiceLogonRight"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeSecurityPrivilege": {
                        "Policy": "Manage auditing and security log",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeSecurityPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeRelabelPrivilege": {
                        "Policy": "Modify an object label",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeRelabelPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeSystemEnvironmentPrivilege": {
                        "Policy": "Modify firmware environment values",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeSystemEnvironmentPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeManageVolumePrivilege": {
                        "Policy": "Perform volume maintenance tasks",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeManageVolumePrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeProfileSingleProcessPrivilege": {
                        "Policy": "Profile single process",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeProfileSingleProcessPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeSystemProfilePrivilege": {
                        "Policy": "Profile system performance",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeSystemProfilePrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeUndockPrivilege": {
                        "Policy": "Remove computer from docking station",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeUndockPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeAssignPrimaryTokenPrivilege": {
                        "Policy": "Replace a process level token",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeAssignPrimaryTokenPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeRestorePrivilege": {
                        "Policy": "Restore files and directories",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeRestorePrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeShutdownPrivilege": {
                        "Policy": "Shut down the system",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeShutdownPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeSyncAgentPrivilege": {
                        "Policy": "Synchronize directory service data",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeSyncAgentPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "SeTakeOwnershipPrivilege": {
                        "Policy": "Take ownership of files or other objects",
                        "lgpo_section": self.user_rights_assignment_gpedit_path,
                        "rights_assignment": True,
                        "Settings": None,
                        "LsaRights": {"Option": "SeTakeOwnershipPrivilege"},
                        "Transform": {
                            "Get": "_sidConversion",
                            "Put": "_usernamesToSidObjects",
                        },
                    },
                    "RecoveryConsoleSecurityLevel": {
                        "Policy": "Recovery console: Allow automatic "
                        "administrative logon",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows NT\\"
                            "CurrentVersion\\Setup\\RecoveryConsole",
                            "Value": "SecurityLevel",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "RecoveryConsoleSetCommand": {
                        "Policy": "Recovery console: Allow floppy copy and "
                        "access to all drives and all folders",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Microsoft\\Windows NT\\"
                            "CurrentVersion\\Setup\\RecoveryConsole",
                            "Value": "SetCommand",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "ForceKeyProtection": {
                        "Policy": "System Cryptography: Force strong key protection for "
                        "user keys stored on the computer",
                        "Settings": self.force_key_protection.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Policies\\Microsoft\\Cryptography",
                            "Value": "ForceKeyProtection",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.force_key_protection,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.force_key_protection,
                                "value_lookup": True,
                            },
                        },
                    },
                    "FIPSAlgorithmPolicy": {
                        "Policy": "System Cryptography: Use FIPS compliant algorithms "
                        "for encryption, hashing, and signing",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\Lsa\\FIPSAlgorithmPolicy",
                            "Value": "Enabled",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "MachineAccessRestriction": {
                        "Policy": "DCOM: Machine Access Restrictions in Security Descriptor "
                        "Definition Language (SDDL) syntax",
                        "Settings": None,
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Policies\\Microsoft\\Windows NT\\DCOM",
                            "Value": "MachineAccessRestriction",
                            "Type": "REG_SZ",
                        },
                        "Transform": {"Put": "_string_put_transform"},
                    },
                    "MachineLaunchRestriction": {
                        "Policy": "DCOM: Machine Launch Restrictions in Security Descriptor "
                        "Definition Language (SDDL) syntax",
                        "Settings": None,
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "Software\\Policies\\Microsoft\\Windows NT\\DCOM",
                            "Value": "MachineLaunchRestriction",
                            "Type": "REG_SZ",
                        },
                        "Transform": {"Put": "_string_put_transform"},
                    },
                    "UseMachineId": {
                        "Policy": "Network security: Allow Local System to use computer "
                        "identity for NTLM",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "UseMachineId",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "allownullsessionfallback": {
                        "Policy": "Network security: Allow LocalSystem NULL session fallback",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa\\MSV1_0",
                            "Value": "allownullsessionfallback",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "AllowOnlineID": {
                        "Policy": "Network security: Allow PKU2U authentication requests "
                        "to this computer to use online identities.",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa\\pku2u",
                            "Value": "AllowOnlineID",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "KrbSupportedEncryptionTypes": {
                        "Policy": "Network security: Configure encryption types allowed "
                        "for Kerberos",
                        "Settings": None,
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\policies"
                            "\\system\\Kerberos\\Parameters",
                            "Value": "SupportedEncryptionTypes",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup_bitwise_add",
                            "Put": "_dict_lookup_bitwise_add",
                            "GetArgs": {
                                "lookup": self.krb_encryption_types,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.krb_encryption_types,
                                "value_lookup": True,
                            },
                        },
                    },
                    "NoLMHash": {
                        "Policy": "Network security: Do not store LAN Manager hash value "
                        "on next password change",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "NoLMHash",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "ForceLogoffWhenHourExpire": {
                        "Policy": "Network security: Force logoff when logon hours expire",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Settings": self.enabled_one_disabled_zero_no_not_defined.keys(),
                        "Secedit": {
                            "Option": "ForceLogoffWhenHourExpire",
                            "Section": "System Access",
                        },
                        "Transform": self.enabled_one_disabled_zero_no_not_defined_transform,
                    },
                    "LmCompatibilityLevel": {
                        "Policy": "Network security: LAN Manager authentication level",
                        "Settings": self.lm_compat_levels.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa",
                            "Value": "LmCompatibilityLevel",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.lm_compat_levels,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.lm_compat_levels,
                                "value_lookup": True,
                            },
                        },
                    },
                    "LDAPClientIntegrity": {
                        "Policy": "Network security: LDAP client signing requirements",
                        "Settings": self.ldap_signing_reqs.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\ldap",
                            "Value": "LDAPClientIntegrity",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.ldap_signing_reqs,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.ldap_signing_reqs,
                                "value_lookup": True,
                            },
                        },
                    },
                    "NTLMMinClientSec": {
                        "Policy": "Network security: Minimum session security for NTLM SSP based "
                        "(including secure RPC) clients",
                        "Settings": None,
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\Lsa\\MSV1_0",
                            "Value": "NTLMMinClientSec",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup_bitwise_add",
                            "Put": "_dict_lookup_bitwise_add",
                            "GetArgs": {
                                "lookup": self.ntlm_session_security_levels,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.ntlm_session_security_levels,
                                "value_lookup": True,
                            },
                        },
                    },
                    "NTLMMinServerSec": {
                        "Policy": "Network security: Minimum session security for NTLM SSP based "
                        "(including secure RPC) servers",
                        "Settings": None,
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\Lsa\\MSV1_0",
                            "Value": "NTLMMinServerSec",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup_bitwise_add",
                            "Put": "_dict_lookup_bitwise_add",
                            "GetArgs": {
                                "lookup": self.ntlm_session_security_levels,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.ntlm_session_security_levels,
                                "value_lookup": True,
                            },
                        },
                    },
                    "ClientAllowedNTLMServers": {
                        "Policy": "Network security: Restrict NTLM: Add remote server"
                        " exceptions for NTLM authentication",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\Lsa\\MSV1_0",
                            "Value": "ClientAllowedNTLMServers",
                            "Type": "REG_MULTI_SZ",
                        },
                        "Transform": {
                            "Put": "_multi_string_put_transform",
                            "Get": "_multi_string_get_transform",
                        },
                    },
                    "DCAllowedNTLMServers": {
                        "Policy": "Network security: Restrict NTLM: Add server exceptions"
                        " in this domain",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Services\\Netlogon\\Parameters",
                            "Value": "DCAllowedNTLMServers",
                            "Type": "REG_MULTI_SZ",
                        },
                        "Transform": {
                            "Put": "_multi_string_put_transform",
                            "Get": "_multi_string_get_transform",
                        },
                    },
                    "AuditReceivingNTLMTraffic": {
                        "Policy": "Network security: Restrict NTLM: Audit Incoming NTLM Traffic",
                        "Settings": self.ntlm_audit_settings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\LSA\\MSV1_0",
                            "Value": "AuditReceivingNTLMTraffic",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.ntlm_audit_settings,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.ntlm_audit_settings,
                                "value_lookup": True,
                            },
                        },
                    },
                    "AuditNTLMInDomain": {
                        "Policy": "Network security: Restrict NTLM: Audit NTLM "
                        "authentication in this domain",
                        "Settings": self.ntlm_domain_audit_settings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\Netlogon\\Parameters",
                            "Value": "AuditNTLMInDomain",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.ntlm_domain_audit_settings,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.ntlm_domain_audit_settings,
                                "value_lookup": True,
                            },
                        },
                    },
                    "RestrictReceivingNTLMTraffic": {
                        "Policy": "Network security: Restrict NTLM: Incoming"
                        " NTLM traffic",
                        "Settings": self.incoming_ntlm_settings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\LSA\\MSV1_0",
                            "Value": "RestrictReceivingNTLMTraffic",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.incoming_ntlm_settings,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.incoming_ntlm_settings,
                                "value_lookup": True,
                            },
                        },
                    },
                    "RestrictNTLMInDomain": {
                        "Policy": "Network security: Restrict NTLM: NTLM "
                        "authentication in this domain",
                        "Settings": self.ntlm_domain_auth_settings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Services\\Netlogon\\Parameters",
                            "Value": "RestrictNTLMInDomain",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.ntlm_domain_auth_settings,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.ntlm_domain_auth_settings,
                                "value_lookup": True,
                            },
                        },
                    },
                    "RestrictSendingNTLMTraffic": {
                        "Policy": "Network security: Restrict NTLM: Outgoing NTLM"
                        " traffic to remote servers",
                        "Settings": self.outgoing_ntlm_settings.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SYSTEM\\CurrentControlSet\\Control\\Lsa\\MSV1_0",
                            "Value": "RestrictSendingNTLMTraffic",
                            "Type": "REG_DWORD",
                        },
                        "Transform": {
                            "Get": "_dict_lookup",
                            "Put": "_dict_lookup",
                            "GetArgs": {
                                "lookup": self.outgoing_ntlm_settings,
                                "value_lookup": False,
                            },
                            "PutArgs": {
                                "lookup": self.outgoing_ntlm_settings,
                                "value_lookup": True,
                            },
                        },
                    },
                    "ShutdownWithoutLogon": {
                        "Policy": "Shutdown: Allow system to be shut down "
                        "without having to log on",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\policies\\system",
                            "Value": "ShutdownWithoutLogon",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "ClearPageFileAtShutdown": {
                        "Policy": "Shutdown: Clear virtual memory pagefile",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\"
                            "SESSION MANAGER\\MEMORY MANAGEMENT",
                            "Value": "ClearPageFileAtShutdown",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "ObCaseInsensitive": {
                        "Policy": "System objects: Require case insensitivity for "
                        "non-Windows subsystems",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\"
                            "SESSION MANAGER\\Kernel",
                            "Value": "ObCaseInsensitive",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "ProtectionMode": {
                        "Policy": "System objects: Strengthen default permissions of "
                        "internal system objects (e.g. Symbolic Links)",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\"
                            "SESSION MANAGER",
                            "Value": "ProtectionMode",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                    "OptionalSubsystems": {
                        "Policy": "System settings: Optional subsystems",
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "System\\CurrentControlSet\\Control\\"
                            "SESSION MANAGER\\SubSystems",
                            "Value": "optional",
                            "Type": "REG_MULTI_SZ",
                        },
                        "Transform": {
                            "Put": "_multi_string_put_transform",
                            "Get": "_multi_string_get_transform",
                        },
                    },
                    "AuthenticodeEnabled": {
                        "Policy": "System settings: Use Certificate Rules on Windows"
                        " Executables for Software Restriction Policies",
                        "Settings": self.enabled_one_disabled_zero.keys(),
                        "lgpo_section": self.security_options_gpedit_path,
                        "Registry": {
                            "Hive": "HKEY_LOCAL_MACHINE",
                            "Path": "SOFTWARE\\Policies\\Microsoft\\Windows\\safer\\codeidentifiers",
                            "Value": "AuthenticodeEnabled",
                            "Type": "REG_DWORD",
                        },
                        "Transform": self.enabled_one_disabled_zero_transform,
                    },
                },
            },
            "User": {"lgpo_section": "User Configuration", "policies": {}},
        }
        self.admx_registry_classes = {
            "User": {
                "policy_path": os.path.join(
                    os.getenv("WINDIR"),
                    "System32",
                    "GroupPolicy",
                    "User",
                    "Registry.pol",
                ),
                "hive": "HKEY_USERS",
                "lgpo_section": "User Configuration",
                "gpt_extension_location": "gPCUserExtensionNames",
                "gpt_extension_guid": "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F73-3407-48AE-BA88-E8213C6761F1}]",
            },
            "Machine": {
                "policy_path": os.path.join(
                    os.getenv("WINDIR"),
                    "System32",
                    "GroupPolicy",
                    "Machine",
                    "Registry.pol",
                ),
                "hive": "HKEY_LOCAL_MACHINE",
                "lgpo_section": "Computer Configuration",
                "gpt_extension_location": "gPCMachineExtensionNames",
                "gpt_extension_guid": "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]",
            },
        }
        self.reg_pol_header = "\u5250\u6765\x01\x00"
        self.gpt_ini_path = os.path.join(
            os.getenv("WINDIR"), "System32", "GroupPolicy", "gpt.ini"
        )

    @classmethod
    def _notEmpty(cls, val, **kwargs):
        """
        ensures a value is not empty
        """
        if val:
            return True
        else:
            return False

    @classmethod
    def _seconds_to_days(cls, val, **kwargs):
        """
        converts a number of seconds to days
        """
        zero_value = kwargs.get("zero_value", 0)
        if val is not None:
            if val == zero_value:
                return 0
            return val / 86400
        else:
            return "Not Defined"

    @classmethod
    def _days_to_seconds(cls, val, **kwargs):
        """
        converts a number of days to seconds
        """
        zero_value = kwargs.get("zero_value", 0)
        if val is not None:
            if val == 0:
                return zero_value
            return val * 86400
        else:
            return "Not Defined"

    @classmethod
    def _seconds_to_minutes(cls, val, **kwargs):
        """
        converts a number of seconds to minutes
        """
        if val is not None:
            return val / 60
        else:
            return "Not Defined"

    @classmethod
    def _minutes_to_seconds(cls, val, **kwargs):
        """
        converts number of minutes to seconds
        """
        if val is not None:
            return val * 60
        else:
            return "Not Defined"

    @classmethod
    def _strip_quotes(cls, val, **kwargs):
        """
        strips quotes from a string
        """
        return val.replace('"', "")

    @classmethod
    def _add_quotes(cls, val, **kwargs):
        """
        add quotes around the string
        """
        return '"{0}"'.format(val)

    @classmethod
    def _binary_enable_zero_disable_one_conversion(cls, val, **kwargs):
        """
        converts a binary 0/1 to Disabled/Enabled
        """
        try:
            if val is not None:
                if ord(val) == 0:
                    return "Disabled"
                elif ord(val) == 1:
                    return "Enabled"
                else:
                    return "Invalid Value: {0!r}".format(val)
            else:
                return "Not Defined"
        except TypeError:
            return "Invalid Value"

    @classmethod
    def _binary_enable_zero_disable_one_reverse_conversion(cls, val, **kwargs):
        """
        converts Enabled/Disabled to unicode char to write to a REG_BINARY value
        """
        if val is not None:
            if val.upper() == "DISABLED":
                return chr(0)
            elif val.upper() == "ENABLED":
                return chr(1)
            else:
                return None
        else:
            return None

    @classmethod
    def _dasd_conversion(cls, val, **kwargs):
        """
        converts 0/1/2 for dasd reg key
        """
        if val is not None:
            if val == "0" or val == 0 or val == "":
                return "Administrators"
            elif val == "1" or val == 1:
                return "Administrators and Power Users"
            elif val == "2" or val == 2:
                return "Administrators and Interactive Users"
            else:
                return "Not Defined"
        else:
            return "Not Defined"

    @classmethod
    def _dasd_reverse_conversion(cls, val, **kwargs):
        """
        converts DASD String values to the reg_sz value
        """
        if val is not None:
            if val.upper() == "ADMINISTRATORS":
                # "" also shows 'administrators' in the GUI
                return "0"
            elif val.upper() == "ADMINISTRATORS AND POWER USERS":
                return "1"
            elif val.upper() == "ADMINISTRATORS AND INTERACTIVE USERS":
                return "2"
            elif val.upper() == "NOT DEFINED":
                # a setting of anything other than nothing, 0, 1, 2 or if it
                # doesn't exist show 'not defined'
                return "9999"
            else:
                return "Invalid Value"
        else:
            return "Not Defined"

    @classmethod
    def _in_range_inclusive(cls, val, **kwargs):
        """
        checks that a value is in an inclusive range
        The value for 0 used by Max Password Age is actually 0xffffffff
        """
        minimum = kwargs.get("min", 0)
        maximum = kwargs.get("max", 1)
        zero_value = kwargs.get("zero_value", 0)

        if isinstance(val, six.string_types):
            if val.lower() == "not defined":
                return True
            else:
                try:
                    val = int(val)
                except ValueError:
                    return False
        if val is not None:
            if minimum <= val <= maximum or val == zero_value:
                return True
            else:
                return False
        else:
            return False

    @classmethod
    def _driver_signing_reg_conversion(cls, val, **kwargs):
        """
        converts the binary value in the registry for driver signing into the
        correct string representation
        """
        log.trace("we have %s for the driver signing value", val)
        if val is not None:
            # since this is from secedit, it should be 3,<value>
            _val = val.split(",")
            if len(_val) == 2:
                if _val[1] == "0":
                    return "Silently Succeed"
                elif _val[1] == "1":
                    return "Warn but allow installation"
                elif _val[1] == "2":
                    return "Do not allow installation"
                elif _val[1] == "Not Defined":
                    return "Not Defined"
                else:
                    return "Invalid Value"
            else:
                return "Not Defined"
        else:
            return "Not Defined"

    @classmethod
    def _driver_signing_reg_reverse_conversion(cls, val, **kwargs):
        """
        converts the string value seen in the GUI to the correct registry value
        for secedit
        """
        if val is not None:
            if val.upper() == "SILENTLY SUCCEED":
                return ",".join(["3", "0"])
            elif val.upper() == "WARN BUT ALLOW INSTALLATION":
                return ",".join(["3", chr(1)])
            elif val.upper() == "DO NOT ALLOW INSTALLATION":
                return ",".join(["3", chr(2)])
            else:
                return "Invalid Value"
        else:
            return "Not Defined"

    @classmethod
    def _sidConversion(cls, val, **kwargs):
        """
        converts a list of pysid objects to string representations
        """
        if isinstance(val, six.string_types):
            val = val.split(",")
        usernames = []
        for _sid in val:
            try:
                userSid = win32security.LookupAccountSid("", _sid)
                if userSid[1]:
                    userSid = "{1}\\{0}".format(userSid[0], userSid[1])
                else:
                    userSid = "{0}".format(userSid[0])
            # TODO: This needs to be more specific
            except Exception:  # pylint: disable=broad-except
                userSid = win32security.ConvertSidToStringSid(_sid)
                log.warning(
                    'Unable to convert SID "%s" to a friendly name.  The SID will be disaplayed instead of a user/group name.',
                    userSid,
                )
            usernames.append(userSid)
        return usernames

    @classmethod
    def _usernamesToSidObjects(cls, val, **kwargs):
        """
        converts a list of usernames to sid objects
        """
        if not val:
            return val
        if isinstance(val, six.string_types):
            val = val.split(",")
        sids = []
        for _user in val:
            try:
                sid = win32security.LookupAccountName("", _user)[0]
                sids.append(sid)
            # This needs to be more specific
            except Exception as e:  # pylint: disable=broad-except
                log.exception("Handle this explicitly")
                raise CommandExecutionError(
                    (
                        'There was an error obtaining the SID of user "{0}". Error '
                        "returned: {1}"
                    ).format(_user, e)
                )
        return sids

    @classmethod
    def _powershell_script_order_conversion(cls, val, **kwargs):
        """
        converts true/false/None to the GUI representation of the powershell
        startup/shutdown script order
        """
        log.trace("script order value = %s", val)
        if val is None or val == "None":
            return "Not Configured"
        elif val == "true":
            return "Run Windows PowerShell scripts first"
        elif val == "false":
            return "Run Windows PowerShell scripts last"
        else:
            return "Invalid Value"

    @classmethod
    def _powershell_script_order_reverse_conversion(cls, val, **kwargs):
        """
        converts powershell script GUI strings representations to
        True/False/None
        """
        if val.upper() == "Run Windows PowerShell scripts first".upper():
            return "true"
        elif val.upper() == "Run Windows PowerShell scripts last".upper():
            return "false"
        elif val is "Not Configured":
            return None
        else:
            return "Invalid Value"

    @classmethod
    def _dict_lookup(cls, item, **kwargs):
        """
        Retrieves the key or value from a dict based on the item
        kwarg lookup dict to search for item
        kwarg value_lookup bool to determine if item should be compared to keys
        or values
        """
        log.trace("item == %s", item)
        value_lookup = kwargs.get("value_lookup", False)
        if "lookup" in kwargs:
            for k, v in six.iteritems(kwargs["lookup"]):
                if value_lookup:
                    if six.text_type(v).lower() == six.text_type(item).lower():
                        log.trace("returning key %s", k)
                        return k
                else:
                    if six.text_type(k).lower() == six.text_type(item).lower():
                        log.trace("returning value %s", v)
                        return v
        return "Invalid Value"

    @classmethod
    def _dict_lookup_bitwise_add(cls, item, **kwargs):
        """
        kwarg value_lookup bool to determine if item_list should be compared to keys
        or values

        kwarg test_zero is used to determine if 0 should be tested when value_lookup is false
        lookup should be a dict with integers for keys

        if value_lookup is True, item is expected to be a list
            the function will return the sum of the keys whose values are in the item list
        if value_lookup is False, item is expected to be an integer
            the function will return the values for the keys
            which successfully "bitwise and" with item
        """
        value_lookup = kwargs.get("value_lookup", False)
        test_zero = kwargs.get("test_zero", False)
        ret_val = None
        if str(item).lower() == "not defined":
            return None
        if value_lookup:
            if not isinstance(item, list):
                return "Invalid Value"
            ret_val = 0
        else:
            if not isinstance(item, six.integer_types):
                return "Invalid Value"
            ret_val = []
        if "lookup" in kwargs:
            for k, v in six.iteritems(kwargs["lookup"]):
                if value_lookup:
                    if six.text_type(v).lower() in [z.lower() for z in item]:
                        ret_val = ret_val + k
                else:
                    do_test = True
                    if not test_zero:
                        if k == 0:
                            do_test = False
                    if do_test and isinstance(k, int) and item & k == k:
                        ret_val.append(v)
        else:
            return "Invalid Value"
        return ret_val

    @classmethod
    def _multi_string_put_transform(cls, item, **kwargs):
        """
        transform for setting REG_MULTI_SZ to properly handle "Not Defined"
        """
        if isinstance(item, list):
            return item
        elif isinstance(item, six.string_types):
            if item.lower() == "not defined":
                return None
            else:
                return item.split(",")
        else:
            return "Invalid Value"

    @classmethod
    def _multi_string_get_transform(cls, item, **kwargs):
        """
        transform for getting REG_MULTI_SZ to properly handle `None`
        """
        if isinstance(item, list):
            return item
        elif item is None:
            return "Not Defined"
        else:
            return "Invalid Value"

    @classmethod
    def _string_put_transform(cls, item, **kwargs):
        """
        transform for a REG_SZ to properly handle "Not Defined"
        """
        if isinstance(item, six.string_types):
            if item.lower() == "not defined":
                return None
            else:
                return item


def __virtual__():
    """
    Only works on Windows systems
    """
    if not salt.utils.platform.is_windows():
        return False, "win_lgpo: Not a Windows System"
    if not HAS_WINDOWS_MODULES:
        return False, "win_lgpo: Required modules failed to load"
    return __virtualname__


def _updateNamespace(item, new_namespace):
    """
    helper function to recursively update the namespaces of an item
    """
    temp_item = ""
    i = item.tag.find("}")
    if i >= 0:
        temp_item = item.tag[i + 1 :]
    else:
        temp_item = item.tag
    item.tag = "{{{0}}}{1}".format(new_namespace, temp_item)
    for child in item.getiterator():
        if isinstance(child.tag, six.string_types):
            temp_item = ""
            i = child.tag.find("}")
            if i >= 0:
                temp_item = child.tag[i + 1 :]
            else:
                temp_item = child.tag
            child.tag = "{{{0}}}{1}".format(new_namespace, temp_item)
    return item


def _updatePolicyElements(policy_item, regkey):
    """
    helper function to add the reg key to each policies element definitions if
    the key attribute is not defined to make xpath searching easier for each
    child in the policy <elements> item
    """
    for child in policy_item.getiterator():
        if "valueName" in child.attrib:
            if "key" not in child.attrib:
                child.attrib["key"] = regkey
    return policy_item


def _remove_unicode_encoding(xml_file):
    """
    attempts to remove the "encoding='unicode'" from an xml file
    as lxml does not support that on a windows node currently

    see issue #38100 (Search.adml)

    For some reason this file is encoded 'utf-16'
    """
    with salt.utils.files.fopen(xml_file, "rb") as f:
        xml_content = f.read()
    modified_xml = re.sub(
        r' encoding=[\'"]+unicode[\'"]+', "", xml_content.decode("utf-16"), count=1
    )
    xml_tree = lxml.etree.parse(six.StringIO(modified_xml))
    return xml_tree


def _remove_invalid_xmlns(xml_file):
    """
    Attempts to remove an invalid xmlns entry in newer versions of
    WindowsDefender.adml

    xmlns="http://schemas.microsoft.com/GroupPolicy/2006/07/PolicyDefinitions"

    For some reason this file is encoded 'utf-8'
    """
    with salt.utils.files.fopen(xml_file, "rb") as f:
        xml_content = f.read()
    modified_xml = re.sub(
        r' xmlns=[\'"]+.*[\'"]+', "", xml_content.decode("utf-8"), count=1
    )
    xml_tree = lxml.etree.parse(six.StringIO(modified_xml))
    return xml_tree


def _parse_xml(adm_file):
    """
    Parse the admx/adml file. There are 3 scenarios (so far) that we'll likely
    encounter:

    1. Valid File
    2. invalid encoding (encoding="unicode") which the lxml library doesn't
       recognize
    3. invalid xmlns entry in the xml header, which the lxml library doesn't
       recognize
    """
    parser = lxml.etree.XMLParser(remove_comments=True)

    modified_xml = ""
    with salt.utils.files.fopen(adm_file, "rb") as rfh:
        file_hash = "{0:X}".format(zlib.crc32(rfh.read()) & 0xFFFFFFFF)

    name, ext = os.path.splitext(os.path.basename(adm_file))
    hashed_filename = "{0}-{1}{2}".format(name, file_hash, ext)

    cache_dir = os.path.join(__opts__["cachedir"], "lgpo", "policy_defs")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    out_file = os.path.join(cache_dir, hashed_filename)

    if not os.path.isfile(out_file):
        log.debug("LGPO: Generating policy template cache for %s%s", name, ext)

        # Remove old files, keep the cache clean
        file_list = glob.glob(os.path.join(cache_dir, "{0}*{1}".format(name, ext)))
        for file_path in file_list:
            os.remove(file_path)

        # Lowercase all the keys
        with salt.utils.files.fopen(adm_file, "rb") as rfh:

            encoding = "utf-8"
            raw = rfh.read()
            try:
                raw = raw.decode(encoding)
            except UnicodeDecodeError:
                log.trace("LGPO: Detecting encoding")
                encoding = "utf-16"
                raw = raw.decode(encoding)
            for line in raw.split("\r\n"):
                if 'key="' in line:
                    start = line.index('key="')
                    q1 = line[start:].index('"') + start
                    q2 = line[q1 + 1 :].index('"') + q1 + 1
                    line = line.replace(line[start:q2], line[start:q2].lower())
                    found_key = True
                modified_xml += line + "\r\n"

        # Convert smart quotes to regular quotes
        modified_xml = modified_xml.replace("\u201c", '"').replace("\u201d", '"')
        modified_xml = modified_xml.replace("\u2018", "'").replace("\u2019", "'")

        # Convert em dash and en dash to dash
        modified_xml = modified_xml.replace("\u2013", "-").replace("\u2014", "-")

        with salt.utils.files.fopen(out_file, "wb") as wfh:
            wfh.write(modified_xml.encode(encoding))

    try:
        # First we'll try to parse valid xml
        xml_tree = lxml.etree.parse(out_file, parser=parser)
    except lxml.etree.XMLSyntaxError:
        try:
            # Next we'll try invalid encoding (see issue #38100)
            xml_tree = _remove_unicode_encoding(out_file)
        except lxml.etree.XMLSyntaxError:
            # Finally we'll try invalid xmlns entry, if this fails, we just want
            # to raise the error
            xml_tree = _remove_invalid_xmlns(out_file)
    return xml_tree


def _load_policy_definitions(path="c:\\Windows\\PolicyDefinitions", language="en-US"):
    """
    helper function to process all ADMX files in the specified policy_def_path
    and build a single XML doc that we can search/use for ADMX policy processing
    """
    # Fallback to the System Install Language
    display_language_fallback = INSTALL_LANGUAGE
    t_policy_definitions = lxml.etree.Element("policyDefinitions")
    t_policy_definitions.append(lxml.etree.Element("categories"))
    t_policy_definitions.append(lxml.etree.Element("policies"))
    t_policy_definitions.append(lxml.etree.Element("policyNamespaces"))
    t_policy_definition_resources = lxml.etree.Element("policyDefinitionResources")
    policydefs_policies_xpath = etree.XPath("/policyDefinitions/policies")
    policydefs_categories_xpath = etree.XPath("/policyDefinitions/categories")
    policydefs_policyns_xpath = etree.XPath("/policyDefinitions/policyNamespaces")
    policydefs_resources_localname_xpath = etree.XPath(
        '//*[local-name() = "policyDefinitionResources"]/*'
    )
    policydef_resources_xpath = etree.XPath("/policyDefinitionResources")
    for root, dirs, files in salt.utils.path.os_walk(path):
        if root == path:
            for t_admx_file in files:
                admx_file_name, admx_file_ext = os.path.splitext(t_admx_file)
                # Only process ADMX files, any other file will cause a
                # stacktrace later on
                if not admx_file_ext == ".admx":
                    log.debug("{0} is not an ADMX file".format(t_admx_file))
                    continue
                admx_file = os.path.join(root, t_admx_file)
                # Parse xml for the ADMX file
                try:
                    xml_tree = _parse_xml(admx_file)
                except lxml.etree.XMLSyntaxError:
                    log.error(
                        "An error was found while processing admx "
                        "file %s, all policies from this file will "
                        "be unavailable via this module",
                        admx_file,
                    )
                    continue
                namespaces = xml_tree.getroot().nsmap
                namespace_string = ""
                if None in namespaces:
                    namespaces["None"] = namespaces[None]
                    namespaces.pop(None)
                    namespace_string = "None:"
                this_namespace = xml_tree.xpath(
                    "/{0}policyDefinitions/{0}policyNamespaces/{0}target/@namespace".format(
                        namespace_string
                    ),
                    namespaces=namespaces,
                )[0]
                categories = xml_tree.xpath(
                    "/{0}policyDefinitions/{0}categories/{0}category".format(
                        namespace_string
                    ),
                    namespaces=namespaces,
                )
                for category in categories:
                    temp_cat = category
                    temp_cat = _updateNamespace(temp_cat, this_namespace)
                    policydefs_categories_xpath(t_policy_definitions)[0].append(
                        temp_cat
                    )
                policies = xml_tree.xpath(
                    "/{0}policyDefinitions/{0}policies/{0}policy".format(
                        namespace_string
                    ),
                    namespaces=namespaces,
                )
                for policy in policies:
                    temp_pol = policy
                    temp_pol = _updateNamespace(temp_pol, this_namespace)
                    if "key" in temp_pol.attrib:
                        temp_pol = _updatePolicyElements(
                            temp_pol, temp_pol.attrib["key"]
                        )

                    policydefs_policies_xpath(t_policy_definitions)[0].append(temp_pol)
                policy_namespaces = xml_tree.xpath(
                    "/{0}policyDefinitions/{0}policyNamespaces/{0}*".format(
                        namespace_string
                    ),
                    namespaces=namespaces,
                )
                for policy_ns in policy_namespaces:
                    temp_ns = policy_ns
                    temp_ns = _updateNamespace(temp_ns, this_namespace)
                    policydefs_policyns_xpath(t_policy_definitions)[0].append(temp_ns)

                # We need to make sure the adml file exists. First we'll check
                # the passed language (eg: en-US). Then we'll try the
                # abbreviated version (en) to account for alternate locations.
                # We'll do the same for the display_language_fallback (en_US).
                adml_file = os.path.join(root, language, admx_file_name + ".adml")
                if not __salt__["file.file_exists"](adml_file):
                    log.info(
                        "An ADML file in the specified ADML language "
                        '"%s" does not exist for the ADMX "%s", the '
                        "the abbreviated language code will be tried.",
                        language,
                        t_admx_file,
                    )

                    adml_file = os.path.join(
                        root, language.split("-")[0], admx_file_name + ".adml"
                    )
                    if not __salt__["file.file_exists"](adml_file):
                        log.info(
                            "An ADML file in the specified ADML language "
                            'code %s does not exist for the ADMX "%s", '
                            "the fallback language will be tried.",
                            language[:2],
                            t_admx_file,
                        )

                        adml_file = os.path.join(
                            root, display_language_fallback, admx_file_name + ".adml"
                        )
                        if not __salt__["file.file_exists"](adml_file):
                            log.info(
                                "An ADML file in the specified ADML "
                                'fallback language "%s" '
                                'does not exist for the ADMX "%s" '
                                "the abbreviated fallback language code "
                                "will be tried.",
                                display_language_fallback,
                                t_admx_file,
                            )

                            adml_file = os.path.join(
                                root,
                                display_language_fallback.split("-")[0],
                                admx_file_name + ".adml",
                            )
                            if not __salt__["file.file_exists"](adml_file):
                                msg = (
                                    "An ADML file in the specified ADML language "
                                    '"{0}" and the fallback language "{1}" do not '
                                    'exist for the ADMX "{2}".'
                                )
                                raise SaltInvocationError(
                                    msg.format(
                                        language, display_language_fallback, t_admx_file
                                    )
                                )
                # Parse xml for the ADML file
                try:
                    xml_tree = _parse_xml(adml_file)
                except lxml.etree.XMLSyntaxError:
                    log.error(
                        "An error was found while processing adml "
                        "file %s, all policies from this file will "
                        "be unavailable via this module",
                        adml_file,
                    )
                    continue
                if None in namespaces:
                    namespaces["None"] = namespaces[None]
                    namespaces.pop(None)
                policydefs_resources = policydefs_resources_localname_xpath(xml_tree)
                for policydefs_resource in policydefs_resources:
                    t_poldef = policydefs_resource
                    t_poldef = _updateNamespace(t_poldef, this_namespace)
                    policydef_resources_xpath(t_policy_definition_resources)[0].append(
                        t_poldef
                    )
    __context__["lgpo.policy_definitions"] = t_policy_definitions
    __context__["lgpo.policy_resources"] = t_policy_definition_resources


def _get_policy_definitions(path="c:\\Windows\\PolicyDefinitions", language="en-US"):
    if "lgpo.policy_definitions" not in __context__:
        log.debug("LGPO: Loading policy definitions")
        _load_policy_definitions(path=path, language=language)
    return __context__["lgpo.policy_definitions"]


def _get_policy_resources(path="c:\\Windows\\PolicyDefinitions", language="en-US"):
    if "lgpo.policy_resources" not in __context__:
        log.debug("LGPO: Loading policy resources")
        _load_policy_definitions(path=path, language=language)
    return __context__["lgpo.policy_resources"]


def _buildElementNsmap(using_elements):
    """
    build a namespace map for an ADMX element
    """
    thisMap = {}
    for e in using_elements:
        thisMap[e.attrib["prefix"]] = e.attrib["namespace"]
    return thisMap


def _get_advaudit_defaults(option=None):
    """
    Loads audit.csv defaults into a dict in __context__ called
    'lgpo.audit_defaults'. The dictionary includes fieldnames and all
    configurable policies as keys. The values are used to create/modify the
    ``audit.csv`` file. The first entry is `fieldnames` used to create the
    header for the csv file. The rest of the entries are the audit policy names.
    Sample data follows:

    {
        'fieldnames': ['Machine Name',
                       'Policy Target',
                       'Subcategory',
                       'Subcategory GUID',
                       'Inclusion Setting',
                       'Exclusion Setting',
                       'Setting Value'],
        'Audit Sensitive Privilege Use': {'Auditpol Name': 'Sensitive Privilege Use',
                                          'Exclusion Setting': '',
                                          'Inclusion Setting': 'No Auditing',
                                          'Machine Name': 'WIN-8FGT3E045SE',
                                          'Policy Target': 'System',
                                          'Setting Value': '0',
                                          'Subcategory': u'Audit Sensitive Privilege Use',
                                          'Subcategory GUID': '{0CCE9228-69AE-11D9-BED3-505054503030}'},
        'Audit Special Logon': {'Auditpol Name': 'Special Logon',
                                'Exclusion Setting': '',
                                'Inclusion Setting': 'No Auditing',
                                'Machine Name': 'WIN-8FGT3E045SE',
                                'Policy Target': 'System',
                                'Setting Value': '0',
                                'Subcategory': u'Audit Special Logon',
                                'Subcategory GUID': '{0CCE921B-69AE-11D9-BED3-505054503030}'},
        'Audit System Integrity': {'Auditpol Name': 'System Integrity',
                                   'Exclusion Setting': '',
                                   'Inclusion Setting': 'No Auditing',
                                   'Machine Name': 'WIN-8FGT3E045SE',
                                   'Policy Target': 'System',
                                   'Setting Value': '0',
                                   'Subcategory': u'Audit System Integrity',
                                   'Subcategory GUID': '{0CCE9212-69AE-11D9-BED3-505054503030}'},
        ...
    }

    .. note::
        `Auditpol Name` designates the value to use when setting the value with
        the auditpol command

    Args:
        option (str): The item from the dictionary to return. If ``None`` the
            entire dictionary is returned. Default is ``None``

    Returns:
        dict: If ``None`` or one of the audit settings is passed
        list: If ``fieldnames`` is passed
    """
    if "lgpo.audit_defaults" not in __context__:
        # Get available setting names and GUIDs
        # This is used to get the fieldnames and GUIDs for individual policies
        log.debug("Loading auditpol defaults into __context__")
        dump = __utils__["auditpol.get_auditpol_dump"]()
        reader = csv.DictReader(dump)
        audit_defaults = {"fieldnames": reader.fieldnames}
        for row in reader:
            row["Machine Name"] = ""
            row["Auditpol Name"] = row["Subcategory"]
            # Special handling for snowflake scenarios where the audit.csv names
            # don't match the auditpol names
            if row["Subcategory"] == "Central Policy Staging":
                row["Subcategory"] = "Audit Central Access Policy Staging"
            elif row["Subcategory"] == "Plug and Play Events":
                row["Subcategory"] = "Audit PNP Activity"
            elif row["Subcategory"] == "Token Right Adjusted Events":
                row["Subcategory"] = "Audit Token Right Adjusted"
            else:
                row["Subcategory"] = "Audit {0}".format(row["Subcategory"])
            audit_defaults[row["Subcategory"]] = row

        __context__["lgpo.audit_defaults"] = audit_defaults

    if option:
        return __context__["lgpo.audit_defaults"][option]
    else:
        return __context__["lgpo.audit_defaults"]


def _get_advaudit_value(option):
    """
    Get the Advanced Auditing policy as configured in
    ``C:\\Windows\\Security\\Audit\\audit.csv``

    Args:
        option (str): The name of the setting as it appears in audit.csv

    Returns:
        bool: ``True`` if successful, otherwise ``False``
    """
    if "lgpo.adv_audit_data" not in __context__:
        system_root = os.environ.get("SystemRoot", "C:\\Windows")
        f_audit = os.path.join(system_root, "security", "audit", "audit.csv")
        f_audit_gpo = os.path.join(
            system_root,
            "System32",
            "GroupPolicy",
            "Machine",
            "Microsoft",
            "Windows NT",
            "Audit",
            "audit.csv",
        )

        # Make sure there is an existing audit.csv file on the machine
        if not __salt__["file.file_exists"](f_audit):
            if __salt__["file.file_exists"](f_audit_gpo):
                # If the GPO audit.csv exists, we'll use that one
                __salt__["file.copy"](f_audit_gpo, f_audit)
            else:
                field_names = _get_advaudit_defaults("fieldnames")
                # If the file doesn't exist anywhere, create it with default
                # fieldnames
                __salt__["file.makedirs"](f_audit)
                __salt__["file.write"](f_audit, ",".join(field_names))

        audit_settings = {}
        with salt.utils.files.fopen(f_audit, mode="r") as csv_file:
            reader = csv.DictReader(csv_file)

            for row in reader:
                audit_settings.update({row["Subcategory"]: row["Setting Value"]})

        __context__["lgpo.adv_audit_data"] = audit_settings

    return __context__["lgpo.adv_audit_data"].get(option, None)


def _set_audit_file_data(option, value):
    """
    Helper function that sets the Advanced Audit settings in the two .csv files
    on Windows. Those files are located at:
    C:\\Windows\\Security\\Audit\\audit.csv
    C:\\Windows\\System32\\GroupPolicy\\Machine\\Microsoft\\Windows NT\\Audit\\audit.csv

    Args:
        option (str): The name of the option to set
        value (str): The value to set. ['None', '0', '1', '2', '3']

    Returns:
        bool: ``True`` if successful, otherwise ``False``
    """
    # Set up some paths here
    system_root = os.environ.get("SystemRoot", "C:\\Windows")
    f_audit = os.path.join(system_root, "security", "audit", "audit.csv")
    f_audit_gpo = os.path.join(
        system_root,
        "System32",
        "GroupPolicy",
        "Machine",
        "Microsoft",
        "Windows NT",
        "Audit",
        "audit.csv",
    )
    f_temp = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".csv", prefix="audit"
    )

    # Lookup dict for "Inclusion Setting" field
    auditpol_values = {
        "None": "No Auditing",
        "0": "No Auditing",
        "1": "Success",
        "2": "Failure",
        "3": "Success and Failure",
    }

    try:
        # Open the existing audit.csv and load the csv `reader`
        with salt.utils.files.fopen(f_audit, mode="r") as csv_file:
            reader = csv.DictReader(csv_file)

            # Open the temporary .csv and load the csv `writer`
            with salt.utils.files.fopen(f_temp.name, mode="w") as tmp_file:
                writer = csv.DictWriter(tmp_file, fieldnames=reader.fieldnames)

                # Write the header values (labels)
                writer.writeheader()

                value_written = False
                # Loop through the current audit.csv and write the changes to
                # the temp csv file for existing settings
                for row in reader:
                    # If the row matches the value we're setting, update it with
                    # the new value
                    if row["Subcategory"] == option:
                        if not value == "None":
                            # The value is not None, make the change
                            row["Inclusion Setting"] = auditpol_values[value]
                            row["Setting Value"] = value
                            log.trace(
                                "LGPO: Setting {0} to {1}" "".format(option, value)
                            )
                            writer.writerow(row)
                        else:
                            # value is None, remove it by not writing it to the
                            # temp file
                            log.trace("LGPO: Removing {0}".format(option))
                        value_written = True
                    # If it's not the value we're setting, just write it
                    else:
                        writer.writerow(row)

                # If a value was not written, it is a new setting not found in
                # the existing audit.cvs file. Add the new setting with values
                # from the defaults
                if not value_written:
                    if not value == "None":
                        # value is not None, write the new value
                        log.trace("LGPO: Setting {0} to {1}" "".format(option, value))
                        defaults = _get_advaudit_defaults(option)
                        writer.writerow(
                            {
                                "Machine Name": defaults["Machine Name"],
                                "Policy Target": defaults["Policy Target"],
                                "Subcategory": defaults["Subcategory"],
                                "Subcategory GUID": defaults["Subcategory GUID"],
                                "Inclusion Setting": auditpol_values[value],
                                "Exclusion Setting": defaults["Exclusion Setting"],
                                "Setting Value": value,
                            }
                        )
                    value_written = True

        if value_written:
            # Copy the temporary csv file over the existing audit.csv in both
            # locations if a value was written
            __salt__["file.copy"](f_temp.name, f_audit, remove_existing=True)
            __salt__["file.makedirs"](f_audit_gpo)
            __salt__["file.copy"](f_temp.name, f_audit_gpo, remove_existing=True)
    finally:
        f_temp.close()
        __salt__["file.remove"](f_temp.name)

    return value_written


def _set_advaudit_pol_data(option, value):
    """
    Helper function that updates the current applied settings to match what has
    just been set in the audit.csv files. We're doing it this way instead of
    running `gpupdate`

    Args:
        option (str): The name of the option to set
        value (str): The value to set. ['None', '0', '1', '2', '3']

    Returns:
        bool: ``True`` if successful, otherwise ``False``
    """
    auditpol_values = {
        "None": "No Auditing",
        "0": "No Auditing",
        "1": "Success",
        "2": "Failure",
        "3": "Success and Failure",
    }
    defaults = _get_advaudit_defaults(option)
    return __utils__["auditpol.set_setting"](
        name=defaults["Auditpol Name"], value=auditpol_values[value]
    )


def _set_advaudit_value(option, value):
    """
    Helper function to update the Advanced Audit policy on the machine. This
    function modifies the two ``audit.csv`` files in the following locations:

    C:\\Windows\\Security\\Audit\\audit.csv
    C:\\Windows\\System32\\GroupPolicy\\Machine\\Microsoft\\Windows NT\\Audit\\audit.csv

    Then it applies those settings using ``auditpol``

    After that, it updates ``__context__`` with the new setting

    Args:
        option (str): The name of the option to set
        value (str): The value to set. ['None', '0', '1', '2', '3']

    Returns:
        bool: ``True`` if successful, otherwise ``False``
    """
    # Set the values in both audit.csv files
    if not _set_audit_file_data(option=option, value=value):
        raise CommandExecutionError(
            "Failed to set audit.csv option: {0}" "".format(option)
        )
    # Apply the settings locally
    if not _set_advaudit_pol_data(option=option, value=value):
        # Only log this error, it will be in effect the next time the machine
        # updates its policy
        log.error(
            "Failed to apply audit setting: {0}\n"
            "Policy will take effect on next GPO update".format(option)
        )

    # Update __context__
    if value is None:
        log.debug("LGPO: Removing Advanced Audit data: {0}".format(option))
        __context__["lgpo.adv_audit_data"].pop(option)
    else:
        log.debug(
            "LGPO: Updating Advanced Audit data: {0}: {1}" "".format(option, value)
        )
        __context__["lgpo.adv_audit_data"][option] = value

    return True


def _get_netsh_value(profile, option):
    if "lgpo.netsh_data" not in __context__:
        __context__["lgpo.netsh_data"] = {}

    if profile not in __context__["lgpo.netsh_data"]:
        log.debug("LGPO: Loading netsh data for {0} profile".format(profile))
        settings = salt.utils.win_lgpo_netsh.get_all_settings(
            profile=profile, store="lgpo"
        )
        __context__["lgpo.netsh_data"].update({profile: settings})
    log.trace(
        "LGPO: netsh returning value: {0}"
        "".format(__context__["lgpo.netsh_data"][profile][option])
    )
    return __context__["lgpo.netsh_data"][profile][option]


def _set_netsh_value(profile, section, option, value):
    if section not in ("firewallpolicy", "settings", "logging", "state"):
        raise ValueError("LGPO: Invalid section: {0}".format(section))
    log.trace(
        "LGPO: Setting the following\n"
        "Profile: {0}\n"
        "Section: {1}\n"
        "Option: {2}\n"
        "Value: {3}".format(profile, section, option, value)
    )
    if section == "firewallpolicy":
        salt.utils.win_lgpo_netsh.set_firewall_settings(
            profile=profile,
            inbound=value if option == "Inbound" else None,
            outbound=value if option == "Outbound" else None,
            store="lgpo",
        )
    if section == "settings":
        salt.utils.win_lgpo_netsh.set_settings(
            profile=profile, setting=option, value=value, store="lgpo"
        )
    if section == "state":
        salt.utils.win_lgpo_netsh.set_state(profile=profile, state=value, store="lgpo")
    if section == "logging":
        if option in ("FileName", "MaxFileSize"):
            if value == "Not configured":
                value = "notconfigured"
        # Trim log for the two logging options
        if option.startswith("Log"):
            option = option[3:]
        salt.utils.win_lgpo_netsh.set_logging_settings(
            profile=profile, setting=option, value=value, store="lgpo"
        )
    log.trace("LGPO: Clearing netsh data for {0} profile".format(profile))
    __context__["lgpo.netsh_data"].pop(profile)
    return True


def _load_secedit_data():
    """
    Helper function that loads secedit data. It runs `secedit /export /cfg
    <file_name>` which creates a file that contains the secedit data.

    Returns:
        str: The contents of the file generated by the secedit command
    """
    try:
        f_exp = os.path.join(__opts__["cachedir"], "secedit-{0}.txt".format(UUID))
        __salt__["cmd.run"](["secedit", "/export", "/cfg", f_exp])
        with io.open(f_exp, encoding="utf-16") as fp:
            secedit_data = fp.readlines()
        return secedit_data
    finally:
        if __salt__["file.file_exists"](f_exp):
            __salt__["file.remove"](f_exp)


def _get_secedit_data():
    """
    Helper function that returns the secedit data in __context__ if it exists
    and puts the secedit data in __context__ if it does not.

    Returns:
        str: secedit data from __context__
    """
    if "lgpo.secedit_data" not in __context__:
        log.debug("LGPO: Loading secedit data")
        __context__["lgpo.secedit_data"] = _load_secedit_data()
    return __context__["lgpo.secedit_data"]


def _get_secedit_value(option):
    """
    Helper function that looks for the passed option in the secedit data
    """
    secedit_data = _get_secedit_data()
    for _line in secedit_data:
        if _line.startswith(option):
            return _line.split("=")[1].strip()
    return "Not Defined"


def _write_secedit_data(inf_data):
    """
    Helper function to write secedit data to the database
    """
    # Set file names
    f_sdb = os.path.join(__opts__["cachedir"], "secedit-{0}.sdb".format(UUID))
    f_inf = os.path.join(__opts__["cachedir"], "secedit-{0}.inf".format(UUID))

    try:
        # Write the changes to the inf file
        __salt__["file.write"](f_inf, inf_data)
        # Run secedit to make the change
        cmd = ["secedit", "/configure", "/db", f_sdb, "/cfg", f_inf]
        retcode = __salt__["cmd.retcode"](cmd)
        # Success
        if retcode == 0:
            # Pop secedit data so it will always be current
            __context__.pop("lgpo.secedit_data", None)
            return True
        # Failure
        return False
    finally:
        # Cleanup our scratch files
        if __salt__["file.file_exists"](f_sdb):
            __salt__["file.remove"](f_sdb)
        if __salt__["file.file_exists"](f_inf):
            __salt__["file.remove"](f_inf)


def _transform_value(value, policy, transform_type):
    """
    helper function to transform the policy value into something that more
    closely matches how the policy is displayed in the gpedit GUI
    """
    t_kwargs = {}
    if "Transform" in policy:
        if transform_type in policy["Transform"]:
            _policydata = _policy_info()
            if transform_type + "Args" in policy["Transform"]:
                t_kwargs = policy["Transform"][transform_type + "Args"]
            return getattr(_policydata, policy["Transform"][transform_type])(
                value, **t_kwargs
            )
        else:
            return value
    else:
        if "Registry" in policy:
            if value == "(value not set)":
                return "Not Defined"
        return value


def _validateSetting(value, policy):
    """
    helper function to validate specified value is appropriate for the policy
    if the 'Settings' key is a list, the value will check that it is in the list
    if the 'Settings' key is a dict we will try to execute the function name
        from the 'Function' key, passing the value and additional arguments from
        the 'Args' dict
    if the 'Settings' key is None, we won't do any validation and just return
        True
    if the Policy has 'Children', we'll validate their settings too
    """
    log.debug("validating {0} for policy {1}".format(value, policy))
    if "Settings" in policy:
        if policy["Settings"]:
            if isinstance(policy["Settings"], list):
                if value not in policy["Settings"]:
                    return False
            elif isinstance(policy["Settings"], dict):
                _policydata = _policy_info()
                if not getattr(_policydata, policy["Settings"]["Function"])(
                    value, **policy["Settings"]["Args"]
                ):
                    return False
    else:
        return True

    return True


def _addAccountRights(sidObject, user_right):
    """
    helper function to add an account right to a user
    """
    try:
        if sidObject:
            _polHandle = win32security.LsaOpenPolicy(
                None, win32security.POLICY_ALL_ACCESS
            )
            user_rights_list = [user_right]
            _ret = win32security.LsaAddAccountRights(
                _polHandle, sidObject, user_rights_list
            )
        return True
    # TODO: This needs to be more specific
    except Exception as e:  # pylint: disable=broad-except
        log.exception("Error attempting to add account right, exception was %s", e)
        return False


def _delAccountRights(sidObject, user_right):
    """
    helper function to remove an account right from a user
    """
    try:
        _polHandle = win32security.LsaOpenPolicy(None, win32security.POLICY_ALL_ACCESS)
        user_rights_list = [user_right]
        _ret = win32security.LsaRemoveAccountRights(
            _polHandle, sidObject, False, user_rights_list
        )
        return True
    except Exception as e:  # pylint: disable=broad-except
        log.exception("Error attempting to delete account right")
        return False


def _getRightsAssignments(user_right):
    """
    helper function to return all the user rights assignments/users
    """
    sids = []
    polHandle = win32security.LsaOpenPolicy(None, win32security.POLICY_ALL_ACCESS)
    sids = win32security.LsaEnumerateAccountsWithUserRight(polHandle, user_right)
    return sids


def _getAdmlDisplayName(adml_xml_data, display_name):
    """
    helper function to take the 'displayName' attribute of an element and find
    the value from the ADML data

    adml_xml_data :: XML data of all ADML files to search
    display_name :: the value of the displayName attribute from the ADMX entry
                    to search the ADML data for
    """
    if display_name.startswith("$(") and display_name.endswith(")"):
        display_name = re.sub(r"(^\$\(|\)$)", "", display_name)
        display_name = display_name.split(".")
        displayname_type = display_name[0]
        displayname_id = display_name[1]
        search_results = ADML_DISPLAY_NAME_XPATH(
            adml_xml_data,
            displayNameType=displayname_type,
            displayNameId=displayname_id,
        )
        if search_results:
            for result in search_results:
                # Needs the `strip()` because some adml data has an extra space
                # at the end
                return result.text.strip()

    return None


def _getAdmlPresentationRefId(adml_data, ref_id):
    """
    helper function to check for a presentation label for a policy element
    """
    search_results = adml_data.xpath(
        '//*[@*[local-name() = "refId"] = "{0}"]'.format(ref_id)
    )
    alternate_label = ""
    if search_results:
        for result in search_results:
            the_localname = etree.QName(result.tag).localname

            # We want to prefer result.text as the label, however, if it is none
            # we will fall back to this method for getting the label
            # Brings some code back from:
            # https://github.com/saltstack/salt/pull/55823/files#diff-b2e4dac5ccc17ab548f245371ec5d6faL5658
            if result.text is None:
                # Get the label from the text element above the referenced
                # element. For example:
                # --- taken from AppPrivacy.adml ---
                # <text>Force allow these specific apps (use Package Family Names):</text>
                # <multiTextBox refId="LetAppsSyncWithDevices_ForceAllowTheseApps_List"/>
                # In this case, the label for the refId is the text element
                # above it.
                presentation_element = PRESENTATION_ANCESTOR_XPATH(result)
                if presentation_element:
                    presentation_element = presentation_element[0]
                    if TEXT_ELEMENT_XPATH(presentation_element):
                        for p_item in presentation_element.getchildren():
                            if p_item == result:
                                break
                            if etree.QName(p_item.tag).localname == "text":
                                if getattr(p_item, "text"):
                                    alternate_label = getattr(p_item, "text").rstrip()
                        if alternate_label.endswith("."):
                            alternate_label = ""

            if the_localname in ["textBox", "comboBox"]:
                label_items = result.xpath('.//*[local-name() = "label"]')
                for label_item in label_items:
                    if label_item.text:
                        return label_item.text.rstrip().rstrip(":")
            elif the_localname in [
                "decimalTextBox",
                "longDecimalTextBox",
                "dropdownList",
                "listBox",
                "checkBox",
                "text",
                "multiTextBox",
            ]:
                if result.text:
                    return result.text.rstrip().rstrip(":")
                else:
                    return alternate_label.rstrip(":")
    return None


def _getFullPolicyName(
    policy_item, policy_name, return_full_policy_names, adml_language
):
    """
    helper function to retrieve the full policy name if needed
    """
    if policy_name in adm_policy_name_map[return_full_policy_names]:
        return adm_policy_name_map[return_full_policy_names][policy_name]
    adml_data = _get_policy_resources(language=adml_language)
    if return_full_policy_names and "displayName" in policy_item.attrib:
        fullPolicyName = _getAdmlDisplayName(
            adml_data, policy_item.attrib["displayName"]
        )
        if fullPolicyName:
            adm_policy_name_map[return_full_policy_names][policy_name] = fullPolicyName
            policy_name = fullPolicyName
    elif return_full_policy_names and "id" in policy_item.attrib:
        fullPolicyName = _getAdmlPresentationRefId(adml_data, policy_item.attrib["id"])
        if fullPolicyName:
            adm_policy_name_map[return_full_policy_names][policy_name] = fullPolicyName
            policy_name = fullPolicyName
    policy_name = policy_name.rstrip(":").rstrip()
    return policy_name


def _regexSearchRegPolData(search_string, policy_data):
    """
    helper function to do a search of Policy data from a registry.pol file
    returns True if the regex search_string is found, otherwise False
    """
    if policy_data:
        if search_string:
            match = re.search(search_string, policy_data, re.IGNORECASE)
            if match:
                return True
    return False


def _getDataFromRegPolData(search_string, policy_data, return_value_name=False):
    """
    helper function to do a search of Policy data from a registry.pol file
    returns the "data" field
    https://msdn.microsoft.com/en-us/library/aa374407(VS.85).aspx
    [key;value;type;size;data]
    """
    value = None
    values = []
    encoded_semicolon = ";".encode("utf-16-le")
    if return_value_name:
        values = {}
    if search_string:
        registry = Registry()
        if len(search_string.split(encoded_semicolon)) >= 3:
            vtype = registry.vtype_reverse[
                ord(search_string.split(encoded_semicolon)[2].decode("utf-32-le"))
            ]
        else:
            vtype = None
        search_string = re.escape(search_string)
        matches = re.finditer(search_string, policy_data, re.IGNORECASE)
        matches = [m for m in matches]
        if matches:
            for match in matches:
                pol_entry = policy_data[
                    match.start() : (
                        policy_data.index("]".encode("utf-16-le"), match.end())
                    )
                ].split(encoded_semicolon)
                if len(pol_entry) >= 2:
                    valueName = pol_entry[1].decode("utf-16-le").rstrip(chr(0))
                if len(pol_entry) >= 5:
                    # Sometimes a semicolon-separated value gets split into
                    # additional elements in the Registry.pol file. For example,
                    # a value of test1;test2;test3 will be 'test1', 'test2', and
                    # 'test3' at the end of the Registry.pol file entry
                    value = encoded_semicolon.join(pol_entry[4:])
                    if vtype == "REG_DWORD" or vtype == "REG_QWORD":
                        if value:
                            if vtype == "REG_DWORD":
                                for v in struct.unpack(b"I", value):
                                    value = v
                            elif vtype == "REG_QWORD":
                                for v in struct.unpack(b"Q", value):
                                    value = v
                        else:
                            value = 0
                    elif vtype == "REG_MULTI_SZ":
                        value = value.decode("utf-16-le").rstrip(chr(0)).split(chr(0))
                    else:
                        value = value.decode("utf-16-le").rstrip(chr(0))
                if return_value_name:
                    log.trace("we want value names and the value")
                    values[valueName] = value
                elif len(matches) > 1:
                    log.trace("we have multiple matches, we will return a list")
                    values.append(value)
    if values:
        value = values

    return value


def _checkListItem(
    policy_element,
    policy_name,
    policy_key,
    xpath_object,
    policy_file_data,
    test_items=True,
):
    """
    helper function to process an enabled/disabled/true/falseList set

    if test_items is True, it will determine if the policy is enabled or
    disabled returning True if all items are configured in the registry.pol file
    and false if they are not

    if test_items is False, the expected strings for the items will be returned
    as a list

    returns True if the enabled/disabledList is 100% configured in the
    registry.pol file, otherwise returns False
    """
    xpath_string = (
        './/*[local-name() = "decimal" or local-name() = "delete"'
        ' or local-name() = "longDecimal" or local-name() = "string"]'
    )
    value_item_child_xpath = etree.XPath(xpath_string)
    expected_strings = []
    for list_element in xpath_object(policy_element):
        configured_items = 0
        required_items = 0
        for item in list_element.getchildren():
            required_items = required_items + 1
            if "key" in item.attrib:
                item_key = item.attrib["key"]
            else:
                item_key = policy_key
            if "valueName" in item.attrib:
                item_valuename = item.attrib["valueName"]
            else:
                log.error(
                    "%s item with attributes %s in policy %s does not "
                    'have the required "valueName" attribute',
                    etree.QName(list_element).localname,
                    item.attrib,
                    policy_element.attrib,
                )
                break
            for value_item in value_item_child_xpath(item):
                search_string = _processValueItem(
                    value_item, item_key, item_valuename, policy_element, item
                )
                if test_items:
                    if _regexSearchRegPolData(
                        re.escape(search_string), policy_file_data
                    ):
                        configured_items = configured_items + 1
                        log.trace(
                            "found the search string in the pol file,"
                            "%s of %s items for policy %s are "
                            "configured in registry.pol",
                            configured_items,
                            required_items,
                            policy_name,
                        )
                else:
                    expected_strings.append(search_string)
        if test_items:
            if required_items > 0 and required_items == configured_items:
                log.trace("%s all items are set", policy_name)
                return True
    if test_items:
        return False
    else:
        return expected_strings


def _checkValueItemParent(
    policy_element,
    policy_name,
    policy_key,
    policy_valueName,
    xpath_object,
    policy_file_data,
    check_deleted=False,
    test_item=True,
):
    """
    helper function to process the parent of a value item object
    if test_item is True, it will determine if the policy is enabled/disabled
    returns True if the value is configured in the registry.pol file, otherwise returns False

    if test_item is False, the expected search string will be returned

    value type parents:
        boolean: https://msdn.microsoft.com/en-us/library/dn606009(v=vs.85).aspx
        enabledValue: https://msdn.microsoft.com/en-us/library/dn606006(v=vs.85).aspx
        disabledValue: https://msdn.microsoft.com/en-us/library/dn606001(v=vs.85).aspx

    """
    for element in xpath_object(policy_element):
        for value_item in element.getchildren():
            search_string = _processValueItem(
                value_item,
                policy_key,
                policy_valueName,
                policy_element,
                element,
                check_deleted=check_deleted,
            )
            if not test_item:
                return search_string
            if _regexSearchRegPolData(re.escape(search_string), policy_file_data):
                log.trace(
                    "found the search string in the pol file, " "%s is configured",
                    policy_name,
                )
                return True
    return False


def _encode_string(value):
    encoded_null = chr(0).encode("utf-16-le")
    if value is None:
        return encoded_null
    elif not isinstance(value, six.string_types):
        # Should we raise an error here, or attempt to cast to a string
        raise TypeError(
            "Value {0} is not a string type\n"
            "Type: {1}".format(repr(value), type(value))
        )
    return b"".join([value.encode("utf-16-le"), encoded_null])


def _buildKnownDataSearchString(
    reg_key, reg_valueName, reg_vtype, reg_data, check_deleted=False
):
    """
    helper function similar to _processValueItem to build a search string for a
    known key/value/type/data
    """
    registry = Registry()
    this_element_value = None
    expected_string = b""
    encoded_semicolon = ";".encode("utf-16-le")
    encoded_null = chr(0).encode("utf-16-le")
    if reg_key:
        reg_key = reg_key.encode("utf-16-le")
    if reg_valueName:
        reg_valueName = reg_valueName.encode("utf-16-le")
    if reg_data and not check_deleted:
        if reg_vtype == "REG_DWORD":
            this_element_value = struct.pack(b"I", int(reg_data))
        elif reg_vtype == "REG_QWORD":
            this_element_value = struct.pack(b"Q", int(reg_data))
        elif reg_vtype == "REG_SZ":
            this_element_value = _encode_string(reg_data)
    if check_deleted:
        reg_vtype = "REG_SZ"
        expected_string = b"".join(
            [
                "[".encode("utf-16-le"),
                reg_key,
                encoded_null,
                encoded_semicolon,
                "**del.".encode("utf-16-le"),
                reg_valueName,
                encoded_null,
                encoded_semicolon,
                chr(registry.vtype[reg_vtype]).encode("utf-32-le"),
                encoded_semicolon,
                six.unichr(len(" {0}".format(chr(0)).encode("utf-16-le"))).encode(
                    "utf-32-le"
                ),
                encoded_semicolon,
                " ".encode("utf-16-le"),
                encoded_null,
                "]".encode("utf-16-le"),
            ]
        )
    else:
        expected_string = b"".join(
            [
                "[".encode("utf-16-le"),
                reg_key,
                encoded_null,
                encoded_semicolon,
                reg_valueName,
                encoded_null,
                encoded_semicolon,
                chr(registry.vtype[reg_vtype]).encode("utf-32-le"),
                encoded_semicolon,
                six.unichr(len(this_element_value)).encode("utf-32-le"),
                encoded_semicolon,
                this_element_value,
                "]".encode("utf-16-le"),
            ]
        )
    return expected_string


def _processValueItem(
    element,
    reg_key,
    reg_valuename,
    policy,
    parent_element,
    check_deleted=False,
    this_element_value=None,
):
    """
    helper function to process a value type item and generate the expected
    string in the Registry.pol file

    element - the element to process
    reg_key - the registry key associated with the element (some inherit from
              their parent policy)
    reg_valuename - the registry valueName associated with the element (some
                    inherit from their parent policy)
    policy - the parent policy element
    parent_element - the parent element (primarily passed in to differentiate
                     children of "elements" objects
    check_deleted - if the returned expected string should be for a deleted
                    value
    this_element_value - a specific value to place into the expected string
                         returned for "elements" children whose values are
                         specified by the user
    """
    registry = Registry()
    expected_string = None
    # https://msdn.microsoft.com/en-us/library/dn606006(v=vs.85).aspx
    this_vtype = "REG_SZ"
    encoded_semicolon = ";".encode("utf-16-le")
    encoded_null = chr(0).encode("utf-16-le")
    if reg_key:
        reg_key = reg_key.encode("utf-16-le")
    if reg_valuename:
        reg_valuename = reg_valuename.encode("utf-16-le")
    if (
        etree.QName(element).localname == "decimal"
        and etree.QName(parent_element).localname != "elements"
    ):
        this_vtype = "REG_DWORD"
        if "value" in element.attrib:
            this_element_value = struct.pack(b"I", int(element.attrib["value"]))
        else:
            log.error(
                "The %s child %s element for the policy with "
                'attributes: %s does not have the required "value" '
                "attribute. The element attributes are: %s",
                etree.QName(parent_element).localname,
                etree.QName(element).localname,
                policy.attrib,
                element.attrib,
            )
            return None
    elif (
        etree.QName(element).localname == "longDecimal"
        and etree.QName(parent_element).localname != "elements"
    ):
        # WARNING: no longDecimals in current ADMX files included with 2012
        # server, so untested/assumed
        this_vtype = "REG_QWORD"
        if "value" in element.attrib:
            this_element_value = struct.pack(b"Q", int(element.attrib["value"]))
        else:
            log.error(
                "The %s child %s element for the policy with "
                'attributes: %s does not have the required "value" '
                "attribute. The element attributes are: %s",
                etree.QName(parent_element).localname,
                etree.QName(element).localname,
                policy.attrib,
                element.attrib,
            )
            return None
    elif etree.QName(element).localname == "string":
        this_vtype = "REG_SZ"
        this_element_value = _encode_string(element.text)
    elif etree.QName(parent_element).localname == "elements":
        standard_element_expected_string = True
        if etree.QName(element).localname == "boolean":
            # a boolean element that has no children will add a REG_DWORD == 1
            # on true or delete the value on false
            # https://msdn.microsoft.com/en-us/library/dn605978(v=vs.85).aspx
            if this_element_value is False:
                check_deleted = True
            if not check_deleted:
                this_vtype = "REG_DWORD"
            this_element_value = struct.pack("I", 1)
            standard_element_expected_string = False
        elif etree.QName(element).localname == "decimal":
            # https://msdn.microsoft.com/en-us/library/dn605987(v=vs.85).aspx
            this_vtype = "REG_DWORD"
            requested_val = this_element_value
            if this_element_value is not None:
                this_element_value = struct.pack(b"I", int(this_element_value))
            if "storeAsText" in element.attrib:
                if element.attrib["storeAsText"].lower() == "true":
                    this_vtype = "REG_SZ"
                    if requested_val is not None:
                        this_element_value = six.text_type(requested_val).encode(
                            "utf-16-le"
                        )
            if check_deleted:
                this_vtype = "REG_SZ"
        elif etree.QName(element).localname == "longDecimal":
            # https://msdn.microsoft.com/en-us/library/dn606015(v=vs.85).aspx
            this_vtype = "REG_QWORD"
            requested_val = this_element_value
            if this_element_value is not None:
                this_element_value = struct.pack(b"Q", int(this_element_value))
            if "storeAsText" in element.attrib:
                if element.attrib["storeAsText"].lower() == "true":
                    this_vtype = "REG_SZ"
                    if requested_val is not None:
                        this_element_value = six.text_type(requested_val).encode(
                            "utf-16-le"
                        )
        elif etree.QName(element).localname == "text":
            # https://msdn.microsoft.com/en-us/library/dn605969(v=vs.85).aspx
            this_vtype = "REG_SZ"
            if "expandable" in element.attrib:
                if element.attrib["expandable"].lower() == "true":
                    this_vtype = "REG_EXPAND_SZ"
            if this_element_value is not None:
                this_element_value = _encode_string(this_element_value)
        elif etree.QName(element).localname == "multiText":
            this_vtype = "REG_MULTI_SZ" if not check_deleted else "REG_SZ"
            if this_element_value is not None:
                this_element_value = "{0}{1}{1}".format(
                    chr(0).join(this_element_value), chr(0)
                )
        elif etree.QName(element).localname == "list":
            standard_element_expected_string = False
            del_keys = b""
            element_valuenames = []
            element_values = this_element_value
            if this_element_value is not None:
                element_valuenames = list(
                    [str(z) for z in range(1, len(this_element_value) + 1)]
                )
            if "additive" in element.attrib:
                if element.attrib["additive"].lower() == "false":
                    # a delete values will be added before all the other
                    # value = data pairs
                    del_keys = b"".join(
                        [
                            "[".encode("utf-16-le"),
                            reg_key,
                            encoded_null,
                            encoded_semicolon,
                            "**delvals.".encode("utf-16-le"),
                            encoded_null,
                            encoded_semicolon,
                            chr(registry.vtype[this_vtype]).encode("utf-32-le"),
                            encoded_semicolon,
                            six.unichr(
                                len(" {0}".format(chr(0)).encode("utf-16-le"))
                            ).encode("utf-32-le"),
                            encoded_semicolon,
                            " ".encode("utf-16-le"),
                            encoded_null,
                            "]".encode("utf-16-le"),
                        ]
                    )
            if "expandable" in element.attrib:
                this_vtype = "REG_EXPAND_SZ"
            if element.attrib.get("explicitValue", "false").lower() == "true":
                if this_element_value is not None:
                    element_valuenames = [str(k) for k in this_element_value.keys()]
                    element_values = [str(v) for v in this_element_value.values()]
            elif "valuePrefix" in element.attrib:
                # if the valuePrefix attribute exists, the valuenames are <prefix><number>
                # most prefixes attributes are empty in the admx files, so the valuenames
                # end up being just numbers
                if element.attrib["valuePrefix"] != "":
                    if this_element_value is not None:
                        element_valuenames = [
                            "{0}{1}".format(element.attrib["valuePrefix"], k)
                            for k in element_valuenames
                        ]
            else:
                # if there is no valuePrefix attribute, the valuename is the value
                if element_values is not None:
                    element_valuenames = [str(z) for z in element_values]
            if not check_deleted:
                if this_element_value is not None:
                    log.trace(
                        "_processValueItem has an explicit " "element_value of %s",
                        this_element_value,
                    )
                    expected_string = del_keys
                    log.trace(
                        "element_valuenames == %s and element_values " "== %s",
                        element_valuenames,
                        element_values,
                    )
                    for i, item in enumerate(element_valuenames):
                        expected_string = expected_string + b"".join(
                            [
                                "[".encode("utf-16-le"),
                                reg_key,
                                encoded_null,
                                encoded_semicolon,
                                element_valuenames[i].encode("utf-16-le"),
                                encoded_null,
                                encoded_semicolon,
                                chr(registry.vtype[this_vtype]).encode("utf-32-le"),
                                encoded_semicolon,
                                six.unichr(
                                    len(
                                        "{0}{1}".format(
                                            element_values[i], chr(0)
                                        ).encode("utf-16-le")
                                    )
                                ).encode("utf-32-le"),
                                encoded_semicolon,
                                _encode_string(element_values[i]),
                                "]".encode("utf-16-le"),
                            ]
                        )
                else:
                    expected_string = del_keys + b"".join(
                        [
                            "[".encode("utf-16-le"),
                            reg_key,
                            encoded_null,
                            encoded_semicolon,
                        ]
                    )
            else:
                expected_string = b"".join(
                    [
                        "[".encode("utf-16-le"),
                        reg_key,
                        encoded_null,
                        encoded_semicolon,
                        "**delvals.".encode("utf-16-le"),
                        encoded_null,
                        encoded_semicolon,
                        chr(registry.vtype[this_vtype]).encode("utf-32-le"),
                        encoded_semicolon,
                        six.unichr(
                            len(" {0}".format(chr(0)).encode("utf-16-le"))
                        ).encode("utf-32-le"),
                        encoded_semicolon,
                        " ".encode("utf-16-le"),
                        encoded_null,
                        "]".encode("utf-16-le"),
                    ]
                )
        elif etree.QName(element).localname == "enum":
            if this_element_value is not None:
                pass

        if standard_element_expected_string and not check_deleted:
            if this_element_value is not None:
                # Sometimes values come in as strings
                if isinstance(this_element_value, str):
                    log.debug("Converting {0} to bytes".format(this_element_value))
                    this_element_value = this_element_value.encode("utf-32-le")
                expected_string = b"".join(
                    [
                        "[".encode("utf-16-le"),
                        reg_key,
                        encoded_null,
                        encoded_semicolon,
                        reg_valuename,
                        encoded_null,
                        encoded_semicolon,
                        chr(registry.vtype[this_vtype]).encode("utf-32-le"),
                        encoded_semicolon,
                        six.unichr(len(this_element_value)).encode("utf-32-le"),
                        encoded_semicolon,
                        this_element_value,
                        "]".encode("utf-16-le"),
                    ]
                )
            else:
                expected_string = b"".join(
                    [
                        "[".encode("utf-16-le"),
                        reg_key,
                        encoded_null,
                        encoded_semicolon,
                        reg_valuename,
                        encoded_null,
                        encoded_semicolon,
                        chr(registry.vtype[this_vtype]).encode("utf-32-le"),
                        encoded_semicolon,
                    ]
                )

    if not expected_string:
        if etree.QName(element).localname == "delete" or check_deleted:
            # delete value
            expected_string = b"".join(
                [
                    "[".encode("utf-16-le"),
                    reg_key,
                    encoded_null,
                    encoded_semicolon,
                    "**del.".encode("utf-16-le"),
                    reg_valuename,
                    encoded_null,
                    encoded_semicolon,
                    chr(registry.vtype[this_vtype]).encode("utf-32-le"),
                    encoded_semicolon,
                    six.unichr(len(" {0}".format(chr(0)).encode("utf-16-le"))).encode(
                        "utf-32-le"
                    ),
                    encoded_semicolon,
                    " ".encode("utf-16-le"),
                    encoded_null,
                    "]".encode("utf-16-le"),
                ]
            )
        else:
            expected_string = b"".join(
                [
                    "[".encode("utf-16-le"),
                    reg_key,
                    encoded_null,
                    encoded_semicolon,
                    reg_valuename,
                    encoded_null,
                    encoded_semicolon,
                    chr(registry.vtype[this_vtype]).encode("utf-32-le"),
                    encoded_semicolon,
                    six.unichr(len(this_element_value)).encode("utf-32-le"),
                    encoded_semicolon,
                    this_element_value,
                    "]".encode("utf-16-le"),
                ]
            )
    return expected_string


def _checkAllAdmxPolicies(
    policy_class,
    adml_language="en-US",
    return_full_policy_names=False,
    hierarchical_return=False,
    return_not_configured=False,
):
    """
    rewrite of _getAllAdminTemplateSettingsFromRegPolFile where instead of
    looking only at the contents of the file, we're going to loop through every
    policy and look in the registry.pol file to determine if it is
    enabled/disabled/not configured
    """
    log.trace("POLICY CLASS == %s", policy_class)
    module_policy_data = _policy_info()
    policy_file_data = _read_regpol_file(
        module_policy_data.admx_registry_classes[policy_class]["policy_path"]
    )
    admx_policies = []
    policy_vals = {}
    hierarchy = {}
    full_names = {}
    admx_policy_definitions = _get_policy_definitions(language=adml_language)
    adml_policy_resources = _get_policy_resources(language=adml_language)
    if policy_file_data:
        log.trace("POLICY CLASS {0} has file data".format(policy_class))
        policy_filedata_split = re.sub(
            salt.utils.stringutils.to_bytes(r"\]{0}$".format(chr(0))),
            b"",
            re.sub(
                salt.utils.stringutils.to_bytes(r"^\[{0}".format(chr(0))),
                b"",
                re.sub(
                    re.escape(module_policy_data.reg_pol_header.encode("utf-16-le")),
                    b"",
                    policy_file_data,
                ),
            ),
        ).split("][".encode("utf-16-le"))
        log.trace("Searching %s policies...", len(policy_filedata_split))
        start_time = time.time()
        # Get the policy for each item defined in Registry.pol
        for policy_item in policy_filedata_split:
            policy_item_key = (
                policy_item.split("{0};".format(chr(0)).encode("utf-16-le"))[0]
                .decode("utf-16-le")
                .lower()
            )
            if policy_item_key:
                # Find the policy definitions with this key
                admx_items = REGKEY_XPATH(
                    admx_policy_definitions, keyvalue=policy_item_key
                )
                log.trace("Found %s policies for %s", len(admx_items), policy_item_key)
                for admx_item in admx_items:
                    # If this is a policy, append it to admx_policies
                    if etree.QName(admx_item).localname == "policy":
                        if admx_item not in admx_policies:
                            admx_policies.append(admx_item)
                    else:
                        # If this is not a policy, find the parent policy for this item
                        for policy_item in POLICY_ANCESTOR_XPATH(admx_item):
                            if policy_item not in admx_policies:
                                admx_policies.append(policy_item)
        log.trace("Search complete: %s seconds", time.time() - start_time)

        if return_not_configured:
            log.trace("Gathering non configured policies")
            start_time = time.time()
            not_configured_policies = ALL_CLASS_POLICY_XPATH(
                admx_policy_definitions, registry_class=policy_class
            )
            for policy_item in admx_policies:
                if policy_item in not_configured_policies:
                    not_configured_policies.remove(policy_item)

            for not_configured_policy in not_configured_policies:
                not_configured_policy_namespace = not_configured_policy.nsmap[
                    not_configured_policy.prefix
                ]
                if not_configured_policy_namespace not in policy_vals:
                    policy_vals[not_configured_policy_namespace] = {}
                policy_vals[not_configured_policy_namespace][
                    not_configured_policy.attrib["name"]
                ] = "Not Configured"
                if return_full_policy_names:
                    if not_configured_policy_namespace not in full_names:
                        full_names[not_configured_policy_namespace] = {}
                    full_names[not_configured_policy_namespace][
                        not_configured_policy.attrib["name"]
                    ] = _getFullPolicyName(
                        policy_item=not_configured_policy,
                        policy_name=not_configured_policy.attrib["name"],
                        return_full_policy_names=return_full_policy_names,
                        adml_language=adml_language,
                    )
                log.trace(
                    "building hierarchy for non-configured item %s",
                    not_configured_policy.attrib["name"],
                )
                if not_configured_policy_namespace not in hierarchy:
                    hierarchy[not_configured_policy_namespace] = {}
                hierarchy[not_configured_policy_namespace][
                    not_configured_policy.attrib["name"]
                ] = _build_parent_list(
                    policy_definition=not_configured_policy,
                    return_full_policy_names=return_full_policy_names,
                    adml_language=adml_language,
                )
            log.trace("Gathering complete: %s seconds", time.time() - start_time)

        log.trace("Examining %s policies...", len(admx_policies))
        start_time = time.time()
        for admx_policy in admx_policies:
            this_valuename = None
            this_policy_setting = "Not Configured"
            element_only_enabled_disabled = True
            explicit_enable_disable_value_setting = False

            if "key" in admx_policy.attrib:
                this_key = admx_policy.attrib["key"]
            else:
                log.error(
                    'policy item %s does not have the required "key" ' "attribute",
                    admx_policy.attrib,
                )
                break
            if "valueName" in admx_policy.attrib:
                this_valuename = admx_policy.attrib["valueName"]
            if "name" in admx_policy.attrib:
                this_policyname = admx_policy.attrib["name"]
            else:
                log.error(
                    'policy item %s does not have the required "name" ' "attribute",
                    admx_policy.attrib,
                )
                break
            this_policynamespace = admx_policy.nsmap[admx_policy.prefix]
            if (
                ENABLED_VALUE_XPATH(admx_policy)
                and this_policy_setting == "Not Configured"
            ):
                # some policies have a disabled list but not an enabled list
                # added this to address those issues
                if DISABLED_LIST_XPATH(admx_policy) or DISABLED_VALUE_XPATH(
                    admx_policy
                ):
                    element_only_enabled_disabled = False
                    explicit_enable_disable_value_setting = True
                if _checkValueItemParent(
                    admx_policy,
                    this_policyname,
                    this_key,
                    this_valuename,
                    ENABLED_VALUE_XPATH,
                    policy_file_data,
                ):
                    this_policy_setting = "Enabled"
                    log.trace(
                        "%s is enabled by detected ENABLED_VALUE_XPATH", this_policyname
                    )
                    if this_policynamespace not in policy_vals:
                        policy_vals[this_policynamespace] = {}
                    policy_vals[this_policynamespace][
                        this_policyname
                    ] = this_policy_setting
            if (
                DISABLED_VALUE_XPATH(admx_policy)
                and this_policy_setting == "Not Configured"
            ):
                # some policies have a disabled list but not an enabled list
                # added this to address those issues
                if ENABLED_LIST_XPATH(admx_policy) or ENABLED_VALUE_XPATH(admx_policy):
                    element_only_enabled_disabled = False
                    explicit_enable_disable_value_setting = True
                if _checkValueItemParent(
                    admx_policy,
                    this_policyname,
                    this_key,
                    this_valuename,
                    DISABLED_VALUE_XPATH,
                    policy_file_data,
                ):
                    this_policy_setting = "Disabled"
                    log.trace(
                        "%s is disabled by detected DISABLED_VALUE_XPATH",
                        this_policyname,
                    )
                    if this_policynamespace not in policy_vals:
                        policy_vals[this_policynamespace] = {}
                    policy_vals[this_policynamespace][
                        this_policyname
                    ] = this_policy_setting
            if (
                ENABLED_LIST_XPATH(admx_policy)
                and this_policy_setting == "Not Configured"
            ):
                if DISABLED_LIST_XPATH(admx_policy) or DISABLED_VALUE_XPATH(
                    admx_policy
                ):
                    element_only_enabled_disabled = False
                    explicit_enable_disable_value_setting = True
                if _checkListItem(
                    admx_policy,
                    this_policyname,
                    this_key,
                    ENABLED_LIST_XPATH,
                    policy_file_data,
                ):
                    this_policy_setting = "Enabled"
                    log.trace(
                        "%s is enabled by detected ENABLED_LIST_XPATH", this_policyname
                    )
                    if this_policynamespace not in policy_vals:
                        policy_vals[this_policynamespace] = {}
                    policy_vals[this_policynamespace][
                        this_policyname
                    ] = this_policy_setting
            if (
                DISABLED_LIST_XPATH(admx_policy)
                and this_policy_setting == "Not Configured"
            ):
                if ENABLED_LIST_XPATH(admx_policy) or ENABLED_VALUE_XPATH(admx_policy):
                    element_only_enabled_disabled = False
                    explicit_enable_disable_value_setting = True
                if _checkListItem(
                    admx_policy,
                    this_policyname,
                    this_key,
                    DISABLED_LIST_XPATH,
                    policy_file_data,
                ):
                    this_policy_setting = "Disabled"
                    log.trace(
                        "%s is disabled by detected DISABLED_LIST_XPATH",
                        this_policyname,
                    )
                    if this_policynamespace not in policy_vals:
                        policy_vals[this_policynamespace] = {}
                    policy_vals[this_policynamespace][
                        this_policyname
                    ] = this_policy_setting

            if not explicit_enable_disable_value_setting and this_valuename:
                # the policy has a key/valuename but no explicit enabled/Disabled
                # Value or List
                # these seem to default to a REG_DWORD 1 = "Enabled" **del. = "Disabled"
                if _regexSearchRegPolData(
                    re.escape(
                        _buildKnownDataSearchString(
                            this_key, this_valuename, "REG_DWORD", "1"
                        )
                    ),
                    policy_file_data,
                ):
                    this_policy_setting = "Enabled"
                    log.trace(
                        "%s is enabled by no explicit enable/disable list or value",
                        this_policyname,
                    )
                    if this_policynamespace not in policy_vals:
                        policy_vals[this_policynamespace] = {}
                    policy_vals[this_policynamespace][
                        this_policyname
                    ] = this_policy_setting
                elif _regexSearchRegPolData(
                    re.escape(
                        _buildKnownDataSearchString(
                            this_key,
                            this_valuename,
                            "REG_DWORD",
                            None,
                            check_deleted=True,
                        )
                    ),
                    policy_file_data,
                ):
                    this_policy_setting = "Disabled"
                    log.trace(
                        "%s is disabled by no explicit enable/disable list or value",
                        this_policyname,
                    )
                    if this_policynamespace not in policy_vals:
                        policy_vals[this_policynamespace] = {}
                    policy_vals[this_policynamespace][
                        this_policyname
                    ] = this_policy_setting

            if ELEMENTS_XPATH(admx_policy):
                if element_only_enabled_disabled or this_policy_setting == "Enabled":
                    # TODO does this need to be modified based on the 'required' attribute?
                    required_elements = {}
                    configured_elements = {}
                    policy_disabled_elements = 0
                    for elements_item in ELEMENTS_XPATH(admx_policy):
                        for child_item in elements_item.getchildren():
                            this_element_name = _getFullPolicyName(
                                policy_item=child_item,
                                policy_name=child_item.attrib["id"],
                                return_full_policy_names=return_full_policy_names,
                                adml_language=adml_language,
                            )
                            required_elements[this_element_name] = None
                            child_key = child_item.attrib.get("key", this_key)
                            child_valuename = child_item.attrib.get(
                                "valueName", this_valuename
                            )

                            if etree.QName(child_item).localname == "boolean":
                                # https://msdn.microsoft.com/en-us/library/dn605978(v=vs.85).aspx
                                if child_item.getchildren():
                                    if (
                                        TRUE_VALUE_XPATH(child_item)
                                        and this_element_name not in configured_elements
                                    ):
                                        if _checkValueItemParent(
                                            child_item,
                                            this_policyname,
                                            child_key,
                                            child_valuename,
                                            TRUE_VALUE_XPATH,
                                            policy_file_data,
                                        ):
                                            configured_elements[
                                                this_element_name
                                            ] = True
                                            log.trace(
                                                "element %s is configured true",
                                                child_item.attrib["id"],
                                            )
                                    if (
                                        FALSE_VALUE_XPATH(child_item)
                                        and this_element_name not in configured_elements
                                    ):
                                        if _checkValueItemParent(
                                            child_item,
                                            this_policyname,
                                            child_key,
                                            child_valuename,
                                            FALSE_VALUE_XPATH,
                                            policy_file_data,
                                        ):
                                            configured_elements[
                                                this_element_name
                                            ] = False
                                            policy_disabled_elements = (
                                                policy_disabled_elements + 1
                                            )
                                            log.trace(
                                                "element %s is configured false",
                                                child_item.attrib["id"],
                                            )
                                    # WARNING - no standard ADMX files use true/falseList
                                    # so this hasn't actually been tested
                                    if (
                                        TRUE_LIST_XPATH(child_item)
                                        and this_element_name not in configured_elements
                                    ):
                                        log.trace("checking trueList")
                                        if _checkListItem(
                                            child_item,
                                            this_policyname,
                                            this_key,
                                            TRUE_LIST_XPATH,
                                            policy_file_data,
                                        ):
                                            configured_elements[
                                                this_element_name
                                            ] = True
                                            log.trace(
                                                "element %s is configured true",
                                                child_item.attrib["id"],
                                            )
                                    if (
                                        FALSE_LIST_XPATH(child_item)
                                        and this_element_name not in configured_elements
                                    ):
                                        log.trace("checking falseList")
                                        if _checkListItem(
                                            child_item,
                                            this_policyname,
                                            this_key,
                                            FALSE_LIST_XPATH,
                                            policy_file_data,
                                        ):
                                            configured_elements[
                                                this_element_name
                                            ] = False
                                            policy_disabled_elements = (
                                                policy_disabled_elements + 1
                                            )
                                            log.trace(
                                                "element %s is configured false",
                                                child_item.attrib["id"],
                                            )
                                else:
                                    if _regexSearchRegPolData(
                                        re.escape(
                                            _processValueItem(
                                                child_item,
                                                child_key,
                                                child_valuename,
                                                admx_policy,
                                                elements_item,
                                                check_deleted=True,
                                            )
                                        ),
                                        policy_file_data,
                                    ):
                                        configured_elements[this_element_name] = False
                                        policy_disabled_elements = (
                                            policy_disabled_elements + 1
                                        )
                                        log.trace(
                                            "element %s is configured false",
                                            child_item.attrib["id"],
                                        )
                                    elif _regexSearchRegPolData(
                                        re.escape(
                                            _processValueItem(
                                                child_item,
                                                child_key,
                                                child_valuename,
                                                admx_policy,
                                                elements_item,
                                                check_deleted=False,
                                            )
                                        ),
                                        policy_file_data,
                                    ):
                                        configured_elements[this_element_name] = True
                                        log.trace(
                                            "element %s is configured true",
                                            child_item.attrib["id"],
                                        )
                            elif (
                                etree.QName(child_item).localname == "decimal"
                                or etree.QName(child_item).localname == "text"
                                or etree.QName(child_item).localname == "longDecimal"
                                or etree.QName(child_item).localname == "multiText"
                            ):
                                # https://msdn.microsoft.com/en-us/library/dn605987(v=vs.85).aspx
                                if _regexSearchRegPolData(
                                    re.escape(
                                        _processValueItem(
                                            child_item,
                                            child_key,
                                            child_valuename,
                                            admx_policy,
                                            elements_item,
                                            check_deleted=True,
                                        )
                                    ),
                                    policy_file_data,
                                ):
                                    configured_elements[this_element_name] = "Disabled"
                                    policy_disabled_elements = (
                                        policy_disabled_elements + 1
                                    )
                                    log.trace(
                                        "element %s is disabled",
                                        child_item.attrib["id"],
                                    )
                                elif _regexSearchRegPolData(
                                    re.escape(
                                        _processValueItem(
                                            child_item,
                                            child_key,
                                            child_valuename,
                                            admx_policy,
                                            elements_item,
                                            check_deleted=False,
                                        )
                                    ),
                                    policy_file_data,
                                ):
                                    configured_value = _getDataFromRegPolData(
                                        _processValueItem(
                                            child_item,
                                            child_key,
                                            child_valuename,
                                            admx_policy,
                                            elements_item,
                                            check_deleted=False,
                                        ),
                                        policy_file_data,
                                    )
                                    configured_elements[
                                        this_element_name
                                    ] = configured_value
                                    log.trace(
                                        "element %s is enabled, value == %s",
                                        child_item.attrib["id"],
                                        configured_value,
                                    )
                            elif etree.QName(child_item).localname == "enum":
                                if _regexSearchRegPolData(
                                    re.escape(
                                        _processValueItem(
                                            child_item,
                                            child_key,
                                            child_valuename,
                                            admx_policy,
                                            elements_item,
                                            check_deleted=True,
                                        )
                                    ),
                                    policy_file_data,
                                ):
                                    log.trace(
                                        "enum element %s is disabled",
                                        child_item.attrib["id"],
                                    )
                                    configured_elements[this_element_name] = "Disabled"
                                    policy_disabled_elements = (
                                        policy_disabled_elements + 1
                                    )
                                else:
                                    for enum_item in child_item.getchildren():
                                        if _checkValueItemParent(
                                            enum_item,
                                            child_item.attrib["id"],
                                            child_key,
                                            child_valuename,
                                            VALUE_XPATH,
                                            policy_file_data,
                                        ):
                                            if VALUE_LIST_XPATH(enum_item):
                                                log.trace("enum item has a valueList")
                                                if _checkListItem(
                                                    enum_item,
                                                    this_policyname,
                                                    child_key,
                                                    VALUE_LIST_XPATH,
                                                    policy_file_data,
                                                ):
                                                    log.trace(
                                                        "all valueList items exist in file"
                                                    )
                                                    configured_elements[
                                                        this_element_name
                                                    ] = _getAdmlDisplayName(
                                                        adml_policy_resources,
                                                        enum_item.attrib["displayName"],
                                                    )
                                                    break
                                            else:
                                                configured_elements[
                                                    this_element_name
                                                ] = _getAdmlDisplayName(
                                                    adml_policy_resources,
                                                    enum_item.attrib["displayName"],
                                                )
                                                break
                            elif etree.QName(child_item).localname == "list":
                                return_value_name = False
                                if (
                                    "explicitValue" in child_item.attrib
                                    and child_item.attrib["explicitValue"].lower()
                                    == "true"
                                ):
                                    log.trace(
                                        "explicitValue list, we will return value names"
                                    )
                                    return_value_name = True
                                if _regexSearchRegPolData(
                                    re.escape(
                                        _processValueItem(
                                            child_item,
                                            child_key,
                                            child_valuename,
                                            admx_policy,
                                            elements_item,
                                            check_deleted=False,
                                        )
                                    )
                                    + salt.utils.stringutils.to_bytes(
                                        r"(?!\*\*delvals\.)"
                                    ),
                                    policy_file_data,
                                ):
                                    configured_value = _getDataFromRegPolData(
                                        _processValueItem(
                                            child_item,
                                            child_key,
                                            child_valuename,
                                            admx_policy,
                                            elements_item,
                                            check_deleted=False,
                                        ),
                                        policy_file_data,
                                        return_value_name=return_value_name,
                                    )
                                    configured_elements[
                                        this_element_name
                                    ] = configured_value
                                    log.trace(
                                        "element %s is enabled values: %s",
                                        child_item.attrib["id"],
                                        configured_value,
                                    )
                                elif _regexSearchRegPolData(
                                    re.escape(
                                        _processValueItem(
                                            child_item,
                                            child_key,
                                            child_valuename,
                                            admx_policy,
                                            elements_item,
                                            check_deleted=True,
                                        )
                                    ),
                                    policy_file_data,
                                ):
                                    configured_elements[this_element_name] = "Disabled"
                                    policy_disabled_elements = (
                                        policy_disabled_elements + 1
                                    )
                                    log.trace(
                                        "element {0} is disabled".format(
                                            child_item.attrib["id"]
                                        )
                                    )
                    if element_only_enabled_disabled:
                        if len(required_elements.keys()) > 0 and len(
                            configured_elements.keys()
                        ) == len(required_elements.keys()):
                            if policy_disabled_elements == len(
                                required_elements.keys()
                            ):
                                log.trace(
                                    "{0} is disabled by all enum elements".format(
                                        this_policyname
                                    )
                                )
                                if this_policynamespace not in policy_vals:
                                    policy_vals[this_policynamespace] = {}
                                policy_vals[this_policynamespace][
                                    this_policyname
                                ] = "Disabled"
                            else:
                                if this_policynamespace not in policy_vals:
                                    policy_vals[this_policynamespace] = {}
                                policy_vals[this_policynamespace][
                                    this_policyname
                                ] = configured_elements
                                log.trace(
                                    "{0} is enabled by enum elements".format(
                                        this_policyname
                                    )
                                )
                    else:
                        if this_policy_setting == "Enabled":
                            if this_policynamespace not in policy_vals:
                                policy_vals[this_policynamespace] = {}
                            policy_vals[this_policynamespace][
                                this_policyname
                            ] = configured_elements
            if (
                return_full_policy_names
                and this_policynamespace in policy_vals
                and this_policyname in policy_vals[this_policynamespace]
            ):
                if this_policynamespace not in full_names:
                    full_names[this_policynamespace] = {}
                full_names[this_policynamespace][this_policyname] = _getFullPolicyName(
                    policy_item=admx_policy,
                    policy_name=admx_policy.attrib["name"],
                    return_full_policy_names=return_full_policy_names,
                    adml_language=adml_language,
                )
                # Make sure the we're passing the full policy name
                # This issue was found when setting the `Allow Telemetry` setting
                # All following states would show a change in this setting
                # When the state does it's first `lgpo.get` it would return `AllowTelemetry`
                # On the second run, it would return `Allow Telemetry`
                # This makes sure we're always returning the full_name when required
                if (
                    this_policyname
                    in policy_vals[this_policynamespace][this_policyname]
                ):
                    full_name = full_names[this_policynamespace][this_policyname]
                    setting = policy_vals[this_policynamespace][this_policyname].pop(
                        this_policyname
                    )
                    policy_vals[this_policynamespace][this_policyname][
                        full_name
                    ] = setting
            if (
                this_policynamespace in policy_vals
                and this_policyname in policy_vals[this_policynamespace]
            ):
                if this_policynamespace not in hierarchy:
                    hierarchy[this_policynamespace] = {}
                hierarchy[this_policynamespace][this_policyname] = _build_parent_list(
                    policy_definition=admx_policy,
                    return_full_policy_names=return_full_policy_names,
                    adml_language=adml_language,
                )
        log.trace("Examination complete: %s seconds", time.time() - start_time)
    if policy_vals and return_full_policy_names and not hierarchical_return:
        log.debug("Compiling non hierarchical return...")
        start_time = time.time()
        unpathed_dict = {}
        pathed_dict = {}
        for policy_namespace in list(policy_vals):
            for policy_item in list(policy_vals[policy_namespace]):
                if (
                    full_names[policy_namespace][policy_item]
                    in policy_vals[policy_namespace]
                ):
                    # add this item with the path'd full name
                    full_path_list = hierarchy[policy_namespace][policy_item]
                    full_path_list.reverse()
                    full_path_list.append(full_names[policy_namespace][policy_item])
                    policy_vals["\\".join(full_path_list)] = policy_vals[
                        policy_namespace
                    ].pop(policy_item)
                    pathed_dict[full_names[policy_namespace][policy_item]] = True
                else:
                    policy_vals[policy_namespace][
                        full_names[policy_namespace][policy_item]
                    ] = policy_vals[policy_namespace].pop(policy_item)
                    if policy_namespace not in unpathed_dict:
                        unpathed_dict[policy_namespace] = {}
                    unpathed_dict[policy_namespace][
                        full_names[policy_namespace][policy_item]
                    ] = policy_item
            # go back and remove any "unpathed" policies that need a full path
            if policy_namespace in unpathed_dict:
                for path_needed in unpathed_dict[policy_namespace]:
                    # remove the item with the same full name and re-add it w/a path'd version
                    full_path_list = hierarchy[policy_namespace][
                        unpathed_dict[policy_namespace][path_needed]
                    ]
                    full_path_list.reverse()
                    full_path_list.append(path_needed)
                    log.trace("full_path_list == %s", full_path_list)
                    policy_vals["\\".join(full_path_list)] = policy_vals[
                        policy_namespace
                    ].pop(path_needed)
        log.trace("Compilation complete: %s seconds", time.time() - start_time)
    for policy_namespace in list(policy_vals):
        if policy_vals[policy_namespace] == {}:
            policy_vals.pop(policy_namespace)
    if policy_vals and hierarchical_return:
        if hierarchy:
            log.debug("Compiling hierarchical return...")
            start_time = time.time()
            for policy_namespace in hierarchy:
                for hierarchy_item in hierarchy[policy_namespace]:
                    if hierarchy_item in policy_vals[policy_namespace]:
                        tdict = {}
                        first_item = True
                        for item in hierarchy[policy_namespace][hierarchy_item]:
                            newdict = {}
                            if first_item:
                                h_policy_name = hierarchy_item
                                if return_full_policy_names:
                                    h_policy_name = full_names[policy_namespace][
                                        hierarchy_item
                                    ]
                                newdict[item] = {
                                    h_policy_name: policy_vals[policy_namespace].pop(
                                        hierarchy_item
                                    )
                                }
                                first_item = False
                            else:
                                newdict[item] = tdict
                            tdict = newdict
                        if tdict:
                            policy_vals = dictupdate.update(policy_vals, tdict)
                if (
                    policy_namespace in policy_vals
                    and policy_vals[policy_namespace] == {}
                ):
                    policy_vals.pop(policy_namespace)
            log.trace("Compilation complete: %s seconds", time.time() - start_time)
        policy_vals = {
            module_policy_data.admx_registry_classes[policy_class]["lgpo_section"]: {
                "Administrative Templates": policy_vals
            }
        }
    return policy_vals


def _build_parent_list(policy_definition, return_full_policy_names, adml_language):
    """
    helper function to build a list containing parent elements of the ADMX
    policy
    """
    parent_list = []
    policy_namespace = list(policy_definition.nsmap.keys())[0]
    parent_category = policy_definition.xpath(
        "{0}:parentCategory/@ref".format(policy_namespace),
        namespaces=policy_definition.nsmap,
    )
    admx_policy_definitions = _get_policy_definitions(language=adml_language)
    if parent_category:
        parent_category = parent_category[0]
        nsmap_xpath = "/policyDefinitions/policyNamespaces/{0}:*" "".format(
            policy_namespace
        )
        this_namespace_map = _buildElementNsmap(
            admx_policy_definitions.xpath(
                nsmap_xpath, namespaces=policy_definition.nsmap
            )
        )
        this_namespace_map = dictupdate.update(
            this_namespace_map, policy_definition.nsmap
        )
        parent_list = _admx_policy_parent_walk(
            path=parent_list,
            policy_namespace=policy_namespace,
            parent_category=parent_category,
            policy_nsmap=this_namespace_map,
            return_full_policy_names=return_full_policy_names,
            adml_language=adml_language,
        )
    return parent_list


def _admx_policy_parent_walk(
    path,
    policy_namespace,
    parent_category,
    policy_nsmap,
    return_full_policy_names,
    adml_language,
):
    """
    helper function to recursively walk up the ADMX namespaces and build the
    hierarchy for the policy
    """
    admx_policy_definitions = _get_policy_definitions(language=adml_language)
    category_xpath_string = '/policyDefinitions/categories/{0}:category[@name="{1}"]'
    using_xpath_string = "/policyDefinitions/policyNamespaces/{0}:using"
    if parent_category.find(":") >= 0:
        # the parent is in another namespace
        policy_namespace = parent_category.split(":")[0]
        parent_category = parent_category.split(":")[1]
        using_xpath_string = using_xpath_string.format(policy_namespace)
        policy_nsmap = dictupdate.update(
            policy_nsmap,
            _buildElementNsmap(
                admx_policy_definitions.xpath(
                    using_xpath_string, namespaces=policy_nsmap
                )
            ),
        )
    category_xpath_string = category_xpath_string.format(
        policy_namespace, parent_category
    )
    if admx_policy_definitions.xpath(category_xpath_string, namespaces=policy_nsmap):
        tparent_category = admx_policy_definitions.xpath(
            category_xpath_string, namespaces=policy_nsmap
        )[0]
        this_parent_name = _getFullPolicyName(
            policy_item=tparent_category,
            policy_name=tparent_category.attrib["name"],
            return_full_policy_names=return_full_policy_names,
            adml_language=adml_language,
        )
        path.append(this_parent_name)
        if tparent_category.xpath(
            "{0}:parentCategory/@ref".format(policy_namespace), namespaces=policy_nsmap
        ):
            # parent has a parent
            path = _admx_policy_parent_walk(
                path=path,
                policy_namespace=policy_namespace,
                parent_category=tparent_category.xpath(
                    "{0}:parentCategory/@ref".format(policy_namespace),
                    namespaces=policy_nsmap,
                )[0],
                policy_nsmap=policy_nsmap,
                return_full_policy_names=return_full_policy_names,
                adml_language=adml_language,
            )
    return path


def _read_regpol_file(reg_pol_path):
    """
    helper function to read a reg policy file and return decoded data
    """
    returndata = None
    if os.path.exists(reg_pol_path):
        with salt.utils.files.fopen(reg_pol_path, "rb") as pol_file:
            returndata = pol_file.read()
    return returndata


def _regexSearchKeyValueCombo(policy_data, policy_regpath, policy_regkey):
    """
    helper function to do a search of Policy data from a registry.pol file
    for a policy_regpath and policy_regkey combo
    """
    if policy_data:
        regex_str = [
            r"(\*",
            r"\*",
            "D",
            "e",
            "l",
            r"\.",
            r"|\*",
            r"\*",
            "D",
            "e",
            "l",
            "V",
            "a",
            "l",
            "s",
            r"\.",
            "){0,1}",
        ]
        specialValueRegex = "\x00".join(regex_str)
        specialValueRegex = salt.utils.stringutils.to_bytes(specialValueRegex)
        _thisSearch = b"".join(
            [
                salt.utils.stringutils.to_bytes(r"\["),
                re.escape(policy_regpath),
                b"\x00;\x00",
                specialValueRegex,
                re.escape(policy_regkey.lstrip(b"\x00")),
                b"\x00;",
            ]
        )
        match = re.search(_thisSearch, policy_data, re.IGNORECASE)
        if match:
            # add 2 so we get the ']' and the \00
            # to return the full policy entry
            return policy_data[
                match.start() : (policy_data.index(b"]", match.end())) + 2
            ]

    return None


def _write_regpol_data(
    data_to_write, policy_file_path, gpt_ini_path, gpt_extension, gpt_extension_guid
):
    """
    helper function to actually write the data to a Registry.pol file

    also updates/edits the gpt.ini file to include the ADM policy extensions
    to let the computer know user and/or machine registry policy files need
    to be processed

    data_to_write: data to write into the user/machine registry.pol file
    policy_file_path: path to the registry.pol file
    gpt_ini_path: path to gpt.ini file
    gpt_extension: gpt extension list name from _policy_info class for this registry class gpt_extension_location
    gpt_extension_guid: admx registry extension guid for the class
    """
    # Write Registry.pol file
    if not os.path.exists(policy_file_path):
        __salt__["file.makedirs"](policy_file_path)
    try:
        with salt.utils.files.fopen(policy_file_path, "wb") as pol_file:
            reg_pol_header = "\u5250\u6765\x01\x00".encode("utf-16-le")
            if not data_to_write.startswith(reg_pol_header):
                pol_file.write(reg_pol_header)
            pol_file.write(data_to_write)
    # TODO: This needs to be more specific
    except Exception as e:  # pylint: disable=broad-except
        msg = (
            "An error occurred attempting to write to {0}, the exception "
            "was: {1}".format(policy_file_path, e)
        )
        log.exception(msg)
        raise CommandExecutionError(msg)

    # Write the gpt.ini file
    gpt_ini_data = ""
    if os.path.exists(gpt_ini_path):
        with salt.utils.files.fopen(gpt_ini_path, "r") as gpt_file:
            gpt_ini_data = gpt_file.read()
    if not _regexSearchRegPolData(r"\[General\]\r\n", gpt_ini_data):
        gpt_ini_data = "[General]\r\n" + gpt_ini_data
    if _regexSearchRegPolData(r"{0}=".format(re.escape(gpt_extension)), gpt_ini_data):
        # ensure the line contains the ADM guid
        gpt_ext_loc = re.search(
            r"^{0}=.*\r\n".format(re.escape(gpt_extension)),
            gpt_ini_data,
            re.IGNORECASE | re.MULTILINE,
        )
        gpt_ext_str = gpt_ini_data[gpt_ext_loc.start() : gpt_ext_loc.end()]
        if not _regexSearchRegPolData(
            r"{0}".format(re.escape(gpt_extension_guid)), gpt_ext_str
        ):
            gpt_ext_str = gpt_ext_str.split("=")
            gpt_ext_str[1] = gpt_extension_guid + gpt_ext_str[1]
            gpt_ext_str = "=".join(gpt_ext_str)
            gpt_ini_data = (
                gpt_ini_data[0 : gpt_ext_loc.start()]
                + gpt_ext_str
                + gpt_ini_data[gpt_ext_loc.end() :]
            )
    else:
        general_location = re.search(
            r"^\[General\]\r\n", gpt_ini_data, re.IGNORECASE | re.MULTILINE
        )
        gpt_ini_data = "{0}{1}={2}\r\n{3}".format(
            gpt_ini_data[general_location.start() : general_location.end()],
            gpt_extension,
            gpt_extension_guid,
            gpt_ini_data[general_location.end() :],
        )
    # https://technet.microsoft.com/en-us/library/cc978247.aspx
    if _regexSearchRegPolData(r"Version=", gpt_ini_data):
        version_loc = re.search(
            r"^Version=.*\r\n", gpt_ini_data, re.IGNORECASE | re.MULTILINE
        )
        version_str = gpt_ini_data[version_loc.start() : version_loc.end()]
        version_str = version_str.split("=")
        version_nums = struct.unpack(b">2H", struct.pack(b">I", int(version_str[1])))
        if gpt_extension.lower() == "gPCMachineExtensionNames".lower():
            version_nums = (version_nums[0], version_nums[1] + 1)
        elif gpt_extension.lower() == "gPCUserExtensionNames".lower():
            version_nums = (version_nums[0] + 1, version_nums[1])
        version_num = struct.unpack(b">I", struct.pack(b">2H", *version_nums))[0]
        gpt_ini_data = "{0}{1}={2}\r\n{3}".format(
            gpt_ini_data[0 : version_loc.start()],
            "Version",
            version_num,
            gpt_ini_data[version_loc.end() :],
        )
    else:
        general_location = re.search(
            r"^\[General\]\r\n", gpt_ini_data, re.IGNORECASE | re.MULTILINE
        )
        if gpt_extension.lower() == "gPCMachineExtensionNames".lower():
            version_nums = (0, 1)
        elif gpt_extension.lower() == "gPCUserExtensionNames".lower():
            version_nums = (1, 0)
        gpt_ini_data = "{0}{1}={2}\r\n{3}".format(
            gpt_ini_data[general_location.start() : general_location.end()],
            "Version",
            int(
                "{0}{1}".format(
                    six.text_type(version_nums[0]).zfill(4),
                    six.text_type(version_nums[1]).zfill(4),
                ),
                16,
            ),
            gpt_ini_data[general_location.end() :],
        )
    if gpt_ini_data:
        try:
            with salt.utils.files.fopen(gpt_ini_path, "w") as gpt_file:
                gpt_file.write(gpt_ini_data)
        # TODO: This needs to be more specific
        except Exception as e:  # pylint: disable=broad-except
            msg = (
                "An error occurred attempting to write the gpg.ini file.\n"
                "path: {0}\n"
                "exception: {1}".format(gpt_ini_path, e)
            )
            log.exception(msg)
            raise CommandExecutionError(msg)


def _policyFileReplaceOrAppendList(string_list, policy_data):
    """
    helper function to take a list of strings for registry.pol file data and
    update existing strings or append the strings
    """
    if not policy_data:
        policy_data = b""
    # we are going to clean off the special pre-fixes, so we get only the valuename
    specialValueRegex = salt.utils.stringutils.to_bytes(
        r"(\*\*Del\.|\*\*DelVals\.){0,1}"
    )
    for this_string in string_list:
        list_item_key = this_string.split(b"\00;")[0].lstrip(b"[")
        list_item_value_name = re.sub(
            specialValueRegex, b"", this_string.split(b"\00;")[1], flags=re.IGNORECASE
        )
        log.trace("item value name is %s", list_item_value_name)
        data_to_replace = _regexSearchKeyValueCombo(
            policy_data, list_item_key, list_item_value_name
        )
        if data_to_replace:
            log.trace("replacing %s with %s", data_to_replace, this_string)
            policy_data = policy_data.replace(data_to_replace, this_string)
        else:
            log.trace("appending %s", this_string)
            policy_data = b"".join([policy_data, this_string])
    return policy_data


def _policyFileReplaceOrAppend(this_string, policy_data, append_only=False):
    """
    helper function to take a ADMX policy string for registry.pol file data and
    update existing string or append the string to the data
    """
    # we are going to clean off the special pre-fixes, so we get only the valuename
    if not policy_data:
        policy_data = b""
    specialValueRegex = salt.utils.stringutils.to_bytes(
        r"(\*\*Del\.|\*\*DelVals\.){0,1}"
    )
    item_key = None
    item_value_name = None
    data_to_replace = None
    if not append_only:
        item_key = this_string.split(b"\00;")[0].lstrip(b"[")
        item_value_name = re.sub(
            specialValueRegex, b"", this_string.split(b"\00;")[1], flags=re.IGNORECASE
        )
        log.trace("item value name is %s", item_value_name)
        data_to_replace = _regexSearchKeyValueCombo(
            policy_data, item_key, item_value_name
        )
    if data_to_replace:
        log.trace("replacing %s with %s", data_to_replace, this_string)
        policy_data = policy_data.replace(data_to_replace, this_string)
    else:
        log.trace("appending %s", this_string)
        policy_data = b"".join([policy_data, this_string])

    return policy_data


def _writeAdminTemplateRegPolFile(
    admtemplate_data, adml_language="en-US", registry_class="Machine"
):
    r"""
    helper function to prep/write adm template data to the Registry.pol file

    each file begins with REGFILE_SIGNATURE (u'\u5250\u6765') and
    REGISTRY_FILE_VERSION (u'\x01\00')

    https://msdn.microsoft.com/en-us/library/aa374407(VS.85).aspx
    +    https://msdn.microsoft.com/en-us/library/cc232696.aspx
    [Registry Path<NULL>;Reg Value<NULL>;Reg Type;SizeInBytes;Data<NULL>]
    """
    existing_data = b""
    policy_data = _policy_info()
    policySearchXpath = '//ns1:*[@id = "{0}" or @name = "{0}"]'
    admx_policy_definitions = _get_policy_definitions(language=adml_language)
    adml_policy_resources = _get_policy_resources(language=adml_language)
    base_policy_settings = _checkAllAdmxPolicies(
        policy_class=registry_class,
        adml_language=adml_language,
        return_full_policy_names=False,
        hierarchical_return=False,
        return_not_configured=False,
    )
    for adm_namespace in admtemplate_data:
        for adm_policy in admtemplate_data[adm_namespace]:
            if (
                six.text_type(admtemplate_data[adm_namespace][adm_policy]).lower()
                == "not configured"
            ):
                if (
                    base_policy_settings.get(adm_namespace, {}).pop(adm_policy, None)
                    is not None
                ):
                    log.trace('Policy "%s" removed', adm_policy)
            else:
                log.trace("adding %s to base_policy_settings", adm_policy)
                if adm_namespace not in base_policy_settings:
                    base_policy_settings[adm_namespace] = {}
                base_policy_settings[adm_namespace][adm_policy] = admtemplate_data[
                    adm_namespace
                ][adm_policy]
    for adm_namespace in base_policy_settings:
        for admPolicy in base_policy_settings[adm_namespace]:
            log.trace("working on admPolicy %s", admPolicy)
            explicit_enable_disable_value_setting = False
            this_key = None
            this_valuename = None
            if (
                six.text_type(base_policy_settings[adm_namespace][admPolicy]).lower()
                == "disabled"
            ):
                log.trace("time to disable %s", admPolicy)
                this_policy = admx_policy_definitions.xpath(
                    policySearchXpath.format(admPolicy),
                    namespaces={"ns1": adm_namespace},
                )
                if this_policy:
                    this_policy = this_policy[0]
                    if "class" in this_policy.attrib:
                        if (
                            this_policy.attrib["class"] == registry_class
                            or this_policy.attrib["class"] == "Both"
                        ):
                            if "key" in this_policy.attrib:
                                this_key = this_policy.attrib["key"]
                            else:
                                log.error(
                                    "policy item %s does not have "
                                    'the required "key" attribute',
                                    this_policy.attrib,
                                )
                                break
                            if "valueName" in this_policy.attrib:
                                this_valuename = this_policy.attrib["valueName"]
                            if DISABLED_VALUE_XPATH(this_policy):
                                # set the disabled value in the registry.pol file
                                explicit_enable_disable_value_setting = True
                                disabled_value_string = _checkValueItemParent(
                                    this_policy,
                                    admPolicy,
                                    this_key,
                                    this_valuename,
                                    DISABLED_VALUE_XPATH,
                                    None,
                                    check_deleted=False,
                                    test_item=False,
                                )
                                existing_data = _policyFileReplaceOrAppend(
                                    disabled_value_string, existing_data
                                )
                            if DISABLED_LIST_XPATH(this_policy):
                                explicit_enable_disable_value_setting = True
                                disabled_list_strings = _checkListItem(
                                    this_policy,
                                    admPolicy,
                                    this_key,
                                    DISABLED_LIST_XPATH,
                                    None,
                                    test_items=False,
                                )
                                log.trace(
                                    "working with disabledList " "portion of %s",
                                    admPolicy,
                                )
                                existing_data = _policyFileReplaceOrAppendList(
                                    disabled_list_strings, existing_data
                                )
                            if (
                                not explicit_enable_disable_value_setting
                                and this_valuename
                            ):
                                disabled_value_string = _buildKnownDataSearchString(
                                    this_key,
                                    this_valuename,
                                    "REG_DWORD",
                                    None,
                                    check_deleted=True,
                                )
                                existing_data = _policyFileReplaceOrAppend(
                                    disabled_value_string, existing_data
                                )
                            if ELEMENTS_XPATH(this_policy):
                                log.trace("checking elements of %s", admPolicy)
                                for elements_item in ELEMENTS_XPATH(this_policy):
                                    for child_item in elements_item.getchildren():
                                        child_key = this_key
                                        child_valuename = this_valuename
                                        if "key" in child_item.attrib:
                                            child_key = child_item.attrib["key"]
                                        if "valueName" in child_item.attrib:
                                            child_valuename = child_item.attrib[
                                                "valueName"
                                            ]
                                        if etree.QName(
                                            child_item
                                        ).localname == "boolean" and (
                                            TRUE_LIST_XPATH(child_item)
                                            or FALSE_LIST_XPATH(child_item)
                                        ):
                                            # WARNING: no OOB adm files use true/falseList items
                                            # this has not been fully vetted
                                            temp_dict = {
                                                "trueList": TRUE_LIST_XPATH,
                                                "falseList": FALSE_LIST_XPATH,
                                            }
                                            for this_list in temp_dict:
                                                disabled_list_strings = _checkListItem(
                                                    child_item,
                                                    admPolicy,
                                                    child_key,
                                                    temp_dict[this_list],
                                                    None,
                                                    test_items=False,
                                                )
                                                log.trace(
                                                    "working with %s portion of %s",
                                                    admPolicy,
                                                    this_list,
                                                )
                                                existing_data = _policyFileReplaceOrAppendList(
                                                    disabled_list_strings, existing_data
                                                )
                                        elif (
                                            etree.QName(child_item).localname
                                            == "boolean"
                                            or etree.QName(child_item).localname
                                            == "decimal"
                                            or etree.QName(child_item).localname
                                            == "text"
                                            or etree.QName(child_item).localname
                                            == "longDecimal"
                                            or etree.QName(child_item).localname
                                            == "multiText"
                                            or etree.QName(child_item).localname
                                            == "enum"
                                        ):
                                            disabled_value_string = _processValueItem(
                                                child_item,
                                                child_key,
                                                child_valuename,
                                                this_policy,
                                                elements_item,
                                                check_deleted=True,
                                            )
                                            log.trace(
                                                "I have disabled value string of %s",
                                                disabled_value_string,
                                            )
                                            existing_data = _policyFileReplaceOrAppend(
                                                disabled_value_string, existing_data
                                            )
                                        elif (
                                            etree.QName(child_item).localname == "list"
                                        ):
                                            disabled_value_string = _processValueItem(
                                                child_item,
                                                child_key,
                                                child_valuename,
                                                this_policy,
                                                elements_item,
                                                check_deleted=True,
                                            )
                                            log.trace(
                                                "I have disabled value string of %s",
                                                disabled_value_string,
                                            )
                                            existing_data = _policyFileReplaceOrAppend(
                                                disabled_value_string, existing_data
                                            )
                        else:
                            log.error(
                                "policy %s was found but it does not appear to be valid for the class %s",
                                admPolicy,
                                registry_class,
                            )
                    else:
                        log.error(
                            'policy item %s does not have the requried "class" attribute',
                            this_policy.attrib,
                        )
            else:
                log.trace('time to enable and set the policy "%s"', admPolicy)
                this_policy = admx_policy_definitions.xpath(
                    policySearchXpath.format(admPolicy),
                    namespaces={"ns1": adm_namespace},
                )
                log.trace("found this_policy == %s", this_policy)
                if this_policy:
                    this_policy = this_policy[0]
                    if "class" in this_policy.attrib:
                        if (
                            this_policy.attrib["class"] == registry_class
                            or this_policy.attrib["class"] == "Both"
                        ):
                            if "key" in this_policy.attrib:
                                this_key = this_policy.attrib["key"]
                            else:
                                log.error(
                                    'policy item %s does not have the required "key" attribute',
                                    this_policy.attrib,
                                )
                                break
                            if "valueName" in this_policy.attrib:
                                this_valuename = this_policy.attrib["valueName"]

                            if ENABLED_VALUE_XPATH(this_policy):
                                explicit_enable_disable_value_setting = True
                                enabled_value_string = _checkValueItemParent(
                                    this_policy,
                                    admPolicy,
                                    this_key,
                                    this_valuename,
                                    ENABLED_VALUE_XPATH,
                                    None,
                                    check_deleted=False,
                                    test_item=False,
                                )
                                existing_data = _policyFileReplaceOrAppend(
                                    enabled_value_string, existing_data
                                )
                            if ENABLED_LIST_XPATH(this_policy):
                                explicit_enable_disable_value_setting = True
                                enabled_list_strings = _checkListItem(
                                    this_policy,
                                    admPolicy,
                                    this_key,
                                    ENABLED_LIST_XPATH,
                                    None,
                                    test_items=False,
                                )
                                log.trace(
                                    "working with enabledList portion of %s", admPolicy
                                )
                                existing_data = _policyFileReplaceOrAppendList(
                                    enabled_list_strings, existing_data
                                )
                            if (
                                not explicit_enable_disable_value_setting
                                and this_valuename
                            ):
                                enabled_value_string = _buildKnownDataSearchString(
                                    this_key,
                                    this_valuename,
                                    "REG_DWORD",
                                    "1",
                                    check_deleted=False,
                                )
                                existing_data = _policyFileReplaceOrAppend(
                                    enabled_value_string, existing_data
                                )
                            if ELEMENTS_XPATH(this_policy):
                                for elements_item in ELEMENTS_XPATH(this_policy):
                                    for child_item in elements_item.getchildren():
                                        child_key = this_key
                                        child_valuename = this_valuename
                                        if "key" in child_item.attrib:
                                            child_key = child_item.attrib["key"]
                                        if "valueName" in child_item.attrib:
                                            child_valuename = child_item.attrib[
                                                "valueName"
                                            ]
                                        if (
                                            child_item.attrib["id"]
                                            in base_policy_settings[adm_namespace][
                                                admPolicy
                                            ]
                                        ):
                                            if etree.QName(
                                                child_item
                                            ).localname == "boolean" and (
                                                TRUE_LIST_XPATH(child_item)
                                                or FALSE_LIST_XPATH(child_item)
                                            ):
                                                list_strings = []
                                                if base_policy_settings[adm_namespace][
                                                    admPolicy
                                                ][child_item.attrib["id"]]:
                                                    list_strings = _checkListItem(
                                                        child_item,
                                                        admPolicy,
                                                        child_key,
                                                        TRUE_LIST_XPATH,
                                                        None,
                                                        test_items=False,
                                                    )
                                                    log.trace(
                                                        "working with trueList portion of {0}".format(
                                                            admPolicy
                                                        )
                                                    )
                                                else:
                                                    list_strings = _checkListItem(
                                                        child_item,
                                                        admPolicy,
                                                        child_key,
                                                        FALSE_LIST_XPATH,
                                                        None,
                                                        test_items=False,
                                                    )
                                                existing_data = _policyFileReplaceOrAppendList(
                                                    list_strings, existing_data
                                                )
                                            elif etree.QName(
                                                child_item
                                            ).localname == "boolean" and (
                                                TRUE_VALUE_XPATH(child_item)
                                                or FALSE_VALUE_XPATH(child_item)
                                            ):
                                                value_string = ""
                                                if base_policy_settings[adm_namespace][
                                                    admPolicy
                                                ][child_item.attrib["id"]]:
                                                    value_string = _checkValueItemParent(
                                                        child_item,
                                                        admPolicy,
                                                        child_key,
                                                        child_valuename,
                                                        TRUE_VALUE_XPATH,
                                                        None,
                                                        check_deleted=False,
                                                        test_item=False,
                                                    )
                                                else:
                                                    value_string = _checkValueItemParent(
                                                        child_item,
                                                        admPolicy,
                                                        child_key,
                                                        child_valuename,
                                                        FALSE_VALUE_XPATH,
                                                        None,
                                                        check_deleted=False,
                                                        test_item=False,
                                                    )
                                                existing_data = _policyFileReplaceOrAppend(
                                                    value_string, existing_data
                                                )
                                            elif (
                                                etree.QName(child_item).localname
                                                == "boolean"
                                                or etree.QName(child_item).localname
                                                == "decimal"
                                                or etree.QName(child_item).localname
                                                == "text"
                                                or etree.QName(child_item).localname
                                                == "longDecimal"
                                                or etree.QName(child_item).localname
                                                == "multiText"
                                            ):
                                                enabled_value_string = _processValueItem(
                                                    child_item,
                                                    child_key,
                                                    child_valuename,
                                                    this_policy,
                                                    elements_item,
                                                    check_deleted=False,
                                                    this_element_value=base_policy_settings[
                                                        adm_namespace
                                                    ][
                                                        admPolicy
                                                    ][
                                                        child_item.attrib["id"]
                                                    ],
                                                )
                                                log.trace(
                                                    "I have enabled value string of %s",
                                                    enabled_value_string,
                                                )
                                                existing_data = _policyFileReplaceOrAppend(
                                                    enabled_value_string, existing_data
                                                )
                                            elif (
                                                etree.QName(child_item).localname
                                                == "enum"
                                            ):
                                                for (
                                                    enum_item
                                                ) in child_item.getchildren():
                                                    if (
                                                        base_policy_settings[
                                                            adm_namespace
                                                        ][admPolicy][
                                                            child_item.attrib["id"]
                                                        ]
                                                        == _getAdmlDisplayName(
                                                            adml_policy_resources,
                                                            enum_item.attrib[
                                                                "displayName"
                                                            ],
                                                        ).strip()
                                                    ):
                                                        enabled_value_string = _checkValueItemParent(
                                                            enum_item,
                                                            child_item.attrib["id"],
                                                            child_key,
                                                            child_valuename,
                                                            VALUE_XPATH,
                                                            None,
                                                            check_deleted=False,
                                                            test_item=False,
                                                        )
                                                        existing_data = _policyFileReplaceOrAppend(
                                                            enabled_value_string,
                                                            existing_data,
                                                        )
                                                        if VALUE_LIST_XPATH(enum_item):
                                                            enabled_list_strings = _checkListItem(
                                                                enum_item,
                                                                admPolicy,
                                                                child_key,
                                                                VALUE_LIST_XPATH,
                                                                None,
                                                                test_items=False,
                                                            )
                                                            log.trace(
                                                                "working with valueList portion of %s",
                                                                child_item.attrib["id"],
                                                            )
                                                            existing_data = _policyFileReplaceOrAppendList(
                                                                enabled_list_strings,
                                                                existing_data,
                                                            )
                                                        break
                                            elif (
                                                etree.QName(child_item).localname
                                                == "list"
                                            ):
                                                enabled_value_string = _processValueItem(
                                                    child_item,
                                                    child_key,
                                                    child_valuename,
                                                    this_policy,
                                                    elements_item,
                                                    check_deleted=False,
                                                    this_element_value=base_policy_settings[
                                                        adm_namespace
                                                    ][
                                                        admPolicy
                                                    ][
                                                        child_item.attrib["id"]
                                                    ],
                                                )
                                                log.trace(
                                                    "I have enabled value string of %s",
                                                    enabled_value_string,
                                                )
                                                existing_data = _policyFileReplaceOrAppend(
                                                    enabled_value_string,
                                                    existing_data,
                                                    append_only=True,
                                                )
    try:
        _write_regpol_data(
            existing_data,
            policy_data.admx_registry_classes[registry_class]["policy_path"],
            policy_data.gpt_ini_path,
            policy_data.admx_registry_classes[registry_class]["gpt_extension_location"],
            policy_data.admx_registry_classes[registry_class]["gpt_extension_guid"],
        )
    # TODO: This needs to be more specific or removed
    except CommandExecutionError as exc:  # pylint: disable=broad-except
        log.exception(
            "Unhandled exception occurred while attempting to "
            "write Adm Template Policy File.\nException: %s",
            exc,
        )
        return False
    return True


def _getScriptSettingsFromIniFile(policy_info):
    """
    helper function to parse/read a GPO Startup/Shutdown script file

    psscript.ini and script.ini file definitions are here
        https://msdn.microsoft.com/en-us/library/ff842529.aspx
        https://msdn.microsoft.com/en-us/library/dd303238.aspx
    """
    _existingData = None
    if os.path.isfile(policy_info["ScriptIni"]["IniPath"]):
        with salt.utils.files.fopen(policy_info["ScriptIni"]["IniPath"], "rb") as fhr:
            _existingData = fhr.read()
        if _existingData:
            try:
                _existingData = deserialize(
                    _existingData.decode("utf-16-le").lstrip("\ufeff")
                )
                log.trace("Have deserialized data %s", _existingData)
            except Exception as error:  # pylint: disable=broad-except
                log.exception(
                    "An error occurred attempting to deserialize data for %s",
                    policy_info["Policy"],
                )
                raise CommandExecutionError(error)
            if "Section" in policy_info["ScriptIni"] and policy_info["ScriptIni"][
                "Section"
            ].lower() in [z.lower() for z in _existingData.keys()]:
                if "SettingName" in policy_info["ScriptIni"]:
                    log.trace(
                        "Need to look for %s", policy_info["ScriptIni"]["SettingName"]
                    )
                    if policy_info["ScriptIni"]["SettingName"].lower() in [
                        z.lower()
                        for z in _existingData[
                            policy_info["ScriptIni"]["Section"]
                        ].keys()
                    ]:
                        return _existingData[policy_info["ScriptIni"]["Section"]][
                            policy_info["ScriptIni"]["SettingName"].lower()
                        ]
                    else:
                        return None
                else:
                    return _existingData[policy_info["ScriptIni"]["Section"]]
            else:
                return None

    return None


def _writeGpoScript(psscript=False):
    """
    helper function to write local GPO startup/shutdown script

    scripts are stored in scripts.ini and psscripts.ini files in
    ``WINDIR\\System32\\GroupPolicy\\Machine|User\\Scripts``

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

    psscript file also has the option of a [ScriptsConfig] section, which has
    the following two parameters:
        StartExecutePSFirst
        EndExecutePSFirst

    these can be set to True/False to denote if the powershell startup/shutdown
    scripts execute first (True) or last (False), if the value isn't set, then
    it is 'Not Configured' in the GUI
    """
    _machineScriptPolicyPath = os.path.join(
        os.getenv("WINDIR"),
        "System32",
        "GroupPolicy",
        "Machine",
        "Scripts",
        "scripts.ini",
    )
    _machinePowershellScriptPolicyPath = os.path.join(
        os.getenv("WINDIR"),
        "System32",
        "GroupPolicy",
        "Machine",
        "Scripts",
        "psscripts.ini",
    )
    _userScriptPolicyPath = os.path.join(
        os.getenv("WINDIR"), "System32", "GroupPolicy", "User", "Scripts", "scripts.ini"
    )
    _userPowershellScriptPolicyPath = os.path.join(
        os.getenv("WINDIR"),
        "System32",
        "GroupPolicy",
        "User",
        "Scripts",
        "psscripts.ini",
    )


def _lookup_admin_template(policy_name, policy_class, adml_language="en-US"):
    """
    (success_flag, policy_xml_item, policy_name_list, message)
    """
    policy_aliases = []
    admx_policy_definitions = _get_policy_definitions(language=adml_language)
    adml_policy_resources = _get_policy_resources(language=adml_language)
    admx_search_results = ADMX_SEARCH_XPATH(
        admx_policy_definitions, policy_name=policy_name, registry_class=policy_class
    )
    if admx_search_results:
        if len(admx_search_results) == 1:
            the_policy = admx_search_results[0]
            policy_display_name = _getFullPolicyName(
                policy_item=the_policy,
                policy_name=the_policy.attrib["name"],
                return_full_policy_names=True,
                adml_language=adml_language,
            )
            policy_aliases.append(policy_display_name)
            policy_aliases.append(the_policy.attrib["name"])
            full_path_list = _build_parent_list(
                policy_definition=the_policy,
                return_full_policy_names=True,
                adml_language=adml_language,
            )
            full_path_list.reverse()
            full_path_list.append(policy_display_name)
            policy_aliases.append("\\".join(full_path_list))
            return True, the_policy, policy_aliases, None
        else:
            msg = 'ADMX policy name/id "{0}" is used in multiple ADMX files'
            return False, None, [], msg
    else:
        adml_search_results = ADML_SEARCH_XPATH(
            adml_policy_resources, policy_name=policy_name
        )
        hierarchy = []
        hierarchy_policy_name = policy_name
        if not adml_search_results:
            log.warning("Trying another: %s", policy_name)
            if "\\" in policy_name:
                hierarchy = policy_name.split("\\")
                policy_name = hierarchy.pop()
                adml_search_results = ADML_SEARCH_XPATH(
                    adml_policy_resources, policy_name=policy_name
                )
        if adml_search_results:
            multiple_adml_entries = False
            suggested_policies = ""
            adml_to_remove = []
            if len(adml_search_results) > 1:
                log.trace(
                    "multiple ADML entries found matching the policy name %s",
                    policy_name,
                )
                multiple_adml_entries = True
                for adml_search_result in adml_search_results:
                    if (
                        not getattr(adml_search_result, "text", "").strip()
                        == policy_name
                    ):
                        adml_to_remove.append(adml_search_result)
                    else:
                        if hierarchy:
                            log.trace("we have hierarchy of %s", hierarchy)
                            display_name_searchval = "$({0}.{1})".format(
                                adml_search_result.tag.split("}")[1],
                                adml_search_result.attrib["id"],
                            )
                            # policy_search_string = '//{0}:policy[@*[local-name() = "displayName"] = "{1}" and (@*[local-name() = "class"] = "Both" or @*[local-name() = "class"] = "{2}") ]'.format(
                            policy_search_string = '//{0}:policy[@displayName = "{1}" and (@class = "Both" or @class = "{2}") ]'.format(
                                adml_search_result.prefix,
                                display_name_searchval,
                                policy_class,
                            )
                            admx_results = []
                            these_admx_search_results = admx_policy_definitions.xpath(
                                policy_search_string,
                                namespaces=adml_search_result.nsmap,
                            )
                            if not these_admx_search_results:
                                log.trace(
                                    "No admx was found for the adml entry %s, it will be removed",
                                    display_name_searchval,
                                )
                                adml_to_remove.append(adml_search_result)
                            for search_result in these_admx_search_results:
                                log.trace("policy_name == %s", policy_name)
                                this_hierarchy = _build_parent_list(
                                    policy_definition=search_result,
                                    return_full_policy_names=True,
                                    adml_language=adml_language,
                                )
                                this_hierarchy.reverse()
                                if hierarchy != this_hierarchy:
                                    msg = "hierarchy %s does not match this item's hierarchy of %s"
                                    log.trace(msg, hierarchy, this_hierarchy)
                                    if len(these_admx_search_results) == 1:
                                        log.trace(
                                            "only 1 admx was found and it does not match this adml, it is safe to remove from the list"
                                        )
                                        adml_to_remove.append(adml_search_result)
                                else:
                                    log.trace(
                                        "hierarchy %s matches item's hierarchy of %s",
                                        hierarchy,
                                        this_hierarchy,
                                    )
                                    log.trace(
                                        "search_result %s added to results",
                                        search_result,
                                    )
                                    admx_results.append(search_result)
                            if len(admx_results) == 1:
                                admx_search_results.append(admx_results[0])
                        else:
                            # verify the ADMX correlated to this ADML is in the same class
                            # that we are looking for
                            display_name_searchval = "$({0}.{1})".format(
                                adml_search_result.tag.split("}")[1],
                                adml_search_result.attrib["id"],
                            )
                            these_admx_search_results = ADMX_DISPLAYNAME_SEARCH_XPATH(
                                admx_policy_definitions,
                                display_name=display_name_searchval,
                                registry_class=policy_class,
                            )
                            if not these_admx_search_results:
                                adml_to_remove.append(adml_search_result)
            for adml in adml_to_remove:
                if adml in adml_search_results:
                    adml_search_results.remove(adml)
            if len(adml_search_results) == 1 and multiple_adml_entries:
                multiple_adml_entries = False
            for adml_search_result in adml_search_results:
                log.trace(
                    "found an ADML entry matching the string! %s -- %s",
                    adml_search_result.tag,
                    adml_search_result.attrib,
                )
                display_name_searchval = "$({0}.{1})".format(
                    adml_search_result.tag.split("}")[1],
                    adml_search_result.attrib["id"],
                )
                log.trace("searching for displayName == %s", display_name_searchval)
                if not admx_search_results:
                    log.trace(
                        "search for an admx entry matching display_name %s and registry_class %s",
                        display_name_searchval,
                        policy_class,
                    )
                    admx_search_results = ADMX_DISPLAYNAME_SEARCH_XPATH(
                        admx_policy_definitions,
                        display_name=display_name_searchval,
                        registry_class=policy_class,
                    )
                if admx_search_results:
                    log.trace(
                        "processing admx_search_results of {0}".format(
                            admx_search_results
                        )
                    )
                    log.trace(
                        "multiple_adml_entries is {0}".format(multiple_adml_entries)
                    )
                    if (
                        len(admx_search_results) == 1 or hierarchy
                    ) and not multiple_adml_entries:
                        found = False
                        for search_result in admx_search_results:
                            found = False
                            if hierarchy:
                                this_hierarchy = _build_parent_list(
                                    policy_definition=search_result,
                                    return_full_policy_names=True,
                                    adml_language=adml_language,
                                )
                                this_hierarchy.reverse()
                                log.trace("testing %s == %s", hierarchy, this_hierarchy)
                                if hierarchy == this_hierarchy:
                                    found = True
                            else:
                                found = True
                            if found:
                                log.trace(
                                    "found the ADMX policy matching "
                                    "the display name %s -- %s",
                                    search_result,
                                    policy_name,
                                )
                                if "name" in search_result.attrib:
                                    policy_display_name = _getFullPolicyName(
                                        policy_item=search_result,
                                        policy_name=search_result.attrib["name"],
                                        return_full_policy_names=True,
                                        adml_language=adml_language,
                                    )
                                    policy_aliases.append(policy_display_name)
                                    policy_aliases.append(search_result.attrib["name"])
                                    full_path_list = _build_parent_list(
                                        policy_definition=search_result,
                                        return_full_policy_names=True,
                                        adml_language=adml_language,
                                    )
                                    full_path_list.reverse()
                                    full_path_list.append(policy_display_name)
                                    policy_aliases.append("\\".join(full_path_list))
                                    return True, search_result, policy_aliases, None
                                else:
                                    msg = (
                                        "ADMX policy with the display name {0} does not"
                                        "have the required name attribute"
                                    )
                                    msg = msg.format(policy_name)
                                    return False, None, [], msg
                        if not found:
                            msg = "Unable to correlate {0} to any policy".format(
                                hierarchy_policy_name
                            )
                            return False, None, [], msg
                    else:
                        for possible_policy in admx_search_results:
                            this_parent_list = _build_parent_list(
                                policy_definition=possible_policy,
                                return_full_policy_names=True,
                                adml_language=adml_language,
                            )
                            this_parent_list.reverse()
                            this_parent_list.append(policy_name)
                            if suggested_policies:
                                suggested_policies = ", ".join(
                                    [suggested_policies, "\\".join(this_parent_list)]
                                )
                            else:
                                suggested_policies = "\\".join(this_parent_list)
            if suggested_policies:
                msg = (
                    'ADML policy name "{0}" is used as the display name'
                    " for multiple policies."
                    "  These policies matched: {1}"
                    ".  You can utilize these long names to"
                    " specify the correct policy"
                )
                return False, None, [], msg.format(policy_name, suggested_policies)
    return (
        False,
        None,
        [],
        "Unable to find {0} policy {1}".format(policy_class, policy_name),
    )


def get_policy_info(policy_name, policy_class, adml_language="en-US"):
    r"""
    Returns information about a specified policy

    Args:
        policy_name (str):
            The name of the policy to lookup
        policy_class (str):
            The class of policy, i.e. machine, user, both
        adml_language (str):
            The ADML language to use for Administrative Template data lookup

    Returns:
        dict: Information about the specified policy

    CLI Example:

    .. code-block:: bash

        salt '*' lgpo.get_policy_info 'Maximum password age' machine

    You can use ``lgpo.get_policy_info`` to get all the possible names that
    could be used in a state file or from the command line (along with elements
    that need to be set/etc). The key is to match the text you see in the
    ``gpedit.msc`` gui exactly, including quotes around words or phrases. The
    "full path" style is really only needed when there are multiple policies
    that use the same base name. For example, ``Access data sources across
    domains`` exists in ~10 different paths. If you put that through
    ``get_policy_info`` you'll get back a message that it is used for multiple
    policies and you need to be more specific.

    CLI Example:

    .. code-block:: bash

        salt-call --local lgpo.get_policy_info ShellRemoveOrderPrints_2 machine

        local:
            ----------
            message:
            policy_aliases:
                - Turn off the "Order Prints" picture task
                - ShellRemoveOrderPrints_2
                - System\Internet Communication Management\Internet Communication settings\Turn off the "Order Prints" picture task
            policy_class:
                machine
            policy_elements:
            policy_found:
                True
            policy_name:
                ShellRemoveOrderPrints_2
            rights_assignment:
                False

    Escaping can get tricky in cmd/Powershell. The following is an example of
    escaping in Powershell using backquotes:

    .. code-block:: bash

        PS>salt-call --local lgpo.get_policy_info "Turn off the `\`"Order Prints`\`" picture task" machine

        local:
            ----------
            message:
            policy_aliases:
                - Turn off the "Order Prints" picture task
                - ShellRemoveOrderPrints_2
                - System\Internet Communication Management\Internet Communication settings\Turn off the "Order Prints" picture task
            policy_class:
                machine
            policy_elements:
            policy_found:
                True
            policy_name:
                Turn off the "Order Prints" picture task
            rights_assignment:
                False

    This function can then be used to get the options available for specifying
    Group Policy Objects to be used in state files. Based on the above any of
    these *should* be usable:

    .. code-block:: bash

        internet_communications_settings:
          lgpo.set:
            - computer_policy:
                Turn off the "Order Prints" picture task: Enabled

    .. code-block:: bash

        internet_communications_settings:
          lgpo.set:
            - computer_policy:
                ShellRemoveOrderPrints_2: Enabled

    When using the full path, it might be a good idea to use single quotes
    around the path:

    .. code-block:: bash

        internet_communications_settings:
          lgpo.set:
            - computer_policy:
                'System\Internet Communication Management\Internet Communication settings\Turn off the "Order Prints" picture task': 'Enabled'

    If you struggle to find the policy from ``get_policy_info`` using the name
    as you see in ``gpedit.msc``, the names such as "ShellRemoveOrderPrints_2"
    come from the ``.admx`` files. If you know nothing about ``.admx/.adml``
    relationships (ADML holds what you see in the GUI, ADMX holds the more
    technical details), then this may be a little bit too much info, but here is
    an example with the above policy using Powershell:


    .. code-block:: bash

        PS>Get-ChildItem -Path C:\Windows\PolicyDefinitions -Recurse -Filter *.adml | Select-String "Order Prints"

        C:\windows\PolicyDefinitions\en-US\ICM.adml:152:      <string id="ShellRemoveOrderPrints">Turn off the "Order Prints" picture task</string>
        C:\windows\PolicyDefinitions\en-US\ICM.adml:153:      <string id="ShellRemoveOrderPrints_Help">This policy setting specifies whether the "Order Prints Online" task is available from Picture Tasks in Windows folders.
        C:\windows\PolicyDefinitions\en-US\ICM.adml:155:The Order Prints Online Wizard is used to download a list of providers and allow users to order prints online.
        C:\windows\PolicyDefinitions\en-US\ICM.adml:157:If you enable this policy setting, the task "Order Prints Online" is removed from Picture Tasks in File Explorer folders.

    From this grep, we can see id "ShellRemoveOrderPrints" is the ID of the
    string used to describe this policy, then we search for it in the ADMX:

    .. code-block:: bash

        PS>Get-ChildItem -Path C:\Windows\PolicyDefinitions -Recurse -Filter *.admx | Select-String "ShellRemoveOrderPrints"

        C:\windows\PolicyDefinitions\ICM.admx:661:    <policy name="ShellRemoveOrderPrints_1" class="User" displayName="$(string.ShellRemoveOrderPrints)" explainText="$(string.ShellRemoveOrderPrints_Help)" key="Software\Microsoft\Windows\CurrentVersion\Policies\Explorer" valueName="NoOnlinePrintsWizard">
        C:\windows\PolicyDefinitions\ICM.admx:671:    <policy name="ShellRemoveOrderPrints_2" class="Machine" displayName="$(string.ShellRemoveOrderPrints)" explainText="$(string.ShellRemoveOrderPrints_Help)" key="Software\Microsoft\Windows\CurrentVersion\Policies\Explorer" valueName="NoOnlinePrintsWizard">

    Now we have two to pick from. And if you notice the ``class="Machine"`` and
    ``class="User"`` (which details if it is a computer policy or user policy
    respectively) the ``ShellRemoveOrderPrints_2`` is the "short name" we could
    use to pass through ``get_policy_info`` to see what the module itself is
    expecting.
    """
    # return the possible policy names and element names
    ret = {
        "policy_name": policy_name,
        "policy_class": policy_class,
        "policy_aliases": [],
        "policy_found": False,
        "rights_assignment": False,
        "policy_elements": [],
        "message": "policy not found",
    }
    policy_class = policy_class.title()
    policy_data = _policy_info()
    if policy_class not in policy_data.policies.keys():
        policy_classes = ", ".join(policy_data.policies.keys())
        ret["message"] = (
            'The requested policy class "{0}" is invalid, '
            "policy_class should be one of: {1}"
            "".format(policy_class, policy_classes)
        )
        return ret
    if policy_name in policy_data.policies[policy_class]["policies"]:
        ret["policy_aliases"].append(
            policy_data.policies[policy_class]["policies"][policy_name]["Policy"]
        )
        ret["policy_found"] = True
        ret["message"] = ""
        if "LsaRights" in policy_data.policies[policy_class]["policies"][policy_name]:
            ret["rights_assignment"] = True
        return ret
    else:
        for pol in policy_data.policies[policy_class]["policies"]:
            if (
                policy_data.policies[policy_class]["policies"][pol]["Policy"].lower()
                == policy_name.lower()
            ):
                ret["policy_aliases"].append(pol)
                ret["policy_found"] = True
                ret["message"] = ""
                if "LsaRights" in policy_data.policies[policy_class]["policies"][pol]:
                    ret["rights_assignment"] = True
                return ret
    success, policy_xml_item, policy_name_list, message = _lookup_admin_template(
        policy_name=policy_name, policy_class=policy_class, adml_language=adml_language
    )
    if success:
        for elements_item in ELEMENTS_XPATH(policy_xml_item):
            for child_item in elements_item.getchildren():
                this_element_name = _getFullPolicyName(
                    policy_item=child_item,
                    policy_name=child_item.attrib["id"],
                    return_full_policy_names=True,
                    adml_language=adml_language,
                )
                ret["policy_elements"].append(
                    {
                        "element_id": child_item.attrib["id"],
                        "element_aliases": [child_item.attrib["id"], this_element_name],
                    }
                )
        ret["policy_aliases"] = policy_name_list
        ret["policy_found"] = True
        ret["message"] = ""
        return ret
    else:
        ret["message"] = message

    return ret


def get(
    policy_class=None,
    return_full_policy_names=True,
    hierarchical_return=False,
    adml_language="en-US",
    return_not_configured=False,
):
    """
    Get a policy value

    Args:

        policy_class (str):
            Some policies are both user and computer, by default all policies
            will be pulled, but this can be used to retrieve only a specific
            policy class User/USER/user = retrieve user policies
            Machine/MACHINE/machine/Computer/COMPUTER/computer = retrieve
            machine/computer policies

        return_full_policy_names (bool):
            True/False to return the policy name as it is seen in the
            ``gpedit.msc`` GUI or to only return the policy key/id.

        hierarchical_return (bool):
            True/False to return the policy data in the hierarchy as seen in the
            ``gpedit.msc`` GUI. The default of False will return data split only
            into User/Computer configuration sections

        adml_language (str):
            The ADML language to use for processing display/descriptive names
            and enumeration values of ADMX template data, defaults to en-US

        return_not_configured (bool):
            Include Administrative Template policies that are 'Not Configured'
            in the return data

    Returns:
        dict: A dictionary containing the policy values for the specified class

    CLI Example:

    .. code-block:: bash

        salt '*' lgpo.get machine return_full_policy_names=True
    """

    vals = {}
    _policydata = _policy_info()

    if policy_class is None or policy_class.lower() == "both":
        policy_class = _policydata.policies.keys()
    elif policy_class.lower() not in [z.lower() for z in _policydata.policies]:
        msg = (
            "The policy_class {0} is not an available policy class, please "
            "use one of the following: {1}, Both"
        )
        raise SaltInvocationError(
            msg.format(policy_class, ", ".join(_policydata.policies.keys()))
        )
    else:
        policy_class = [policy_class.title()]

    # handle policies statically defined in this module
    for p_class in policy_class:
        this_class_policy_names = _policydata.policies[p_class]["policies"]
        class_vals = {}
        for policy_name in this_class_policy_names:
            _pol = None
            if policy_name in _policydata.policies[p_class]["policies"]:
                _pol = _policydata.policies[p_class]["policies"][policy_name]
            else:
                for policy in _policydata.policies[p_class]["policies"]:
                    if (
                        _policydata.policies[p_class]["policies"][policy][
                            "Policy"
                        ].upper()
                        == policy_name.upper()
                    ):
                        _pol = _policydata.policies[p_class]["policies"][policy]
                        policy_name = policy
            if _pol:
                vals_key_name = policy_name
                class_vals[policy_name] = _get_policy_info_setting(_pol)
                if return_full_policy_names:
                    class_vals[_pol["Policy"]] = class_vals.pop(policy_name)
                    vals_key_name = _pol["Policy"]
                if hierarchical_return:
                    if "lgpo_section" in _pol:
                        firstItem = True
                        tdict = {}
                        for level in reversed(_pol["lgpo_section"]):
                            newdict = {}
                            if firstItem:
                                newdict[level] = {
                                    vals_key_name: class_vals.pop(vals_key_name)
                                }
                                firstItem = False
                            else:
                                newdict[level] = tdict
                            tdict = newdict
                        if tdict:
                            class_vals = dictupdate.update(class_vals, tdict)
            else:
                msg = (
                    "The specified policy {0} is not currently available "
                    "to be configured via this module"
                )
                raise CommandExecutionError(msg.format(policy_name))
        class_vals = dictupdate.update(
            class_vals,
            _checkAllAdmxPolicies(
                policy_class=p_class,
                adml_language=adml_language,
                return_full_policy_names=return_full_policy_names,
                hierarchical_return=hierarchical_return,
                return_not_configured=return_not_configured,
            ),
        )
        if _policydata.policies[p_class]["lgpo_section"] not in class_vals:
            temp_dict = {_policydata.policies[p_class]["lgpo_section"]: class_vals}
            class_vals = temp_dict
        vals = dictupdate.update(vals, class_vals)

    return vals


def _get_policy_info_setting(policy_definition):
    """
    Some policies are defined in this module and others by the ADMX/ADML files
    on the machine. This function loads the current values for policies defined
    in this module.

    Args:
        policy_definition (dict):
            A sub-dict of Policies property of the _policy_info() class.
            Basically a dictionary that defines the policy

    Returns:
        The transformed value. The transform is defined in the policy
        definition. It can be a list, a string, a dictionary, depending on how
        it's defined

    Usage:
        policy_data = _policy_info()
        policy_name = 'RemoteRegistryExactPaths'
        policy_definition = policy_data.policies['Machine']['policies'][policy_name]
        policy_value = _get_policy_info_setting(policy_definition)
    """
    if "Registry" in policy_definition:
        # Get value using the Registry mechanism
        value = __utils__["reg.read_value"](
            policy_definition["Registry"]["Hive"],
            policy_definition["Registry"]["Path"],
            policy_definition["Registry"]["Value"],
        )["vdata"]
        log.trace(
            "Value %r found for Regisry policy %s", value, policy_definition["Policy"]
        )
    elif "Secedit" in policy_definition:
        # Get value using the Secedit mechanism
        value = _get_secedit_value(option=policy_definition["Secedit"]["Option"])
        log.trace(
            "Value %r found for Secedit policy %s", value, policy_definition["Policy"]
        )
    elif "NetSH" in policy_definition:
        # Get value using the NetSH mechanism
        value = _get_netsh_value(
            profile=policy_definition["NetSH"]["Profile"],
            option=policy_definition["NetSH"]["Option"],
        )
        log.trace(
            "Value %r found for NetSH policy %s", value, policy_definition["Policy"]
        )
    elif "AdvAudit" in policy_definition:
        # Get value using the AuditPol mechanism
        value = _get_advaudit_value(option=policy_definition["AdvAudit"]["Option"])
        log.trace(
            "Value %r found for AuditPol policy %s", value, policy_definition["Policy"]
        )
    elif "NetUserModal" in policy_definition:
        # Get value using the NetUserModal mechanism
        modal_return = win32net.NetUserModalsGet(
            None, policy_definition["NetUserModal"]["Modal"]
        )
        value = modal_return[policy_definition["NetUserModal"]["Option"]]
        log.trace(
            "Value %r found for NetUserModal policy %s",
            value,
            policy_definition["Policy"],
        )
    elif "LsaRights" in policy_definition:
        # Get value using the LSARights mechanism
        value = _getRightsAssignments(policy_definition["LsaRights"]["Option"])
        log.trace(
            "Value %r found for LSARights policy %s", value, policy_definition["Policy"]
        )
    elif "ScriptIni" in policy_definition:
        value = _getScriptSettingsFromIniFile(policy_definition)
        log.trace(
            "Value %r found for ScriptIni policy %s", value, policy_definition["Policy"]
        )
    else:
        message = "Unknown or missing mechanism in policy_definition\n" "{0}".format(
            policy_definition
        )
        raise CommandExecutionError(message)
    value = _transform_value(
        value=value, policy=policy_definition, transform_type="Get"
    )
    return value


def _get_policy_adm_setting(
    admx_policy,
    policy_class,
    adml_language="en-US",
    return_full_policy_names=False,
    hierarchical_return=False,
):
    """
    Get the current setting for polices set via the policy templates (ADMX/ADML)
    files

    Args:
        admx_policy (obj):
            The XPath object as returned by the ``_lookup_admin_template``
            function

        policy_class (str):
            The policy class. Must be one of ``machine`` or ``user``

        adml_language (str):
            The language code for the adml file to use for localization. The
            default is ``en-US``

        return_full_policy_names (bool):
            Returns the full policy name regardless of what was passed in
            ``policy_name``

        hierarchical_return (bool):
            Returns a hierarchical view of the policy showing its parents

    Returns:
        dict: A dictionary containing the policy settings

    Usage:
        policy_name = 'AutoUpdateCfg'
        policy_class = 'machine'
        adml_language = 'en-US'
        success, policy_obj, _, _ = _lookup_admin_template(
            policy_name=policy_name,
            policy_class=policy_class,
            adml_language=adml_language)
        if success:
            setting = _get_policy_adm_setting(
                admx_policy=policy_obj,
                policy_class=policy_class,
                adml_language=adml_language,
                return_full_policy_names=return_full_policy_names,
                hierarchical_return=hierarchical_return
            )
    """
    # TODO: Need to figure out how to get the lgpo.get function to use this code
    # TODO: as it is very similar
    # Validate policy Key and Name attributes
    this_key = admx_policy.attrib.get("key", None)
    this_policy_name = admx_policy.attrib.get("name", None)
    if this_key is None or this_policy_name is None:
        msg = (
            'Policy is missing the required "key" or "name" attribute:\n'
            "{0}".format(admx_policy.attrib)
        )
        raise CommandExecutionError(msg)

    # Get additional settings
    this_value_name = admx_policy.attrib.get("valueName", None)
    this_policy_setting = "Not Configured"
    this_policy_namespace = admx_policy.nsmap[admx_policy.prefix]

    # Set some default values, these will get flipped below
    element_only_enabled_disabled = True
    explicit_enable_disable_value_setting = False

    # Load additional data
    policy_data = _policy_info()
    policy_file_data = _read_regpol_file(
        policy_data.admx_registry_classes[policy_class]["policy_path"]
    )
    adml_policy_resources = _get_policy_resources(language=adml_language)

    policy_vals = {}

    if ENABLED_VALUE_XPATH(admx_policy) and this_policy_setting == "Not Configured":
        # some policies have a disabled list but not an enabled list
        # added this to address those issues
        if DISABLED_LIST_XPATH(admx_policy) or DISABLED_VALUE_XPATH(admx_policy):
            element_only_enabled_disabled = False
            explicit_enable_disable_value_setting = True
            if _checkValueItemParent(
                policy_element=admx_policy,
                policy_name=this_policy_name,
                policy_key=this_key,
                policy_valueName=this_value_name,
                xpath_object=ENABLED_VALUE_XPATH,
                policy_file_data=policy_file_data,
            ):
                log.trace(
                    "%s is enabled by detected ENABLED_VALUE_XPATH", this_policy_name
                )
                this_policy_setting = "Enabled"
                policy_vals.setdefault(this_policy_namespace, {})[
                    this_policy_name
                ] = this_policy_setting
    if DISABLED_VALUE_XPATH(admx_policy) and this_policy_setting == "Not Configured":
        # some policies have a disabled list but not an enabled list
        # added this to address those issues
        if ENABLED_LIST_XPATH(admx_policy) or ENABLED_VALUE_XPATH(admx_policy):
            element_only_enabled_disabled = False
            explicit_enable_disable_value_setting = True
            if _checkValueItemParent(
                policy_element=admx_policy,
                policy_name=this_policy_name,
                policy_key=this_key,
                policy_valueName=this_value_name,
                xpath_object=DISABLED_VALUE_XPATH,
                policy_file_data=policy_file_data,
            ):
                log.trace(
                    "%s is disabled by detected DISABLED_VALUE_XPATH", this_policy_name
                )
                this_policy_setting = "Disabled"
                policy_vals.setdefault(this_policy_namespace, {})[
                    this_policy_name
                ] = this_policy_setting
    if ENABLED_LIST_XPATH(admx_policy):
        if DISABLED_LIST_XPATH(admx_policy) or DISABLED_VALUE_XPATH(admx_policy):
            element_only_enabled_disabled = False
            explicit_enable_disable_value_setting = True
            if _checkListItem(
                policy_element=admx_policy,
                policy_name=this_policy_name,
                policy_key=this_key,
                xpath_object=ENABLED_LIST_XPATH,
                policy_file_data=policy_file_data,
            ):
                log.trace(
                    "%s is enabled by detected ENABLED_LIST_XPATH", this_policy_name
                )
                this_policy_setting = "Enabled"
                policy_vals.setdefault(this_policy_namespace, {})[
                    this_policy_name
                ] = this_policy_setting
    if DISABLED_LIST_XPATH(admx_policy):
        if ENABLED_LIST_XPATH(admx_policy) or ENABLED_VALUE_XPATH(admx_policy):
            element_only_enabled_disabled = False
            explicit_enable_disable_value_setting = True
            if _checkListItem(
                policy_element=admx_policy,
                policy_name=this_policy_name,
                policy_key=this_key,
                xpath_object=DISABLED_LIST_XPATH,
                policy_file_data=policy_file_data,
            ):
                log.trace(
                    "%s is disabled by detected DISABLED_LIST_XPATH", this_policy_name
                )
                this_policy_setting = "Disabled"
                policy_vals.setdefault(this_policy_namespace, {})[
                    this_policy_name
                ] = this_policy_setting

    if not explicit_enable_disable_value_setting and this_value_name:
        # the policy has a key/valuename but no explicit Enabled/Disabled
        # Value or List
        # these seem to default to a REG_DWORD 1 = "Enabled" **del. = "Disabled"
        if _regexSearchRegPolData(
            re.escape(
                _buildKnownDataSearchString(
                    reg_key=this_key,
                    reg_valueName=this_value_name,
                    reg_vtype="REG_DWORD",
                    reg_data="1",
                )
            ),
            policy_file_data,
        ):
            log.trace(
                "%s is enabled by no explicit enable/disable list or " "value",
                this_policy_name,
            )
            this_policy_setting = "Enabled"
            policy_vals.setdefault(this_policy_namespace, {})[
                this_policy_name
            ] = this_policy_setting
        elif _regexSearchRegPolData(
            re.escape(
                _buildKnownDataSearchString(
                    reg_key=this_key,
                    reg_valueName=this_value_name,
                    reg_vtype="REG_DWORD",
                    reg_data=None,
                    check_deleted=True,
                )
            ),
            policy_file_data,
        ):
            log.trace(
                "%s is disabled by no explicit enable/disable list or " "value",
                this_policy_name,
            )
            this_policy_setting = "Disabled"
            policy_vals.setdefault(this_policy_namespace, {})[
                this_policy_name
            ] = this_policy_setting

    full_names = {}
    hierarchy = {}
    if ELEMENTS_XPATH(admx_policy):
        if element_only_enabled_disabled or this_policy_setting == "Enabled":
            # TODO does this need to be modified based on the 'required' attribute?
            required_elements = {}
            configured_elements = {}
            policy_disabled_elements = 0
            for elements_item in ELEMENTS_XPATH(admx_policy):
                for child_item in elements_item.getchildren():
                    this_element_name = _getFullPolicyName(
                        policy_item=child_item,
                        policy_name=child_item.attrib["id"],
                        return_full_policy_names=return_full_policy_names,
                        adml_language=adml_language,
                    )
                    required_elements[this_element_name] = None
                    child_key = child_item.attrib.get("key", this_key)
                    child_value_name = child_item.attrib.get(
                        "valueName", this_value_name
                    )
                    if etree.QName(child_item).localname == "boolean":
                        # https://msdn.microsoft.com/en-us/library/dn605978(v=vs.85).aspx
                        if child_item.getchildren():
                            if (
                                TRUE_VALUE_XPATH(child_item)
                                and this_element_name not in configured_elements
                            ):
                                if _checkValueItemParent(
                                    policy_element=child_item,
                                    policy_name=this_policy_name,
                                    policy_key=child_key,
                                    policy_valueName=child_value_name,
                                    xpath_object=TRUE_VALUE_XPATH,
                                    policy_file_data=policy_file_data,
                                ):
                                    configured_elements[this_element_name] = True
                                    log.trace(
                                        "element %s is configured true",
                                        child_item.attrib["id"],
                                    )
                            if (
                                FALSE_VALUE_XPATH(child_item)
                                and this_element_name not in configured_elements
                            ):
                                if _checkValueItemParent(
                                    policy_element=child_item,
                                    policy_name=this_policy_name,
                                    policy_key=child_key,
                                    policy_valueName=child_value_name,
                                    xpath_object=FALSE_VALUE_XPATH,
                                    policy_file_data=policy_file_data,
                                ):
                                    configured_elements[this_element_name] = False
                                    policy_disabled_elements = (
                                        policy_disabled_elements + 1
                                    )
                                    log.trace(
                                        "element %s is configured false",
                                        child_item.attrib["id"],
                                    )
                            # WARNING - no standard ADMX files use true/falseList
                            # so this hasn't actually been tested
                            if (
                                TRUE_LIST_XPATH(child_item)
                                and this_element_name not in configured_elements
                            ):
                                log.trace("checking trueList")
                                if _checkListItem(
                                    policy_element=child_item,
                                    policy_name=this_policy_name,
                                    policy_key=this_key,
                                    xpath_object=TRUE_LIST_XPATH,
                                    policy_file_data=policy_file_data,
                                ):
                                    configured_elements[this_element_name] = True
                                    log.trace(
                                        "element %s is configured true",
                                        child_item.attrib["id"],
                                    )
                            if (
                                FALSE_LIST_XPATH(child_item)
                                and this_element_name not in configured_elements
                            ):
                                log.trace("checking falseList")
                                if _checkListItem(
                                    policy_element=child_item,
                                    policy_name=this_policy_name,
                                    policy_key=this_key,
                                    xpath_object=FALSE_LIST_XPATH,
                                    policy_file_data=policy_file_data,
                                ):
                                    configured_elements[this_element_name] = False
                                    policy_disabled_elements = (
                                        policy_disabled_elements + 1
                                    )
                                    log.trace(
                                        "element %s is configured false",
                                        child_item.attrib["id"],
                                    )
                        else:
                            if _regexSearchRegPolData(
                                re.escape(
                                    _processValueItem(
                                        element=child_item,
                                        reg_key=child_key,
                                        reg_valuename=child_value_name,
                                        policy=admx_policy,
                                        parent_element=elements_item,
                                        check_deleted=True,
                                    )
                                ),
                                policy_file_data,
                            ):
                                configured_elements[this_element_name] = False
                                policy_disabled_elements = policy_disabled_elements + 1
                                log.trace(
                                    "element %s is configured false",
                                    child_item.attrib["id"],
                                )
                            elif _regexSearchRegPolData(
                                re.escape(
                                    _processValueItem(
                                        element=child_item,
                                        reg_key=child_key,
                                        reg_valuename=child_value_name,
                                        policy=admx_policy,
                                        parent_element=elements_item,
                                        check_deleted=False,
                                    )
                                ),
                                policy_file_data,
                            ):
                                configured_elements[this_element_name] = True
                                log.trace(
                                    "element %s is configured true",
                                    child_item.attrib["id"],
                                )
                    elif etree.QName(child_item).localname in [
                        "decimal",
                        "text",
                        "longDecimal",
                        "multiText",
                    ]:
                        # https://msdn.microsoft.com/en-us/library/dn605987(v=vs.85).aspx
                        if _regexSearchRegPolData(
                            re.escape(
                                _processValueItem(
                                    element=child_item,
                                    reg_key=child_key,
                                    reg_valuename=child_value_name,
                                    policy=admx_policy,
                                    parent_element=elements_item,
                                    check_deleted=True,
                                )
                            ),
                            policy_file_data,
                        ):
                            configured_elements[this_element_name] = "Disabled"
                            policy_disabled_elements = policy_disabled_elements + 1
                            log.trace("element %s is disabled", child_item.attrib["id"])
                        elif _regexSearchRegPolData(
                            re.escape(
                                _processValueItem(
                                    element=child_item,
                                    reg_key=child_key,
                                    reg_valuename=child_value_name,
                                    policy=admx_policy,
                                    parent_element=elements_item,
                                    check_deleted=False,
                                )
                            ),
                            policy_data=policy_file_data,
                        ):
                            configured_value = _getDataFromRegPolData(
                                _processValueItem(
                                    element=child_item,
                                    reg_key=child_key,
                                    reg_valuename=child_value_name,
                                    policy=admx_policy,
                                    parent_element=elements_item,
                                    check_deleted=False,
                                ),
                                policy_data=policy_file_data,
                            )
                            configured_elements[this_element_name] = configured_value
                            log.trace(
                                "element %s is enabled, value == %s",
                                child_item.attrib["id"],
                                configured_value,
                            )
                    elif etree.QName(child_item).localname == "enum":
                        if _regexSearchRegPolData(
                            re.escape(
                                _processValueItem(
                                    element=child_item,
                                    reg_key=child_key,
                                    reg_valuename=child_value_name,
                                    policy=admx_policy,
                                    parent_element=elements_item,
                                    check_deleted=True,
                                )
                            ),
                            policy_file_data,
                        ):
                            log.trace(
                                "enum element %s is disabled", child_item.attrib["id"]
                            )
                            configured_elements[this_element_name] = "Disabled"
                            policy_disabled_elements = policy_disabled_elements + 1
                        else:
                            for enum_item in child_item.getchildren():
                                if _checkValueItemParent(
                                    policy_element=enum_item,
                                    policy_name=child_item.attrib["id"],
                                    policy_key=child_key,
                                    policy_valueName=child_value_name,
                                    xpath_object=VALUE_XPATH,
                                    policy_file_data=policy_file_data,
                                ):
                                    if VALUE_LIST_XPATH(enum_item):
                                        log.trace("enum item has a valueList")
                                        if _checkListItem(
                                            policy_element=enum_item,
                                            policy_name=this_policy_name,
                                            policy_key=child_key,
                                            xpath_object=VALUE_LIST_XPATH,
                                            policy_file_data=policy_file_data,
                                        ):
                                            log.trace(
                                                "all valueList items exist in file"
                                            )
                                            configured_elements[
                                                this_element_name
                                            ] = _getAdmlDisplayName(
                                                adml_xml_data=adml_policy_resources,
                                                display_name=enum_item.attrib[
                                                    "displayName"
                                                ],
                                            )
                                            break
                                    else:
                                        configured_elements[
                                            this_element_name
                                        ] = _getAdmlDisplayName(
                                            adml_xml_data=adml_policy_resources,
                                            display_name=enum_item.attrib[
                                                "displayName"
                                            ],
                                        )
                                        break
                    elif etree.QName(child_item).localname == "list":
                        return_value_name = False
                        if (
                            "explicitValue" in child_item.attrib
                            and child_item.attrib["explicitValue"].lower() == "true"
                        ):
                            log.trace("explicitValue list, we will return value names")
                            return_value_name = True
                        if _regexSearchRegPolData(
                            re.escape(
                                _processValueItem(
                                    element=child_item,
                                    reg_key=child_key,
                                    reg_valuename=child_value_name,
                                    policy=admx_policy,
                                    parent_element=elements_item,
                                    check_deleted=False,
                                )
                            )
                            + salt.utils.stringutils.to_bytes(r"(?!\*\*delvals\.)"),
                            policy_data=policy_file_data,
                        ):
                            configured_value = _getDataFromRegPolData(
                                _processValueItem(
                                    element=child_item,
                                    reg_key=child_key,
                                    reg_valuename=child_value_name,
                                    policy=admx_policy,
                                    parent_element=elements_item,
                                    check_deleted=False,
                                ),
                                policy_data=policy_file_data,
                                return_value_name=return_value_name,
                            )
                            configured_elements[this_element_name] = configured_value
                            log.trace(
                                "element %s is enabled values: %s",
                                child_item.attrib["id"],
                                configured_value,
                            )
                        elif _regexSearchRegPolData(
                            re.escape(
                                _processValueItem(
                                    element=child_item,
                                    reg_key=child_key,
                                    reg_valuename=child_value_name,
                                    policy=admx_policy,
                                    parent_element=elements_item,
                                    check_deleted=True,
                                )
                            ),
                            policy_file_data,
                        ):
                            configured_elements[this_element_name] = "Disabled"
                            policy_disabled_elements = policy_disabled_elements + 1
                            log.trace(
                                "element {0} is disabled".format(
                                    child_item.attrib["id"]
                                )
                            )
            if element_only_enabled_disabled:
                if len(required_elements.keys()) > 0 and len(
                    configured_elements.keys()
                ) == len(required_elements.keys()):
                    if policy_disabled_elements == len(required_elements.keys()):
                        log.trace(
                            "{0} is disabled by all enum elements".format(
                                this_policy_name
                            )
                        )
                        policy_vals.setdefault(this_policy_namespace, {})[
                            this_policy_name
                        ] = "Disabled"
                    else:
                        log.trace(
                            "{0} is enabled by enum elements".format(this_policy_name)
                        )
                        policy_vals.setdefault(this_policy_namespace, {})[
                            this_policy_name
                        ] = configured_elements
                else:
                    policy_vals.setdefault(this_policy_namespace, {})[
                        this_policy_name
                    ] = this_policy_setting
            else:
                if this_policy_setting == "Enabled":
                    policy_vals.setdefault(this_policy_namespace, {})[
                        this_policy_name
                    ] = configured_elements
        else:
            policy_vals.setdefault(this_policy_namespace, {})[
                this_policy_name
            ] = this_policy_setting
    else:
        policy_vals.setdefault(this_policy_namespace, {})[
            this_policy_name
        ] = this_policy_setting

    if (
        return_full_policy_names
        and this_policy_namespace in policy_vals
        and this_policy_name in policy_vals[this_policy_namespace]
    ):
        full_names.setdefault(this_policy_namespace, {})
        full_names[this_policy_namespace][this_policy_name] = _getFullPolicyName(
            policy_item=admx_policy,
            policy_name=admx_policy.attrib["name"],
            return_full_policy_names=return_full_policy_names,
            adml_language=adml_language,
        )
        # Make sure the we're passing the full policy name
        # This issue was found when setting the `Allow Telemetry` setting
        # All following states would show a change in this setting
        # When the state does it's first `lgpo.get` it would return `AllowTelemetry`
        # On the second run, it would return `Allow Telemetry`
        # This makes sure we're always returning the full_name when required
        if this_policy_name in policy_vals[this_policy_namespace][this_policy_name]:
            full_name = full_names[this_policy_namespace][this_policy_name]
            setting = policy_vals[this_policy_namespace][this_policy_name].pop(
                this_policy_name
            )
            policy_vals[this_policy_namespace][this_policy_name][full_name] = setting

    if (
        this_policy_namespace in policy_vals
        and this_policy_name in policy_vals[this_policy_namespace]
    ):
        hierarchy.setdefault(this_policy_namespace, {})[
            this_policy_name
        ] = _build_parent_list(
            policy_definition=admx_policy,
            return_full_policy_names=return_full_policy_names,
            adml_language=adml_language,
        )

    if policy_vals and return_full_policy_names and not hierarchical_return:
        log.debug("Compiling non hierarchical return...")
        unpathed_dict = {}
        pathed_dict = {}
        for policy_namespace in list(policy_vals):
            for policy_item in list(policy_vals[policy_namespace]):
                full_name = full_names[policy_namespace][policy_item]
                if full_name in policy_vals[policy_namespace]:
                    # add this item with the path'd full name
                    full_path_list = hierarchy[policy_namespace][policy_item]
                    full_path_list.reverse()
                    full_path_list.append(full_names[policy_namespace][policy_item])
                    policy_vals["\\".join(full_path_list)] = policy_vals[
                        policy_namespace
                    ].pop(policy_item)
                    pathed_dict[full_name] = True
                else:
                    policy_vals[policy_namespace][full_name] = policy_vals[
                        policy_namespace
                    ].pop(policy_item)
                    unpathed_dict.setdefault(policy_namespace, {})[
                        full_name
                    ] = policy_item
            # go back and remove any "unpathed" policies that need a full path
            for path_needed in unpathed_dict[policy_namespace]:
                # remove the item with the same full name and re-add it w/a path'd version
                full_path_list = hierarchy[policy_namespace][
                    unpathed_dict[policy_namespace][path_needed]
                ]
                full_path_list.reverse()
                full_path_list.append(path_needed)
                log.trace("full_path_list == %s", full_path_list)
                policy_vals["\\".join(full_path_list)] = policy_vals[
                    policy_namespace
                ].pop(path_needed)

    for policy_namespace in list(policy_vals):
        # Remove empty entries
        if policy_vals[policy_namespace] == {}:
            policy_vals.pop(policy_namespace)
        # Remove namespace and keep the values
        elif isinstance(policy_vals[policy_namespace], dict):
            if this_policy_namespace == policy_namespace and not hierarchical_return:
                policy_vals.update(policy_vals[policy_namespace])
                policy_vals.pop(policy_namespace)

    if policy_vals and hierarchical_return:
        if hierarchy:
            log.debug("Compiling hierarchical return...")
            for policy_namespace in hierarchy:
                for hierarchy_item in hierarchy[policy_namespace]:
                    if hierarchy_item in policy_vals[policy_namespace]:
                        t_dict = {}
                        first_item = True
                        for item in hierarchy[policy_namespace][hierarchy_item]:
                            new_dict = {}
                            if first_item:
                                h_policy_name = hierarchy_item
                                if return_full_policy_names:
                                    h_policy_name = full_names[policy_namespace][
                                        hierarchy_item
                                    ]
                                new_dict[item] = {
                                    h_policy_name: policy_vals[policy_namespace].pop(
                                        hierarchy_item
                                    )
                                }
                                first_item = False
                            else:
                                new_dict[item] = t_dict
                            t_dict = new_dict
                        if t_dict:
                            policy_vals = dictupdate.update(policy_vals, t_dict)
                if (
                    policy_namespace in policy_vals
                    and policy_vals[policy_namespace] == {}
                ):
                    policy_vals.pop(policy_namespace)
        policy_vals = {
            policy_data.admx_registry_classes[policy_class]["lgpo_section"]: {
                "Administrative Templates": policy_vals
            }
        }

    return policy_vals


def get_policy(
    policy_name,
    policy_class,
    adml_language="en-US",
    return_value_only=True,
    return_full_policy_names=True,
    hierarchical_return=False,
):
    r"""
    Get the current settings for a single policy on the machine

    Args:
        policy_name (str):
            The name of the policy to retrieve. Can be the any of the names
            or alieses returned by ``lgpo.get_policy_info``

        policy_class (str):
            The policy class. Must be one of ``machine`` or ``user``

        adml_language (str):
            The language code for the adml file to use for localization. The
            default is ``en-US``

        return_value_only (bool):
            ``True`` will return only the value for the policy, without the
            name of the policy. ``return_full_policy_names`` and
            ``hierarchical_return`` will be ignored. Default is ``True``

        return_full_policy_names (bool):
            Returns the full policy name regardless of what was passed in
            ``policy_name``

            .. note::
                This setting applies to sub-elements of the policy if they
                exist. The value passed in ``policy_name`` will always be used
                as the policy name when this setting is ``False``

        hierarchical_return (bool):
            Returns a hierarchical view of the policy showing its parents

    Returns:
        dict: A dictionary containing the policy settings

    CLI Example:

    .. code-block:: bash

        # Using the policy id
        salt * lgpo.get_policy LockoutDuration machine
        salt * lgpo.get_policy AutoUpdateCfg machine

        # Using the full name
        salt * lgpo.get_policy "Account lockout duration" machine
        salt * lgpo.get_policy "Configure Automatic Updates" machine

        # Using full path and name
        salt * lgpo.get_policy "Windows Components\Windows Update\Configure Automatic Updates" machine
    """
    if not policy_name:
        raise SaltInvocationError("policy_name must be defined")
    if not policy_class:
        raise SaltInvocationError("policy_class must be defined")
    policy_class = policy_class.title()
    policy_data = _policy_info()
    if policy_class not in policy_data.policies.keys():
        policy_classes = ", ".join(policy_data.policies.keys())
        message = (
            'The requested policy class "{0}" is invalid, policy_class '
            "should be one of: {1}".format(policy_class, policy_classes)
        )
        raise CommandExecutionError(message)

    # Look in the _policy_data object first
    policy_definition = None
    if policy_name in policy_data.policies[policy_class]["policies"]:
        policy_definition = policy_data.policies[policy_class]["policies"][policy_name]
    else:
        for pol in policy_data.policies[policy_class]["policies"]:
            if (
                policy_data.policies[policy_class]["policies"][pol]["Policy"].lower()
                == policy_name.lower()
            ):
                policy_definition = policy_data.policies[policy_class]["policies"][pol]
                break
    if policy_definition:
        if return_value_only:
            return _get_policy_info_setting(policy_definition)
        if return_full_policy_names:
            key_name = policy_definition["Policy"]
        else:
            key_name = policy_name
        setting = {key_name: _get_policy_info_setting(policy_definition)}
        if hierarchical_return:
            if "lgpo_section" in policy_definition:
                first_item = True
                t_dict = {}
                for level in reversed(policy_definition["lgpo_section"]):
                    new_dict = {}
                    if first_item:
                        new_dict[level] = {key_name: setting.pop(key_name)}
                        first_item = False
                    else:
                        new_dict[level] = t_dict
                    t_dict = new_dict
                if t_dict:
                    setting = t_dict

        return setting

    success, policy_obj, _, _ = _lookup_admin_template(
        policy_name=policy_name, policy_class=policy_class, adml_language=adml_language
    )
    if success:
        setting = _get_policy_adm_setting(
            admx_policy=policy_obj,
            policy_class=policy_class,
            adml_language=adml_language,
            return_full_policy_names=return_full_policy_names,
            hierarchical_return=hierarchical_return,
        )
        if return_value_only:
            for key in setting:
                return setting[key]
        return setting


def set_computer_policy(
    name, setting, cumulative_rights_assignments=True, adml_language="en-US"
):
    """
    Set a single computer policy

    Args:
        name (str):
            The name of the policy to configure

        setting (str):
            The setting to configure the named policy with

        cumulative_rights_assignments (bool): Determine how user rights
            assignment policies are configured. If True, user right assignment
            specifications are simply added to the existing policy. If False,
            only the users specified will get the right (any existing will have
            the right revoked)

        adml_language (str): The language files to use for looking up
            Administrative Template policy data (i.e. how the policy is
            displayed in the GUI).  Defaults to 'en-US' (U.S. English).

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' lgpo.set_computer_policy LockoutDuration 1440
    """
    pol = {}
    pol[name] = setting
    ret = set_(
        computer_policy=pol,
        user_policy=None,
        cumulative_rights_assignments=cumulative_rights_assignments,
        adml_language=adml_language,
    )
    return ret


def set_user_policy(name, setting, adml_language="en-US"):
    """
    Set a single user policy

    Args:

        name (str):
            The name of the policy to configure

        setting (str):
            The setting to configure the named policy with

        adml_language (str):
            The language files to use for looking up Administrative Template
            policy data (i.e. how the policy is displayed in the GUI). Defaults
            to 'en-US' (U.S. English).

    Returns:
        bool: True if successful, Otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' lgpo.set_user_policy "Control Panel\\Display\\Disable the Display Control Panel" Enabled
    """
    pol = {}
    pol[name] = setting
    ret = set_(
        user_policy=pol,
        computer_policy=None,
        cumulative_rights_assignments=True,
        adml_language=adml_language,
    )
    return ret


def set_(
    computer_policy=None,
    user_policy=None,
    cumulative_rights_assignments=True,
    adml_language="en-US",
):
    """
    Set a local server policy.

    Args:

        computer_policy (dict):
            A dictionary of "policyname: value" pairs of computer policies to
            set. 'value' should be how it is displayed in the gpedit GUI, i.e.
            if a setting can be 'Enabled'/'Disabled', then that should be passed

            Administrative Template data may require dicts within dicts, to
            specify each element of the Administrative Template policy.
            Administrative Templates policies are always cumulative.

            Policy names can be specified in a number of ways based on the type
            of policy:

                Windows Settings Policies:

                    These policies can be specified using the GUI display name
                    or the key name from the _policy_info class in this module.
                    The GUI display name is also contained in the _policy_info
                    class in this module.

                Administrative Template Policies:

                    These can be specified using the policy name as displayed in
                    the GUI (case sensitive). Some policies have the same name,
                    but a different location (for example, "Access data sources
                    across domains"). These can be differentiated by the "path"
                    in the GUI (for example, "Windows Components\\Internet
                    Explorer\\Internet Control Panel\\Security Page\\Internet
                    Zone\\Access data sources across domains").

                    Additionally, policies can be specified using the "name" and
                    "id" attributes from the ADMX files.

                    For Administrative Templates that have policy elements, each
                    element can be specified using the text string as seen in
                    the GUI or using the ID attribute from the ADMX file. Due to
                    the way some of the GUI text is laid out, some policy
                    element names could include descriptive text that appears
                    lbefore the policy element in the GUI.

                    Use the get_policy_info function for the policy name to view
                    the element ID/names that the module will accept.

        user_policy (dict):
            The same setup as the computer_policy, except with data to configure
            the local user policy.

        cumulative_rights_assignments (bool):
            Determine how user rights assignment policies are configured.

            If True, user right assignment specifications are simply added to
            the existing policy

            If False, only the users specified will get the right (any existing
            will have the right revoked)

        adml_language (str):
            The language files to use for looking up Administrative Template
            policy data (i.e. how the policy is displayed in the GUI). Defaults
            to 'en-US' (U.S. English).

    Returns:
        bool: True is successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' lgpo.set computer_policy="{'LockoutDuration': 2, 'RestrictAnonymous': 'Enabled', 'AuditProcessTracking': 'Succes, Failure'}"
    """

    if computer_policy and not isinstance(computer_policy, dict):
        msg = "computer_policy must be specified as a dict"
        raise SaltInvocationError(msg)
    if user_policy and not isinstance(user_policy, dict):
        msg = "user_policy must be specified as a dict"
        raise SaltInvocationError(msg)
    policies = {}
    policies["User"] = user_policy
    policies["Machine"] = computer_policy
    if policies:
        adml_policy_resources = _get_policy_resources(language=adml_language)
        for p_class in policies:
            _secedits = {}
            _netshs = {}
            _advaudits = {}
            _modal_sets = {}
            _admTemplateData = {}
            _regedits = {}
            _lsarights = {}
            _policydata = _policy_info()
            if policies[p_class]:
                for policy_name in policies[p_class]:
                    _pol = None
                    policy_key_name = policy_name
                    if policy_name in _policydata.policies[p_class]["policies"]:
                        _pol = _policydata.policies[p_class]["policies"][policy_name]
                    else:
                        for policy in _policydata.policies[p_class]["policies"]:
                            if (
                                _policydata.policies[p_class]["policies"][policy][
                                    "Policy"
                                ].upper()
                                == policy_name.upper()
                            ):
                                _pol = _policydata.policies[p_class]["policies"][policy]
                                policy_key_name = policy
                    if _pol:
                        # transform and validate the setting
                        _value = _transform_value(
                            value=policies[p_class][policy_name],
                            policy=_policydata.policies[p_class]["policies"][
                                policy_key_name
                            ],
                            transform_type="Put",
                        )
                        if not _validateSetting(
                            value=_value,
                            policy=_policydata.policies[p_class]["policies"][
                                policy_key_name
                            ],
                        ):
                            msg = "The specified value {0} is not an acceptable setting for policy {1}."
                            raise SaltInvocationError(
                                msg.format(policies[p_class][policy_name], policy_name)
                            )
                        if "Registry" in _pol:
                            # set value in registry
                            log.trace("%s is a registry policy", policy_name)
                            _regedits[policy_name] = {"policy": _pol, "value": _value}
                        elif "Secedit" in _pol:
                            # set value with secedit
                            log.trace("%s is a Secedit policy", policy_name)
                            if _pol["Secedit"]["Section"] not in _secedits:
                                _secedits[_pol["Secedit"]["Section"]] = []
                            _secedits[_pol["Secedit"]["Section"]].append(
                                " ".join(
                                    [
                                        _pol["Secedit"]["Option"],
                                        "=",
                                        six.text_type(_value),
                                    ]
                                )
                            )
                        elif "NetSH" in _pol:
                            # set value with netsh
                            log.trace("%s is a NetSH policy", policy_name)
                            _netshs.setdefault(
                                policy_name,
                                {
                                    "profile": _pol["NetSH"]["Profile"],
                                    "section": _pol["NetSH"]["Section"],
                                    "option": _pol["NetSH"]["Option"],
                                    "value": six.text_type(_value),
                                },
                            )
                        elif "AdvAudit" in _pol:
                            # set value with advaudit
                            _advaudits.setdefault(
                                policy_name,
                                {
                                    "option": _pol["AdvAudit"]["Option"],
                                    "value": six.text_type(_value),
                                },
                            )
                        elif "NetUserModal" in _pol:
                            # set value via NetUserModal
                            log.trace("%s is a NetUserModal policy", policy_name)
                            if _pol["NetUserModal"]["Modal"] not in _modal_sets:
                                _modal_sets[_pol["NetUserModal"]["Modal"]] = {}
                            _modal_sets[_pol["NetUserModal"]["Modal"]][
                                _pol["NetUserModal"]["Option"]
                            ] = _value
                        elif "LsaRights" in _pol:
                            log.trace("%s is a LsaRights policy", policy_name)
                            _lsarights[policy_name] = {"policy": _pol, "value": _value}
                    else:
                        _value = policies[p_class][policy_name]
                        log.trace('searching for "%s" in admx data', policy_name)
                        (
                            success,
                            the_policy,
                            policy_name_list,
                            msg,
                        ) = _lookup_admin_template(
                            policy_name=policy_name,
                            policy_class=p_class,
                            adml_language=adml_language,
                        )
                        if success:
                            policy_name = the_policy.attrib["name"]
                            policy_namespace = the_policy.nsmap[the_policy.prefix]
                            if policy_namespace not in _admTemplateData:
                                _admTemplateData[policy_namespace] = {}
                            _admTemplateData[policy_namespace][policy_name] = _value
                        else:
                            raise SaltInvocationError(msg)
                        if (
                            policy_namespace
                            and policy_name in _admTemplateData[policy_namespace]
                            and the_policy is not None
                        ):
                            log.trace(
                                "setting == %s",
                                six.text_type(
                                    _admTemplateData[policy_namespace][policy_name]
                                ).lower(),
                            )
                            log.trace(
                                six.text_type(
                                    _admTemplateData[policy_namespace][policy_name]
                                ).lower()
                            )
                            if (
                                six.text_type(
                                    _admTemplateData[policy_namespace][policy_name]
                                ).lower()
                                != "disabled"
                                and six.text_type(
                                    _admTemplateData[policy_namespace][policy_name]
                                ).lower()
                                != "not configured"
                            ):
                                if ELEMENTS_XPATH(the_policy):
                                    if isinstance(
                                        _admTemplateData[policy_namespace][policy_name],
                                        dict,
                                    ):
                                        for elements_item in ELEMENTS_XPATH(the_policy):
                                            for (
                                                child_item
                                            ) in elements_item.getchildren():
                                                # check each element
                                                log.trace(
                                                    "checking element %s",
                                                    child_item.attrib["id"],
                                                )
                                                temp_element_name = None
                                                this_element_name = _getFullPolicyName(
                                                    policy_item=child_item,
                                                    policy_name=child_item.attrib["id"],
                                                    return_full_policy_names=True,
                                                    adml_language=adml_language,
                                                )
                                                log.trace(
                                                    'id attribute == "%s"  this_element_name == "%s"',
                                                    child_item.attrib["id"],
                                                    this_element_name,
                                                )
                                                if (
                                                    this_element_name
                                                    in _admTemplateData[
                                                        policy_namespace
                                                    ][policy_name]
                                                ):
                                                    temp_element_name = (
                                                        this_element_name
                                                    )
                                                elif (
                                                    child_item.attrib["id"]
                                                    in _admTemplateData[
                                                        policy_namespace
                                                    ][policy_name]
                                                ):
                                                    temp_element_name = child_item.attrib[
                                                        "id"
                                                    ]
                                                else:
                                                    msg = (
                                                        'Element "{0}" must be included'
                                                        " in the policy configuration for policy {1}"
                                                    )
                                                    raise SaltInvocationError(
                                                        msg.format(
                                                            this_element_name,
                                                            policy_name,
                                                        )
                                                    )
                                                if (
                                                    "required" in child_item.attrib
                                                    and child_item.attrib[
                                                        "required"
                                                    ].lower()
                                                    == "true"
                                                ):
                                                    if not _admTemplateData[
                                                        policy_namespace
                                                    ][policy_name][temp_element_name]:
                                                        msg = 'Element "{0}" requires a value to be specified'
                                                        raise SaltInvocationError(
                                                            msg.format(
                                                                temp_element_name
                                                            )
                                                        )
                                                if (
                                                    etree.QName(child_item).localname
                                                    == "boolean"
                                                ):
                                                    if not isinstance(
                                                        _admTemplateData[
                                                            policy_namespace
                                                        ][policy_name][
                                                            temp_element_name
                                                        ],
                                                        bool,
                                                    ):
                                                        msg = "Element {0} requires a boolean True or False"
                                                        raise SaltInvocationError(
                                                            msg.format(
                                                                temp_element_name
                                                            )
                                                        )
                                                elif (
                                                    etree.QName(child_item).localname
                                                    == "decimal"
                                                    or etree.QName(child_item).localname
                                                    == "longDecimal"
                                                ):
                                                    min_val = 0
                                                    max_val = 9999
                                                    if "minValue" in child_item.attrib:
                                                        min_val = int(
                                                            child_item.attrib[
                                                                "minValue"
                                                            ]
                                                        )
                                                    if "maxValue" in child_item.attrib:
                                                        max_val = int(
                                                            child_item.attrib[
                                                                "maxValue"
                                                            ]
                                                        )
                                                    if (
                                                        int(
                                                            _admTemplateData[
                                                                policy_namespace
                                                            ][policy_name][
                                                                temp_element_name
                                                            ]
                                                        )
                                                        < min_val
                                                        or int(
                                                            _admTemplateData[
                                                                policy_namespace
                                                            ][policy_name][
                                                                temp_element_name
                                                            ]
                                                        )
                                                        > max_val
                                                    ):
                                                        msg = 'Element "{0}" value must be between {1} and {2}'
                                                        raise SaltInvocationError(
                                                            msg.format(
                                                                temp_element_name,
                                                                min_val,
                                                                max_val,
                                                            )
                                                        )
                                                elif (
                                                    etree.QName(child_item).localname
                                                    == "enum"
                                                ):
                                                    # make sure the value is in the enumeration
                                                    found = False
                                                    for (
                                                        enum_item
                                                    ) in child_item.getchildren():
                                                        if (
                                                            _admTemplateData[
                                                                policy_namespace
                                                            ][policy_name][
                                                                temp_element_name
                                                            ]
                                                            == _getAdmlDisplayName(
                                                                adml_policy_resources,
                                                                enum_item.attrib[
                                                                    "displayName"
                                                                ],
                                                            ).strip()
                                                        ):
                                                            found = True
                                                            break
                                                    if not found:
                                                        msg = 'Element "{0}" does not have a valid value'
                                                        raise SaltInvocationError(
                                                            msg.format(
                                                                temp_element_name
                                                            )
                                                        )
                                                elif (
                                                    etree.QName(child_item).localname
                                                    == "list"
                                                ):
                                                    if (
                                                        "explicitValue"
                                                        in child_item.attrib
                                                        and child_item.attrib[
                                                            "explicitValue"
                                                        ].lower()
                                                        == "true"
                                                    ):
                                                        if not isinstance(
                                                            _admTemplateData[
                                                                policy_namespace
                                                            ][policy_name][
                                                                temp_element_name
                                                            ],
                                                            dict,
                                                        ):
                                                            msg = (
                                                                'Each list item of element "{0}" '
                                                                "requires a dict value"
                                                            )
                                                            msg = msg.format(
                                                                temp_element_name
                                                            )
                                                            raise SaltInvocationError(
                                                                msg
                                                            )
                                                    elif not isinstance(
                                                        _admTemplateData[
                                                            policy_namespace
                                                        ][policy_name][
                                                            temp_element_name
                                                        ],
                                                        list,
                                                    ):
                                                        msg = 'Element "{0}" requires a list value'
                                                        msg = msg.format(
                                                            temp_element_name
                                                        )
                                                        raise SaltInvocationError(msg)
                                                elif (
                                                    etree.QName(child_item).localname
                                                    == "multiText"
                                                ):
                                                    if not isinstance(
                                                        _admTemplateData[
                                                            policy_namespace
                                                        ][policy_name][
                                                            temp_element_name
                                                        ],
                                                        list,
                                                    ):
                                                        msg = 'Element "{0}" requires a list value'
                                                        msg = msg.format(
                                                            temp_element_name
                                                        )
                                                        raise SaltInvocationError(msg)
                                                _admTemplateData[policy_namespace][
                                                    policy_name
                                                ][
                                                    child_item.attrib["id"]
                                                ] = _admTemplateData[
                                                    policy_namespace
                                                ][
                                                    policy_name
                                                ].pop(
                                                    temp_element_name
                                                )
                                    else:
                                        msg = 'The policy "{0}" has elements which must be configured'
                                        msg = msg.format(policy_name)
                                        raise SaltInvocationError(msg)
                                else:
                                    if (
                                        six.text_type(
                                            _admTemplateData[policy_namespace][
                                                policy_name
                                            ]
                                        ).lower()
                                        != "enabled"
                                    ):
                                        msg = (
                                            'The policy {0} must either be "Enabled", '
                                            '"Disabled", or "Not Configured"'
                                        )
                                        msg = msg.format(policy_name)
                                        raise SaltInvocationError(msg)
                if _regedits:
                    for regedit in _regedits:
                        log.trace("%s is a Registry policy", regedit)
                        # if the value setting is None or "(value not set)", we will delete the value from the registry
                        if (
                            _regedits[regedit]["value"] is not None
                            and _regedits[regedit]["value"] != "(value not set)"
                        ):
                            _ret = __salt__["reg.set_value"](
                                _regedits[regedit]["policy"]["Registry"]["Hive"],
                                _regedits[regedit]["policy"]["Registry"]["Path"],
                                _regedits[regedit]["policy"]["Registry"]["Value"],
                                _regedits[regedit]["value"],
                                _regedits[regedit]["policy"]["Registry"]["Type"],
                            )
                        else:
                            _ret = __salt__["reg.read_value"](
                                _regedits[regedit]["policy"]["Registry"]["Hive"],
                                _regedits[regedit]["policy"]["Registry"]["Path"],
                                _regedits[regedit]["policy"]["Registry"]["Value"],
                            )
                            if _ret["success"] and _ret["vdata"] != "(value not set)":
                                _ret = __salt__["reg.delete_value"](
                                    _regedits[regedit]["policy"]["Registry"]["Hive"],
                                    _regedits[regedit]["policy"]["Registry"]["Path"],
                                    _regedits[regedit]["policy"]["Registry"]["Value"],
                                )
                        if not _ret:
                            msg = (
                                "Error while attempting to set policy {0} via the registry."
                                "  Some changes may not be applied as expected"
                            )
                            raise CommandExecutionError(msg.format(regedit))
                if _lsarights:
                    for lsaright in _lsarights:
                        _existingUsers = None
                        if not cumulative_rights_assignments:
                            _existingUsers = _getRightsAssignments(
                                _lsarights[lsaright]["policy"]["LsaRights"]["Option"]
                            )
                        if _lsarights[lsaright]["value"]:
                            for acct in _lsarights[lsaright]["value"]:
                                _ret = _addAccountRights(
                                    acct,
                                    _lsarights[lsaright]["policy"]["LsaRights"][
                                        "Option"
                                    ],
                                )
                                if not _ret:
                                    msg = "An error occurred attempting to configure the user right {0}."
                                    raise SaltInvocationError(msg.format(lsaright))
                        if _existingUsers:
                            for acct in _existingUsers:
                                if acct not in _lsarights[lsaright]["value"]:
                                    _ret = _delAccountRights(
                                        acct,
                                        _lsarights[lsaright]["policy"]["LsaRights"][
                                            "Option"
                                        ],
                                    )
                                    if not _ret:
                                        msg = (
                                            "An error occurred attempting to remove previously"
                                            "configured users with right {0}."
                                        )
                                        raise SaltInvocationError(msg.format(lsaright))
                if _secedits:
                    # we've got secedits to make
                    log.trace(_secedits)
                    ini_data = "\r\n".join(["[Unicode]", "Unicode=yes"])
                    _seceditSections = [
                        "System Access",
                        "Event Audit",
                        "Registry Values",
                        "Privilege Rights",
                    ]
                    for _seceditSection in _seceditSections:
                        if _seceditSection in _secedits:
                            ini_data = "\r\n".join(
                                [
                                    ini_data,
                                    "".join(["[", _seceditSection, "]"]),
                                    "\r\n".join(_secedits[_seceditSection]),
                                ]
                            )
                    ini_data = "\r\n".join(
                        [ini_data, "[Version]", 'signature="$CHICAGO$"', "Revision=1"]
                    )
                    log.trace("ini_data == %s", ini_data)
                    if not _write_secedit_data(ini_data):
                        msg = (
                            "Error while attempting to set policies via "
                            "secedit. Some changes may not be applied as "
                            "expected"
                        )
                        raise CommandExecutionError(msg)
                if _netshs:
                    # we've got netsh settings to make
                    for setting in _netshs:
                        log.trace("Setting firewall policy: {0}".format(setting))
                        log.trace(_netshs[setting])
                        _set_netsh_value(**_netshs[setting])

                if _advaudits:
                    # We've got AdvAudit settings to make
                    for setting in _advaudits:
                        log.trace("Setting Advanced Audit policy: {0}".format(setting))
                        log.trace(_advaudits[setting])
                        _set_advaudit_value(**_advaudits[setting])

                if _modal_sets:
                    # we've got modalsets to make
                    log.trace(_modal_sets)
                    for _modal_set in _modal_sets:
                        try:
                            _existingModalData = win32net.NetUserModalsGet(
                                None, _modal_set
                            )
                            _newModalSetData = dictupdate.update(
                                _existingModalData, _modal_sets[_modal_set]
                            )
                            log.trace("NEW MODAL SET = %s", _newModalSetData)
                            _ret = win32net.NetUserModalsSet(
                                None, _modal_set, _newModalSetData
                            )
                        # TODO: This needs to be more specific
                        except Exception as exc:  # pylint: disable=broad-except
                            msg = (
                                "An unhandled exception occurred while "
                                "attempting to set policy via "
                                "NetUserModalSet\n{0}".format(exc)
                            )
                            log.exception(msg)
                            raise CommandExecutionError(msg)
                if _admTemplateData:
                    _ret = False
                    log.trace(
                        "going to write some adm template data :: %s", _admTemplateData
                    )
                    _ret = _writeAdminTemplateRegPolFile(
                        _admTemplateData,
                        adml_language=adml_language,
                        registry_class=p_class,
                    )
                    if not _ret:
                        msg = (
                            "Error while attempting to write Administrative Template Policy data."
                            "  Some changes may not be applied as expected"
                        )
                        raise CommandExecutionError(msg)
        return True
    else:
        msg = "You have to specify something!"
        raise SaltInvocationError(msg)
