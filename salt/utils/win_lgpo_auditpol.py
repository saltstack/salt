r"""
A salt util for modifying the audit policies on the machine. This util is used
by the ``win_auditpol`` and ``win_lgpo`` modules.

Though this utility does not set group policy for auditing, it displays how all
auditing configuration is applied on the machine, either set directly or via
local or domain group policy.

.. versionadded:: 2018.3.4
.. versionadded:: 2019.2.1

Audit policy is read and written using the Windows ``advapi32`` APIs
(``AuditQuerySystemPolicy`` / ``AuditSetSystemPolicy``) with a static
subcategory GUID to English name map, so behavior is consistent regardless of
the host OS display language.

This util allows you to view and modify the audit settings as they are applied
on the machine. The audit settings are broken down into nine categories:

- Account Logon
- Account Management
- Detailed Tracking
- DS Access
- Logon/Logoff
- Object Access
- Policy Change
- Privilege Use
- System

The ``get_settings`` function will return the subcategories for all nine of
the above categories in one dictionary along with their auditing status.

Subcategory names are **canonical English** strings (they match the names Salt
and LGPO use, not the host OS localized ``auditpol`` display names).

To modify a setting you only need to specify the subcategory name and the value
you wish to set. Valid settings are:

- No Auditing
- Success
- Failure
- Success and Failure

The module constant ``settings`` maps those English labels to the integer
**auditing bitmask** passed to ``AuditSetSystemPolicy`` (``0``–``3``, aligned
with LGPO ``audit.csv`` ``Setting Value``). Execution modules should keep
using the string labels; callers should not rely on ``settings`` values being
``auditpol.exe`` switch strings.

LGPO loads defaults via :func:`get_advaudit_policy_rows`; :func:`get_auditpol_dump`
serializes the same data as UTF-8 CSV lines for backward compatibility.

Usage:

.. code-block:: python

    import salt.utils.win_lgpo_auditpol

    # Get current state of all audit settings
    salt.utils.win_lgpo_auditpol.get_settings()

    # Get the current state of all audit settings in the "Account Logon"
    # category
    salt.utils.win_lgpo_auditpol.get_settings(category="Account Logon")

    # Get current state of the "Credential Validation" setting
    salt.utils.win_lgpo_auditpol.get_setting(name='Credential Validation')

    # Set the state of the "Credential Validation" setting to Success and
    # Failure
    salt.utils.win_lgpo_auditpol.set_setting(name='Credential Validation',
                                             value='Success and Failure')

    # Set the state of the "Credential Validation" setting to No Auditing
    salt.utils.win_lgpo_auditpol.set_setting(name='Credential Validation',
                                             value='No Auditing')
"""

from __future__ import annotations

import contextlib
import csv
import ctypes
import io
import logging
import struct
import uuid
from ctypes import wintypes as w
from types import SimpleNamespace

import salt.utils.platform
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)
__virtualname__ = "auditpol"
__context__ = {}

categories = [
    "Account Logon",
    "Account Management",
    "Detailed Tracking",
    "DS Access",
    "Logon/Logoff",
    "Object Access",
    "Policy Change",
    "Privilege Use",
    "System",
]

# English value label -> bitmask for AuditSetSystemPolicy (matches LGPO 0–3)
settings = {
    "No Auditing": 0,
    "Success": 1,
    "Failure": 2,
    "Success and Failure": 3,
}

_AUDIT_NONE = 0
_AUDIT_SUCCESS = 1
_AUDIT_FAILURE = 2

_TOKEN_QUERY = 0x0008
_TOKEN_ADJUST_PRIVILEGES = 0x0020
_SE_PRIVILEGE_ENABLED = 0x00000002

_FIELDNAMES = [
    "Machine Name",
    "Policy Target",
    "Subcategory",
    "Subcategory GUID",
    "Inclusion Setting",
    "Exclusion Setting",
    "Setting Value",
]


class _GUID(ctypes.Structure):
    """Win32 ``GUID`` layout (``Data1``..``Data4``) for ``Audit*`` APIs."""

    _fields_ = [
        ("Data1", w.DWORD),
        ("Data2", w.WORD),
        ("Data3", w.WORD),
        ("Data4", w.BYTE * 8),
    ]


class _AUDIT_POLICY_INFORMATION(ctypes.Structure):
    """``AUDIT_POLICY_INFORMATION`` from ntsecapi / advapi32 (per subcategory)."""

    _fields_ = [
        ("AuditSubcategoryGuid", _GUID),
        ("AuditingInformation", w.ULONG),
        ("AuditCategoryGuid", _GUID),
    ]


class _LUID(ctypes.Structure):
    """Locally unique identifier (used with ``LookupPrivilegeValueW``)."""

    _fields_ = [("LowPart", w.DWORD), ("HighPart", w.LONG)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    """One privilege entry for ``TOKEN_PRIVILEGES``."""

    _fields_ = [("Luid", _LUID), ("Attributes", w.DWORD)]


class _TOKEN_PRIVILEGES(ctypes.Structure):
    """``TOKEN_PRIVILEGES`` with a single ``LUID_AND_ATTRIBUTES`` (fixed size)."""

    _fields_ = [("PrivilegeCount", w.DWORD), ("Privileges", _LUID_AND_ATTRIBUTES * 1)]


def _load_advapi32():
    """
    Bind advapi32/kernel32 entry points used for audit policy and token
    privileges. ``use_last_error=True`` so ``ctypes.get_last_error()`` matches
    Win32 failures after each call.
    """
    advapi32_dll = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32_dll = ctypes.WinDLL("kernel32", use_last_error=True)

    # AuditQuerySystemPolicy — ntsecapi.h; ppAuditPolicy is heap-allocated; free
    # with AuditFree. Local names match Win32 exports for easier MSDN lookup.
    AuditQuerySystemPolicy = advapi32_dll.AuditQuerySystemPolicy
    AuditQuerySystemPolicy.argtypes = [
        ctypes.POINTER(_GUID),
        w.ULONG,
        ctypes.POINTER(ctypes.POINTER(_AUDIT_POLICY_INFORMATION)),
    ]
    AuditQuerySystemPolicy.restype = w.BOOL

    # AuditSetSystemPolicy — category GUID member ignored per MSDN.
    AuditSetSystemPolicy = advapi32_dll.AuditSetSystemPolicy
    AuditSetSystemPolicy.argtypes = [
        ctypes.POINTER(_AUDIT_POLICY_INFORMATION),
        w.ULONG,
    ]
    AuditSetSystemPolicy.restype = w.BOOL

    AuditFree = advapi32_dll.AuditFree
    AuditFree.argtypes = [w.LPVOID]
    AuditFree.restype = None

    OpenProcessToken = advapi32_dll.OpenProcessToken
    OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    OpenProcessToken.restype = w.BOOL

    LookupPrivilegeValueW = advapi32_dll.LookupPrivilegeValueW
    LookupPrivilegeValueW.argtypes = [
        w.LPCWSTR,
        w.LPCWSTR,
        ctypes.POINTER(_LUID),
    ]
    LookupPrivilegeValueW.restype = w.BOOL

    AdjustTokenPrivileges = advapi32_dll.AdjustTokenPrivileges
    AdjustTokenPrivileges.argtypes = [
        w.HANDLE,
        w.BOOL,
        ctypes.POINTER(_TOKEN_PRIVILEGES),
        w.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    AdjustTokenPrivileges.restype = w.BOOL

    GetCurrentProcess = kernel32_dll.GetCurrentProcess
    GetCurrentProcess.argtypes = []
    GetCurrentProcess.restype = w.HANDLE

    CloseHandle = kernel32_dll.CloseHandle
    CloseHandle.argtypes = [w.HANDLE]
    CloseHandle.restype = w.BOOL

    return SimpleNamespace(
        AuditQuerySystemPolicy=AuditQuerySystemPolicy,
        AuditSetSystemPolicy=AuditSetSystemPolicy,
        AuditFree=AuditFree,
        OpenProcessToken=OpenProcessToken,
        LookupPrivilegeValueW=LookupPrivilegeValueW,
        AdjustTokenPrivileges=AdjustTokenPrivileges,
        GetCurrentProcess=GetCurrentProcess,
        CloseHandle=CloseHandle,
    )


_API = None


def _api():
    """
    Lazy singleton of :func:`_load_advapi32` bindings (``_API`` cache).

    Attributes use **PascalCase** names matching the Win32 exports (e.g.
    ``AuditQuerySystemPolicy``) for parity with MSDN and headers.
    """
    global _API
    if _API is None:
        _API = _load_advapi32()
    return _API


def _uuid_to_guid(subcategory_uuid: uuid.UUID) -> _GUID:
    """
    Pack a Python :class:`uuid.UUID` into the Win32 ``GUID`` memory layout.

    ``UUID.bytes_le`` matches how ``GUID`` fields are ordered in RAM for the
    ``Data1``/``Data2``/``Data3``/``Data4`` split used by ``AuditQuerySystemPolicy``.
    """
    uuid_bytes_le = subcategory_uuid.bytes_le
    guid_struct = _GUID()
    guid_struct.Data1, guid_struct.Data2, guid_struct.Data3 = struct.unpack(
        "<IHH", uuid_bytes_le[:8]
    )
    ctypes.memmove(guid_struct.Data4, uuid_bytes_le[8:16], 8)
    return guid_struct


def _mask_to_labels(audit_mask: int) -> tuple[str, str]:
    """Map ``AuditingInformation`` bitmask to (Inclusion Setting, Setting Value str)."""
    success_on = bool(audit_mask & _AUDIT_SUCCESS)
    failure_on = bool(audit_mask & _AUDIT_FAILURE)
    if success_on and failure_on:
        return "Success and Failure", "3"
    if success_on:
        return "Success", "1"
    if failure_on:
        return "Failure", "2"
    return "No Auditing", "0"


@contextlib.contextmanager
def _enable_se_security_privilege():
    """
    Enable ``SeSecurityPrivilege`` on this process for the duration of the
    ``with`` block (required for ``AuditSetSystemPolicy``).
    """
    win32 = _api()
    process_token_handle = w.HANDLE()
    if not win32.OpenProcessToken(
        win32.GetCurrentProcess(),
        _TOKEN_ADJUST_PRIVILEGES | _TOKEN_QUERY,
        ctypes.byref(process_token_handle),
    ):
        raise CommandExecutionError(
            "OpenProcessToken failed", info={"errno": ctypes.get_last_error()}
        )
    try:
        security_privilege_luid = _LUID()
        if not win32.LookupPrivilegeValueW(
            None, "SeSecurityPrivilege", ctypes.byref(security_privilege_luid)
        ):
            raise CommandExecutionError(
                "LookupPrivilegeValueW(SeSecurityPrivilege) failed",
                info={"errno": ctypes.get_last_error()},
            )
        token_privileges = _TOKEN_PRIVILEGES()
        token_privileges.PrivilegeCount = 1
        token_privileges.Privileges[0].Luid = security_privilege_luid
        token_privileges.Privileges[0].Attributes = _SE_PRIVILEGE_ENABLED
        if not win32.AdjustTokenPrivileges(
            process_token_handle,
            False,
            ctypes.byref(token_privileges),
            ctypes.sizeof(token_privileges),
            None,
            None,
        ):
            raise CommandExecutionError(
                "AdjustTokenPrivileges failed",
                info={"errno": ctypes.get_last_error()},
            )
        yield
    finally:
        win32.CloseHandle(process_token_handle)


def _query_system_policies():
    """
    Call ``AuditQuerySystemPolicy`` for every subcategory in
    :data:`_AUDIT_SUBCATEGORY_METADATA`.

    Returns:
        list: One tuple per row:
        ``(category_name, subcategory_name, subcategory_uuid, audit_mask)`` —
        ``audit_mask`` is the raw ``AuditingInformation`` ULONG (success/failure
        bits per MSDN).
    """
    metadata_rows = _AUDIT_SUBCATEGORY_METADATA
    subcategory_count = len(metadata_rows)

    # Contiguous array of GUIDs — required; passing a single GUID pointer is a
    # common marshaling mistake and yields ERROR_INVALID_PARAMETER.
    guid_array_type = _GUID * subcategory_count
    subcategory_guid_array = guid_array_type()
    subcategory_uuids_ordered = []
    for index, (_category, _subcategory, guid_string) in enumerate(metadata_rows):
        parsed_uuid = uuid.UUID(guid_string)
        subcategory_uuids_ordered.append(parsed_uuid)
        subcategory_guid_array[index] = _uuid_to_guid(parsed_uuid)

    # Output: pointer to heap array of AUDIT_POLICY_INFORMATION (same length).
    allocated_policy_array_ptr = ctypes.POINTER(_AUDIT_POLICY_INFORMATION)()
    win32 = _api()
    if not win32.AuditQuerySystemPolicy(
        subcategory_guid_array,
        subcategory_count,
        ctypes.byref(allocated_policy_array_ptr),
    ):
        err = ctypes.get_last_error()
        raise CommandExecutionError(
            "AuditQuerySystemPolicy failed",
            info={"errno": err},
        )
    if not allocated_policy_array_ptr:
        return [
            (
                metadata_rows[i][0],
                metadata_rows[i][1],
                subcategory_uuids_ordered[i],
                0,
            )
            for i in range(subcategory_count)
        ]
    try:
        results = []
        for index in range(subcategory_count):
            policy_info_struct = allocated_policy_array_ptr[index]
            results.append(
                (
                    metadata_rows[index][0],
                    metadata_rows[index][1],
                    subcategory_uuids_ordered[index],
                    int(policy_info_struct.AuditingInformation),
                )
            )
        return results
    finally:
        win32.AuditFree(allocated_policy_array_ptr)


# (category, subcategory English name as in auditpol backup / set, GUID string)
# GUIDs align with Microsoft advanced audit subcategories (see e.g. PowerShell
# AuditPolicyDsc AuditPolicyResourceHelper).
_AUDIT_SUBCATEGORY_METADATA = [
    ("System", "Security State Change", "{0CCE9210-69AE-11D9-BED3-505054503030}"),
    ("System", "Security System Extension", "{0CCE9211-69AE-11D9-BED3-505054503030}"),
    ("System", "System Integrity", "{0CCE9212-69AE-11D9-BED3-505054503030}"),
    ("System", "IPsec Driver", "{0CCE9213-69AE-11D9-BED3-505054503030}"),
    ("System", "Other System Events", "{0CCE9214-69AE-11D9-BED3-505054503030}"),
    ("Logon/Logoff", "Logon", "{0CCE9215-69AE-11D9-BED3-505054503030}"),
    ("Logon/Logoff", "Logoff", "{0CCE9216-69AE-11D9-BED3-505054503030}"),
    ("Logon/Logoff", "Account Lockout", "{0CCE9217-69AE-11D9-BED3-505054503030}"),
    ("Logon/Logoff", "IPsec Main Mode", "{0CCE9218-69AE-11D9-BED3-505054503030}"),
    ("Logon/Logoff", "IPsec Quick Mode", "{0CCE9219-69AE-11D9-BED3-505054503030}"),
    ("Logon/Logoff", "IPsec Extended Mode", "{0CCE921A-69AE-11D9-BED3-505054503030}"),
    ("Logon/Logoff", "Special Logon", "{0CCE921B-69AE-11D9-BED3-505054503030}"),
    (
        "Logon/Logoff",
        "Other Logon/Logoff Events",
        "{0CCE921C-69AE-11D9-BED3-505054503030}",
    ),
    ("Logon/Logoff", "Network Policy Server", "{0CCE9243-69AE-11D9-BED3-505054503030}"),
    ("Logon/Logoff", "User / Device Claims", "{0CCE9247-69AE-11D9-BED3-505054503030}"),
    ("Logon/Logoff", "Group Membership", "{0CCE9249-69AE-11D9-BED3-505054503030}"),
    ("Object Access", "File System", "{0CCE921D-69AE-11D9-BED3-505054503030}"),
    ("Object Access", "Registry", "{0CCE921E-69AE-11D9-BED3-505054503030}"),
    ("Object Access", "Kernel Object", "{0CCE921F-69AE-11D9-BED3-505054503030}"),
    ("Object Access", "SAM", "{0CCE9220-69AE-11D9-BED3-505054503030}"),
    (
        "Object Access",
        "Certification Services",
        "{0CCE9221-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Object Access",
        "Application Generated",
        "{0CCE9222-69AE-11D9-BED3-505054503030}",
    ),
    ("Object Access", "Handle Manipulation", "{0CCE9223-69AE-11D9-BED3-505054503030}"),
    ("Object Access", "File Share", "{0CCE9224-69AE-11D9-BED3-505054503030}"),
    (
        "Object Access",
        "Filtering Platform Packet Drop",
        "{0CCE9225-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Object Access",
        "Filtering Platform Connection",
        "{0CCE9226-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Object Access",
        "Other Object Access Events",
        "{0CCE9227-69AE-11D9-BED3-505054503030}",
    ),
    ("Object Access", "Detailed File Share", "{0CCE9244-69AE-11D9-BED3-505054503030}"),
    ("Object Access", "Removable Storage", "{0CCE9245-69AE-11D9-BED3-505054503030}"),
    (
        "Object Access",
        "Central Policy Staging",
        "{0CCE9246-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Privilege Use",
        "Sensitive Privilege Use",
        "{0CCE9228-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Privilege Use",
        "Non Sensitive Privilege Use",
        "{0CCE9229-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Privilege Use",
        "Other Privilege Use Events",
        "{0CCE922A-69AE-11D9-BED3-505054503030}",
    ),
    ("Detailed Tracking", "Process Creation", "{0CCE922B-69AE-11D9-BED3-505054503030}"),
    (
        "Detailed Tracking",
        "Process Termination",
        "{0CCE922C-69AE-11D9-BED3-505054503030}",
    ),
    ("Detailed Tracking", "DPAPI Activity", "{0CCE922D-69AE-11D9-BED3-505054503030}"),
    ("Detailed Tracking", "RPC Events", "{0CCE922E-69AE-11D9-BED3-505054503030}"),
    (
        "Detailed Tracking",
        "Plug and Play Events",
        "{0CCE9248-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Detailed Tracking",
        "Token Right Adjusted Events",
        "{0CCE924A-69AE-11D9-BED3-505054503030}",
    ),
    ("Policy Change", "Audit Policy Change", "{0CCE922F-69AE-11D9-BED3-505054503030}"),
    (
        "Policy Change",
        "Authentication Policy Change",
        "{0CCE9230-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Policy Change",
        "Authorization Policy Change",
        "{0CCE9231-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Policy Change",
        "MPSSVC Rule-Level Policy Change",
        "{0CCE9232-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Policy Change",
        "Filtering Platform Policy Change",
        "{0CCE9233-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Policy Change",
        "Other Policy Change Events",
        "{0CCE9234-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Management",
        "User Account Management",
        "{0CCE9235-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Management",
        "Computer Account Management",
        "{0CCE9236-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Management",
        "Security Group Management",
        "{0CCE9237-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Management",
        "Distribution Group Management",
        "{0CCE9238-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Management",
        "Application Group Management",
        "{0CCE9239-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Management",
        "Other Account Management Events",
        "{0CCE923A-69AE-11D9-BED3-505054503030}",
    ),
    ("DS Access", "Directory Service Access", "{0CCE923B-69AE-11D9-BED3-505054503030}"),
    (
        "DS Access",
        "Directory Service Changes",
        "{0CCE923C-69AE-11D9-BED3-505054503030}",
    ),
    (
        "DS Access",
        "Directory Service Replication",
        "{0CCE923D-69AE-11D9-BED3-505054503030}",
    ),
    (
        "DS Access",
        "Detailed Directory Service Replication",
        "{0CCE923E-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Logon",
        "Credential Validation",
        "{0CCE923F-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Logon",
        "Kerberos Service Ticket Operations",
        "{0CCE9240-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Logon",
        "Other Account Logon Events",
        "{0CCE9241-69AE-11D9-BED3-505054503030}",
    ),
    (
        "Account Logon",
        "Kerberos Authentication Service",
        "{0CCE9242-69AE-11D9-BED3-505054503030}",
    ),
]


def __virtual__():
    """
    Only load if on a Windows system
    """
    if not salt.utils.platform.is_windows():
        return False, "This utility only available on Windows"

    return __virtualname__


def get_advaudit_policy_rows():
    """
    Return one row per advanced audit subcategory for LGPO and related code.

    Rows are built from ``AuditQuerySystemPolicy`` and the in-module GUID/name
    table, so they do not depend on ``auditpol.exe`` or the host display
    language.

    Returns:
        list: A list of dictionaries, each with keys ``Machine Name``,
            ``Policy Target``, ``Subcategory``, ``Subcategory GUID``,
            ``Inclusion Setting``, ``Exclusion Setting``, and ``Setting Value``.
            ``Machine Name`` is always ``""``; ``Policy Target`` is ``System``;
            ``Subcategory`` is the English name used with :func:`set_setting`;
            ``Subcategory GUID`` is braced uppercase; ``Setting Value`` is
            ``"0"``–``"3"`` matching LGPO's ``audit.csv`` convention.

    Raises:
        CommandExecutionError: If the Windows API call fails.
    """
    rows_out = []
    for (_metadata_category, subcategory, guid_string), query_row in zip(
        _AUDIT_SUBCATEGORY_METADATA, _query_system_policies()
    ):
        _, _, _, audit_mask = query_row
        inclusion, setting_val = _mask_to_labels(audit_mask)
        guid_braced = guid_string.upper()
        rows_out.append(
            {
                "Machine Name": "",
                "Policy Target": "System",
                "Subcategory": subcategory,
                "Subcategory GUID": guid_braced,
                "Inclusion Setting": inclusion,
                "Exclusion Setting": "",
                "Setting Value": setting_val,
            }
        )
    return rows_out


def get_settings(category="All"):
    """
    Get the current configuration for all audit settings in the given category.

    Reads effective policy via ``AuditQuerySystemPolicy`` (not ``auditpol
    /get``), so results use English subcategory keys and English value labels
    regardless of OS language.

    Args:
        category (str):
            One of the nine categories, or ``All`` / ``*`` for every
            subcategory. Names are matched case-insensitively against
            :data:`categories`.

    Returns:
        dict: Maps each **English** subcategory name to one of ``No Auditing``,
            ``Success``, ``Failure``, or ``Success and Failure``.

    Raises:
        KeyError: If ``category`` is not recognized.
        CommandExecutionError: If the Windows API call fails.
    """
    if category.lower() in ["all", "*"]:
        want = None
    else:
        want = None
        for c in categories:
            if c.lower() == category.lower():
                want = c
                break
        if want is None:
            raise KeyError(f'Invalid category: "{category}"')

    ret = {}
    for (category_name, subcategory_name, _subcategory_uuid), query_row in zip(
        _AUDIT_SUBCATEGORY_METADATA, _query_system_policies()
    ):
        _, _, _, audit_mask = query_row
        if want is not None and category_name != want:
            continue
        label, _setting_value_str = _mask_to_labels(audit_mask)
        ret[subcategory_name] = label
    return ret


def get_setting(name):
    """
    Get the current configuration for a single subcategory.

    Args:
        name (str): English subcategory name (matched case-insensitively).

    Returns:
        str: One of ``No Auditing``, ``Success``, ``Failure``, or
            ``Success and Failure``.

    Raises:
        KeyError: If ``name`` is not a known subcategory.
        CommandExecutionError: If querying the current policy fails.
    """
    current_settings = get_settings(category="All")
    for setting in current_settings:
        if name.lower() == setting.lower():
            return current_settings[setting]
    raise KeyError(f"Invalid name: {name}")


def _get_valid_names():
    """
    Return lowercase English subcategory names valid for :func:`set_setting`.

    Cached on ``__context__['auditpol.valid_names']`` until cleared after a
    successful :func:`set_setting`.
    """
    if "auditpol.valid_names" not in __context__:
        settings_map = get_settings(category="All")
        __context__["auditpol.valid_names"] = [k.lower() for k in settings_map]
    return __context__["auditpol.valid_names"]


def set_setting(name, value):
    """
    Set the auditing bitmask for one subcategory.

    Enables ``SeSecurityPrivilege`` on the current process token for the
    duration of the ``AuditSetSystemPolicy`` call.

    Args:
        name (str):
            English subcategory name (same strings as returned by
            :func:`get_settings`).
        value (str):
            One of ``No Auditing``, ``Success``, ``Failure``, or
            ``Success and Failure`` (matched case-insensitively).

    Returns:
        bool: ``True`` on success.

    Raises:
        KeyError: On invalid ``name`` or ``value``.
        CommandExecutionError: If privilege adjustment or
            ``AuditSetSystemPolicy`` fails.
    """
    if name.lower() not in _get_valid_names():
        raise KeyError(f"Invalid name: {name}")
    audit_bitmask = None
    for setting in settings:
        if value.lower() == setting.lower():
            audit_bitmask = int(settings[setting])
            break
    if audit_bitmask is None:
        raise KeyError(f"Invalid setting value: {value}")

    resolved_subcategory_name = None
    resolved_subcategory_uuid = None
    for _meta_cat, meta_subcategory, guid_string in _AUDIT_SUBCATEGORY_METADATA:
        if name.lower() == meta_subcategory.lower():
            resolved_subcategory_name = meta_subcategory
            resolved_subcategory_uuid = uuid.UUID(guid_string)
            break
    if resolved_subcategory_uuid is None:
        raise KeyError(f"Invalid name: {name}")

    audit_policy_info = _AUDIT_POLICY_INFORMATION()
    audit_policy_info.AuditSubcategoryGuid = _uuid_to_guid(resolved_subcategory_uuid)
    audit_policy_info.AuditingInformation = audit_bitmask
    audit_policy_info.AuditCategoryGuid = _GUID()

    win32 = _api()
    with _enable_se_security_privilege():
        policy_count = 1
        if not win32.AuditSetSystemPolicy(
            ctypes.byref(audit_policy_info), policy_count
        ):
            err = ctypes.get_last_error()
            raise CommandExecutionError(
                "AuditSetSystemPolicy failed",
                info={
                    "errno": err,
                    "name": resolved_subcategory_name,
                    "value": value,
                },
            )

    __context__.pop("auditpol.valid_names", None)
    return True


def get_auditpol_dump():
    """
    Return advanced audit policy rows as CSV **text lines** (UTF-8).

    This does not run ``auditpol /backup`` or read a temp file. It formats the
    same data as :func:`get_advaudit_policy_rows` using :mod:`csv`, so each line
    is a normal Unicode string (newlines ``\\n``).

    Returns:
        list: Lines including a header row, suitable for passing to
            :class:`csv.DictReader` if needed.

    Raises:
        CommandExecutionError: If building rows fails (e.g. API error from
            :func:`get_advaudit_policy_rows`).
    """
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for row in get_advaudit_policy_rows():
        writer.writerow(row)
    buf.seek(0)
    return buf.readlines()
