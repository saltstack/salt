# -*- coding: utf-8 -*-
"""
Windows specific utility functions, this module should be imported in a try,
except block because it is only applicable on Windows platforms.


Much of what is here was adapted from the following:

    https://stackoverflow.com/a/43233332
    http://stackoverflow.com/questions/29566330
"""
from __future__ import absolute_import, unicode_literals

import collections
import ctypes
import logging
import os
from ctypes import wintypes

import ntsecuritycon
import psutil
import win32api
import win32con
import win32process
import win32security
import win32service
from salt.ext.six.moves import range, zip

# Set up logging
log = logging.getLogger(__name__)

ntdll = ctypes.WinDLL("ntdll")
secur32 = ctypes.WinDLL("secur32")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
userenv = ctypes.WinDLL("userenv", use_last_error=True)

SYSTEM_SID = "S-1-5-18"
LOCAL_SRV_SID = "S-1-5-19"
NETWORK_SRV_SID = "S-1-5-19"

LOGON_WITH_PROFILE = 0x00000001

WINSTA_ALL = (
    win32con.WINSTA_ACCESSCLIPBOARD
    | win32con.WINSTA_ACCESSGLOBALATOMS
    | win32con.WINSTA_CREATEDESKTOP
    | win32con.WINSTA_ENUMDESKTOPS
    | win32con.WINSTA_ENUMERATE
    | win32con.WINSTA_EXITWINDOWS
    | win32con.WINSTA_READATTRIBUTES
    | win32con.WINSTA_READSCREEN
    | win32con.WINSTA_WRITEATTRIBUTES
    | win32con.DELETE
    | win32con.READ_CONTROL
    | win32con.WRITE_DAC
    | win32con.WRITE_OWNER
)

DESKTOP_ALL = (
    win32con.DESKTOP_CREATEMENU
    | win32con.DESKTOP_CREATEWINDOW
    | win32con.DESKTOP_ENUMERATE
    | win32con.DESKTOP_HOOKCONTROL
    | win32con.DESKTOP_JOURNALPLAYBACK
    | win32con.DESKTOP_JOURNALRECORD
    | win32con.DESKTOP_READOBJECTS
    | win32con.DESKTOP_SWITCHDESKTOP
    | win32con.DESKTOP_WRITEOBJECTS
    | win32con.DELETE
    | win32con.READ_CONTROL
    | win32con.WRITE_DAC
    | win32con.WRITE_OWNER
)

MAX_COMPUTER_NAME_LENGTH = 15

SECURITY_LOGON_TYPE = wintypes.ULONG
Interactive = 2
Network = 3
Batch = 4
Service = 5

LOGON_SUBMIT_TYPE = wintypes.ULONG
PROFILE_BUFFER_TYPE = wintypes.ULONG

MsV1_0InteractiveLogon = 2
MsV1_0Lm20Logon = 3
MsV1_0NetworkLogon = 4
MsV1_0WorkstationUnlockLogon = 7
MsV1_0S4ULogon = 12
MsV1_0NoElevationLogon = 82

KerbInteractiveLogon = 2
KerbWorkstationUnlockLogon = 7
KerbS4ULogon = 12

MSV1_0_S4U_LOGON_FLAG_CHECK_LOGONHOURS = 0x2

KERB_S4U_LOGON_FLAG_CHECK_LOGONHOURS = 0x2
KERB_S4U_LOGON_FLAG_IDENTITY = 0x8

TOKEN_SOURCE_LENGTH = 8

NEGOTIATE_PACKAGE_NAME = b"Negotiate"
MICROSOFT_KERBEROS_NAME = b"Kerberos"
MSV1_0_PACKAGE_NAME = b"MICROSOFT_AUTHENTICATION_PACKAGE_V1_0"

DELETE = 0x00010000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
WRITE_OWNER = 0x00080000

STANDARD_RIGHTS_REQUIRED = DELETE | READ_CONTROL | WRITE_DAC | WRITE_OWNER

TOKEN_ASSIGN_PRIMARY = 0x0001
TOKEN_DUPLICATE = 0x0002
TOKEN_IMPERSONATE = 0x0004
TOKEN_QUERY = 0x0008
TOKEN_QUERY_SOURCE = 0x0010
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_ADJUST_GROUPS = 0x0040
TOKEN_ADJUST_DEFAULT = 0x0080
TOKEN_ADJUST_SESSIONID = 0x0100

TOKEN_ALL_ACCESS = (
    STANDARD_RIGHTS_REQUIRED
    | TOKEN_ASSIGN_PRIMARY
    | TOKEN_DUPLICATE
    | TOKEN_IMPERSONATE
    | TOKEN_QUERY
    | TOKEN_QUERY_SOURCE
    | TOKEN_ADJUST_PRIVILEGES
    | TOKEN_ADJUST_GROUPS
    | TOKEN_ADJUST_DEFAULT
    | TOKEN_ADJUST_SESSIONID
)

DUPLICATE_CLOSE_SOURCE = 0x00000001
DUPLICATE_SAME_ACCESS = 0x00000002

TOKEN_TYPE = wintypes.ULONG
TokenPrimary = 1
TokenImpersonation = 2

SECURITY_IMPERSONATION_LEVEL = wintypes.ULONG
SecurityAnonymous = 0
SecurityIdentification = 1
SecurityImpersonation = 2
SecurityDelegation = 3


class NTSTATUS(wintypes.LONG):
    def to_error(self):
        return ntdll.RtlNtStatusToDosError(self)

    def __repr__(self):
        name = self.__class__.__name__
        status = wintypes.ULONG.from_buffer(self)
        return "{}({})".format(name, status.value)


PNTSTATUS = ctypes.POINTER(NTSTATUS)


class BOOL(wintypes.BOOL):
    def __repr__(self):
        name = self.__class__.__name__
        return "{}({})".format(name, bool(self))


class HANDLE(wintypes.HANDLE):
    __slots__ = ("closed",)

    def __int__(self):
        return self.value or 0

    def Detach(self):
        if not getattr(self, "closed", False):
            self.closed = True
            value = int(self)
            self.value = None
            return value
        raise ValueError("already closed")

    def Close(self, CloseHandle=kernel32.CloseHandle):
        if self and not getattr(self, "closed", False):
            CloseHandle(self.Detach())

    __del__ = Close

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, int(self))


class LARGE_INTEGER(wintypes.LARGE_INTEGER):
    # https://msdn.microsoft.com/en-us/library/ff553204
    ntdll.RtlSecondsSince1970ToTime.restype = None
    _unix_epoch = wintypes.LARGE_INTEGER()
    ntdll.RtlSecondsSince1970ToTime(0, ctypes.byref(_unix_epoch))
    _unix_epoch = _unix_epoch.value

    def __int__(self):
        return self.value

    def __repr__(self):
        name = self.__class__.__name__
        return "{}({})".format(name, self.value)

    def as_time(self):
        time100ns = self.value - self._unix_epoch
        if time100ns >= 0:
            return time100ns / 1e7
        raise ValueError("value predates the Unix epoch")

    @classmethod
    def from_time(cls, t):
        time100ns = int(t * 10 ** 7)
        return cls(time100ns + cls._unix_epoch)


CHAR = ctypes.c_char
WCHAR = ctypes.c_wchar
PCHAR = ctypes.POINTER(CHAR)
PWCHAR = ctypes.POINTER(WCHAR)


class STRING(ctypes.Structure):
    _fields_ = (
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", PCHAR),
    )


LPSTRING = ctypes.POINTER(STRING)


class UNICODE_STRING(ctypes.Structure):
    _fields_ = (
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", PWCHAR),
    )


LPUNICODE_STRING = ctypes.POINTER(UNICODE_STRING)


class LUID(ctypes.Structure):
    _fields_ = (
        ("LowPart", wintypes.DWORD),
        ("HighPart", wintypes.LONG),
    )

    def __new__(cls, value=0):
        return cls.from_buffer_copy(ctypes.c_ulonglong(value))

    def __int__(self):
        return ctypes.c_ulonglong.from_buffer(self).value

    def __repr__(self):
        name = self.__class__.__name__
        return "{}({})".format(name, int(self))


LPLUID = ctypes.POINTER(LUID)
PSID = wintypes.LPVOID


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = (
        ("Sid", PSID),
        ("Attributes", wintypes.DWORD),
    )


LPSID_AND_ATTRIBUTES = ctypes.POINTER(SID_AND_ATTRIBUTES)


class TOKEN_GROUPS(ctypes.Structure):
    _fields_ = (
        ("GroupCount", wintypes.DWORD),
        ("Groups", SID_AND_ATTRIBUTES * 1),
    )


LPTOKEN_GROUPS = ctypes.POINTER(TOKEN_GROUPS)


class TOKEN_SOURCE(ctypes.Structure):
    _fields_ = (
        ("SourceName", CHAR * TOKEN_SOURCE_LENGTH),
        ("SourceIdentifier", LUID),
    )

    def __init__(self, SourceName=None, SourceIdentifier=None):
        super(TOKEN_SOURCE, self).__init__()
        if SourceName is not None:
            if not isinstance(SourceName, bytes):
                SourceName = SourceName.encode("mbcs")
            self.SourceName = SourceName
        if SourceIdentifier is None:
            # pylint: disable=access-member-before-definition
            luid = self.SourceIdentifier
            # pylint: enable=access-member-before-definition
            ntdll.NtAllocateLocallyUniqueId(ctypes.byref(luid))
        else:
            self.SourceIdentifier = SourceIdentifier


LPTOKEN_SOURCE = ctypes.POINTER(TOKEN_SOURCE)
py_source_context = TOKEN_SOURCE(b"PYTHON  ")
py_origin_name = __name__.encode()
py_logon_process_name = "{}-{}".format(py_origin_name, os.getpid())
SIZE_T = ctypes.c_size_t


class QUOTA_LIMITS(ctypes.Structure):
    _fields_ = (
        ("PagedPoolLimit", SIZE_T),
        ("NonPagedPoolLimit", SIZE_T),
        ("MinimumWorkingSetSize", SIZE_T),
        ("MaximumWorkingSetSize", SIZE_T),
        ("PagefileLimit", SIZE_T),
        ("TimeLimit", wintypes.LARGE_INTEGER),
    )


LPQUOTA_LIMITS = ctypes.POINTER(QUOTA_LIMITS)
LPULONG = ctypes.POINTER(wintypes.ULONG)
LSA_OPERATIONAL_MODE = wintypes.ULONG
LPLSA_OPERATIONAL_MODE = LPULONG
LPHANDLE = ctypes.POINTER(wintypes.HANDLE)
LPLPVOID = ctypes.POINTER(wintypes.LPVOID)
LPDWORD = ctypes.POINTER(wintypes.DWORD)


class ContiguousUnicode(ctypes.Structure):
    # _string_names_: sequence matched to underscore-prefixed fields
    def __init__(self, *args, **kwargs):  # pylint: disable=useless-super-delegation
        super(ContiguousUnicode, self).__init__(*args, **kwargs)

    def _get_unicode_string(self, name):
        wchar_size = ctypes.sizeof(WCHAR)
        s = getattr(self, "_{}".format(name))
        length = s.Length // wchar_size
        buf = s.Buffer
        if buf:
            return buf[:length]
        return None

    def _set_unicode_buffer(self, values):
        cls = type(self)
        wchar_size = ctypes.sizeof(WCHAR)
        bufsize = (len("\x00".join(values)) + 1) * wchar_size
        ctypes.resize(self, ctypes.sizeof(cls) + bufsize)
        addr = ctypes.addressof(self) + ctypes.sizeof(cls)
        for value in values:
            bufsize = (len(value) + 1) * wchar_size
            ctypes.memmove(addr, value, bufsize)
            addr += bufsize

    def _set_unicode_string(self, name, value):
        values = []
        for n in self._string_names_:
            if n == name:
                values.append(value or "")
            else:
                values.append(getattr(self, n) or "")
        self._set_unicode_buffer(values)

        cls = type(self)
        wchar_size = ctypes.sizeof(WCHAR)
        addr = ctypes.addressof(self) + ctypes.sizeof(cls)
        for n, v in zip(self._string_names_, values):
            ptr = ctypes.cast(addr, PWCHAR)
            ustr = getattr(self, "_{}".format(n))
            length = ustr.Length = len(v) * wchar_size
            full_length = length + wchar_size
            if (n == name and value is None) or (
                n != name and not (length or ustr.Buffer)
            ):
                ustr.Buffer = None
                ustr.MaximumLength = 0
            else:
                ustr.Buffer = ptr
                ustr.MaximumLength = full_length
            addr += full_length

    def __getattr__(self, name):
        if name not in self._string_names_:
            raise AttributeError
        return self._get_unicode_string(name)

    def __setattr__(self, name, value):
        if name in self._string_names_:
            self._set_unicode_string(name, value)
        else:
            super(ContiguousUnicode, self).__setattr__(name, value)

    @classmethod
    def from_address_copy(cls, address, size=None):
        x = ctypes.Structure.__new__(cls)
        if size is not None:
            ctypes.resize(x, size)
        ctypes.memmove(ctypes.byref(x), address, ctypes.sizeof(x))
        delta = ctypes.addressof(x) - address
        for n in cls._string_names_:
            ustr = getattr(x, "_{}".format(n))
            addr = ctypes.c_void_p.from_buffer(ustr.Buffer)
            if addr:
                addr.value += delta
        return x


class AuthInfo(ContiguousUnicode):
    # _message_type_: from a logon-submit-type enumeration
    def __init__(self):
        super(AuthInfo, self).__init__()
        self.MessageType = self._message_type_


class MSV1_0_INTERACTIVE_LOGON(AuthInfo):
    _message_type_ = MsV1_0InteractiveLogon
    _string_names_ = "LogonDomainName", "UserName", "Password"

    _fields_ = (
        ("MessageType", LOGON_SUBMIT_TYPE),
        ("_LogonDomainName", UNICODE_STRING),
        ("_UserName", UNICODE_STRING),
        ("_Password", UNICODE_STRING),
    )

    def __init__(self, UserName=None, Password=None, LogonDomainName=None):
        super(MSV1_0_INTERACTIVE_LOGON, self).__init__()
        if LogonDomainName is not None:
            self.LogonDomainName = LogonDomainName
        if UserName is not None:
            self.UserName = UserName
        if Password is not None:
            self.Password = Password


class S4ULogon(AuthInfo):
    _string_names_ = "UserPrincipalName", "DomainName"

    _fields_ = (
        ("MessageType", LOGON_SUBMIT_TYPE),
        ("Flags", wintypes.ULONG),
        ("_UserPrincipalName", UNICODE_STRING),
        ("_DomainName", UNICODE_STRING),
    )

    def __init__(self, UserPrincipalName=None, DomainName=None, Flags=0):
        super(S4ULogon, self).__init__()
        self.Flags = Flags
        if UserPrincipalName is not None:
            self.UserPrincipalName = UserPrincipalName
        if DomainName is not None:
            self.DomainName = DomainName


class MSV1_0_S4U_LOGON(S4ULogon):
    _message_type_ = MsV1_0S4ULogon


class KERB_S4U_LOGON(S4ULogon):
    _message_type_ = KerbS4ULogon


PMSV1_0_S4U_LOGON = ctypes.POINTER(MSV1_0_S4U_LOGON)
PKERB_S4U_LOGON = ctypes.POINTER(KERB_S4U_LOGON)


class ProfileBuffer(ContiguousUnicode):
    # _message_type_
    def __init__(self):
        super(ProfileBuffer, self).__init__()
        self.MessageType = self._message_type_


class MSV1_0_INTERACTIVE_PROFILE(ProfileBuffer):
    _message_type_ = MsV1_0InteractiveLogon
    _string_names_ = (
        "LogonScript",
        "HomeDirectory",
        "FullName",
        "ProfilePath",
        "HomeDirectoryDrive",
        "LogonServer",
    )
    _fields_ = (
        ("MessageType", PROFILE_BUFFER_TYPE),
        ("LogonCount", wintypes.USHORT),
        ("BadPasswordCount", wintypes.USHORT),
        ("LogonTime", LARGE_INTEGER),
        ("LogoffTime", LARGE_INTEGER),
        ("KickOffTime", LARGE_INTEGER),
        ("PasswordLastSet", LARGE_INTEGER),
        ("PasswordCanChange", LARGE_INTEGER),
        ("PasswordMustChange", LARGE_INTEGER),
        ("_LogonScript", UNICODE_STRING),
        ("_HomeDirectory", UNICODE_STRING),
        ("_FullName", UNICODE_STRING),
        ("_ProfilePath", UNICODE_STRING),
        ("_HomeDirectoryDrive", UNICODE_STRING),
        ("_LogonServer", UNICODE_STRING),
        ("UserFlags", wintypes.ULONG),
    )


def _check_status(result, func, args):
    if result.value < 0:
        raise ctypes.WinError(result.to_error())
    return args


def _check_bool(result, func, args):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return args


INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
INVALID_DWORD_VALUE = wintypes.DWORD(-1).value  # ~WinAPI
INFINITE = INVALID_DWORD_VALUE
STD_INPUT_HANDLE = wintypes.DWORD(-10).value
STD_OUTPUT_HANDLE = wintypes.DWORD(-11).value
STD_ERROR_HANDLE = wintypes.DWORD(-12).value


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = (
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    )

    def __init__(self, **kwds):
        self.nLength = ctypes.sizeof(self)
        super(SECURITY_ATTRIBUTES, self).__init__(**kwds)


LPSECURITY_ATTRIBUTES = ctypes.POINTER(SECURITY_ATTRIBUTES)
LPBYTE = ctypes.POINTER(wintypes.BYTE)
LPHANDLE = PHANDLE = ctypes.POINTER(ctypes.c_void_p)
LPDWORD = ctypes.POINTER(ctypes.c_ulong)


class STARTUPINFO(ctypes.Structure):
    """https://msdn.microsoft.com/en-us/library/ms686331"""

    _fields_ = (
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", LPBYTE),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    )

    def __init__(self, **kwds):
        self.cb = ctypes.sizeof(self)
        super(STARTUPINFO, self).__init__(**kwds)


LPSTARTUPINFO = ctypes.POINTER(STARTUPINFO)


class PROC_THREAD_ATTRIBUTE_LIST(ctypes.Structure):
    pass


PPROC_THREAD_ATTRIBUTE_LIST = ctypes.POINTER(PROC_THREAD_ATTRIBUTE_LIST)


class STARTUPINFOEX(STARTUPINFO):
    _fields_ = (("lpAttributeList", PPROC_THREAD_ATTRIBUTE_LIST),)


LPSTARTUPINFOEX = ctypes.POINTER(STARTUPINFOEX)


class PROCESS_INFORMATION(ctypes.Structure):
    """https://msdn.microsoft.com/en-us/library/ms684873"""

    _fields_ = (
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    )


LPPROCESS_INFORMATION = ctypes.POINTER(PROCESS_INFORMATION)


class HANDLE_IHV(wintypes.HANDLE):
    pass


def errcheck_ihv(result, func, args):
    if result.value == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    return result.value


class DWORD_IDV(wintypes.DWORD):
    pass


def errcheck_idv(result, func, args):
    if result.value == INVALID_DWORD_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    return result.value


def errcheck_bool(result, func, args):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return args


def _win(func, restype, *argtypes):
    func.restype = restype
    func.argtypes = argtypes
    if issubclass(restype, NTSTATUS):
        func.errcheck = _check_status
    elif issubclass(restype, BOOL):
        func.errcheck = _check_bool
    elif issubclass(restype, HANDLE_IHV):
        func.errcheck = errcheck_ihv
    elif issubclass(restype, DWORD_IDV):
        func.errcheck = errcheck_idv
    else:
        func.errcheck = errcheck_bool


# https://msdn.microsoft.com/en-us/library/ms683231
_win(kernel32.GetStdHandle, HANDLE_IHV, wintypes.DWORD)  # _In_ nStdHandle


# https://msdn.microsoft.com/en-us/library/ms724211
_win(kernel32.CloseHandle, wintypes.BOOL, wintypes.HANDLE)  # _In_ hObject


# https://msdn.microsoft.com/en-us/library/ms724935
_win(
    kernel32.SetHandleInformation,
    wintypes.BOOL,
    wintypes.HANDLE,  # _In_ hObject
    wintypes.DWORD,  # _In_ dwMask
    wintypes.DWORD,
)  # _In_ dwFlags


# https://msdn.microsoft.com/en-us/library/ms724251
_win(
    kernel32.DuplicateHandle,
    wintypes.BOOL,
    wintypes.HANDLE,  # _In_  hSourceProcessHandle,
    wintypes.HANDLE,  # _In_  hSourceHandle,
    wintypes.HANDLE,  # _In_  hTargetProcessHandle,
    LPHANDLE,  # _Out_ lpTargetHandle,
    wintypes.DWORD,  # _In_  dwDesiredAccess,
    wintypes.BOOL,  # _In_  bInheritHandle,
    wintypes.DWORD,
)  # _In_  dwOptions


# https://msdn.microsoft.com/en-us/library/ms683179
_win(kernel32.GetCurrentProcess, wintypes.HANDLE)


# https://msdn.microsoft.com/en-us/library/ms683189
_win(
    kernel32.GetExitCodeProcess,
    wintypes.BOOL,
    wintypes.HANDLE,  # _In_  hProcess,
    LPDWORD,
)  # _Out_ lpExitCode


# https://msdn.microsoft.com/en-us/library/aa365152
_win(
    kernel32.CreatePipe,
    wintypes.BOOL,
    PHANDLE,  # _Out_    hReadPipe,
    PHANDLE,  # _Out_    hWritePipe,
    LPSECURITY_ATTRIBUTES,  # _In_opt_ lpPipeAttributes,
    wintypes.DWORD,
)  # _In_     nSize


# https://msdn.microsoft.com/en-us/library/ms682431
# _win(advapi32.CreateProcessWithTokenW, wintypes.BOOL,
#    PHANDLE,       # _In_        lpUsername
#    wintypes.DWORD,         # _In_        dwLogonFlags
#    wintypes.LPCWSTR,       # _In_opt_    lpApplicationName
#    wintypes.LPWSTR,        # _Inout_opt_ lpCommandLine
#    wintypes.DWORD,         # _In_        dwCreationFlags
#    wintypes.LPVOID,        # _In_opt_     lpEnvironment
#    wintypes.LPCWSTR,       # _In_opt_    lpCurrentDirectory
#    LPSTARTUPINFO,          # _In_        lpStartupInfo
#    LPPROCESS_INFORMATION)  # _Out_       lpProcessInformation


# https://msdn.microsoft.com/en-us/library/ms682431
_win(
    advapi32.CreateProcessWithLogonW,
    wintypes.BOOL,
    wintypes.LPCWSTR,  # _In_        lpUsername
    wintypes.LPCWSTR,  # _In_opt_    lpDomain
    wintypes.LPCWSTR,  # _In_        lpPassword
    wintypes.DWORD,  # _In_        dwLogonFlags
    wintypes.LPCWSTR,  # _In_opt_    lpApplicationName
    wintypes.LPWSTR,  # _Inout_opt_ lpCommandLine
    wintypes.DWORD,  # _In_        dwCreationFlags
    wintypes.LPCWSTR,  # _In_opt_    lpEnvironment
    wintypes.LPCWSTR,  # _In_opt_    lpCurrentDirectory
    LPSTARTUPINFO,  # _In_        lpStartupInfo
    LPPROCESS_INFORMATION,
)  # _Out_       lpProcessInformation


# https://msdn.microsoft.com/en-us/library/ms683179
_win(kernel32.GetCurrentProcess, wintypes.HANDLE)


# https://msdn.microsoft.com/en-us/library/ms724251
_win(
    kernel32.DuplicateHandle,
    BOOL,
    wintypes.HANDLE,  # _In_  hSourceProcessHandle
    wintypes.HANDLE,  # _In_  hSourceHandle
    wintypes.HANDLE,  # _In_  hTargetProcessHandle
    LPHANDLE,  # _Out_ lpTargetHandle
    wintypes.DWORD,  # _In_  dwDesiredAccess
    wintypes.BOOL,  # _In_  bInheritHandle
    wintypes.DWORD,
)  # _In_  dwOptions


# https://msdn.microsoft.com/en-us/library/ms724295
_win(
    kernel32.GetComputerNameW, BOOL, wintypes.LPWSTR, LPDWORD  # _Out_   lpBuffer
)  # _Inout_ lpnSize


# https://msdn.microsoft.com/en-us/library/aa379295
_win(
    advapi32.OpenProcessToken,
    BOOL,
    wintypes.HANDLE,  # _In_  ProcessHandle
    wintypes.DWORD,  # _In_  DesiredAccess
    LPHANDLE,
)  # _Out_ TokenHandle


# https://msdn.microsoft.com/en-us/library/aa446617
_win(
    advapi32.DuplicateTokenEx,
    BOOL,
    wintypes.HANDLE,  # _In_     hExistingToken
    wintypes.DWORD,  # _In_     dwDesiredAccess
    LPSECURITY_ATTRIBUTES,  # _In_opt_ lpTokenAttributes
    SECURITY_IMPERSONATION_LEVEL,  # _In_     ImpersonationLevel
    TOKEN_TYPE,  # _In_     TokenType
    LPHANDLE,
)  # _Out_    phNewToken


# https://msdn.microsoft.com/en-us/library/ff566415
_win(ntdll.NtAllocateLocallyUniqueId, NTSTATUS, LPLUID)  # _Out_ LUID


# https://msdn.microsoft.com/en-us/library/aa378279
_win(
    secur32.LsaFreeReturnBuffer, NTSTATUS, wintypes.LPVOID,
)  # _In_ Buffer


# https://msdn.microsoft.com/en-us/library/aa378265
_win(
    secur32.LsaConnectUntrusted, NTSTATUS, LPHANDLE,
)  # _Out_ LsaHandle


# https://msdn.microsoft.com/en-us/library/aa378318
_win(
    secur32.LsaRegisterLogonProcess,
    NTSTATUS,
    LPSTRING,  # _In_  LogonProcessName
    LPHANDLE,  # _Out_ LsaHandle
    LPLSA_OPERATIONAL_MODE,
)  # _Out_ SecurityMode


# https://msdn.microsoft.com/en-us/library/aa378269
_win(secur32.LsaDeregisterLogonProcess, NTSTATUS, wintypes.HANDLE)  # _In_ LsaHandle


# https://msdn.microsoft.com/en-us/library/aa378297
_win(
    secur32.LsaLookupAuthenticationPackage,
    NTSTATUS,
    wintypes.HANDLE,  # _In_  LsaHandle
    LPSTRING,  # _In_  PackageName
    LPULONG,
)  # _Out_ AuthenticationPackage


# https://msdn.microsoft.com/en-us/library/aa378292
_win(
    secur32.LsaLogonUser,
    NTSTATUS,
    wintypes.HANDLE,  # _In_     LsaHandle
    LPSTRING,  # _In_     OriginName
    SECURITY_LOGON_TYPE,  # _In_     LogonType
    wintypes.ULONG,  # _In_     AuthenticationPackage
    wintypes.LPVOID,  # _In_     AuthenticationInformation
    wintypes.ULONG,  # _In_     AuthenticationInformationLength
    LPTOKEN_GROUPS,  # _In_opt_ LocalGroups
    LPTOKEN_SOURCE,  # _In_     SourceContext
    LPLPVOID,  # _Out_    ProfileBuffer
    LPULONG,  # _Out_    ProfileBufferLength
    LPLUID,  # _Out_    LogonId
    LPHANDLE,  # _Out_    Token
    LPQUOTA_LIMITS,  # _Out_    Quotas
    PNTSTATUS,
)  # _Out_    SubStatus


def duplicate_token(
    source_token=None,
    access=TOKEN_ALL_ACCESS,
    impersonation_level=SecurityImpersonation,
    token_type=TokenPrimary,
    attributes=None,
):
    close_source = False
    if source_token is None:
        close_source = True
        source_token = HANDLE()
        advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(), TOKEN_ALL_ACCESS, ctypes.byref(source_token)
        )
    token = HANDLE()
    try:
        advapi32.DuplicateTokenEx(
            source_token,
            access,
            attributes,
            impersonation_level,
            token_type,
            ctypes.byref(token),
        )
    finally:
        if close_source:
            source_token.Close()
    return token


def lsa_connect_untrusted():
    handle = wintypes.HANDLE()
    secur32.LsaConnectUntrusted(ctypes.byref(handle))
    return handle.value


def lsa_register_logon_process(logon_process_name):
    if not isinstance(logon_process_name, bytes):
        logon_process_name = logon_process_name.encode("mbcs")
    logon_process_name = logon_process_name[:127]
    buf = ctypes.create_string_buffer(logon_process_name, 128)
    name = STRING(len(logon_process_name), len(buf), buf)
    handle = wintypes.HANDLE()
    mode = LSA_OPERATIONAL_MODE()
    secur32.LsaRegisterLogonProcess(
        ctypes.byref(name), ctypes.byref(handle), ctypes.byref(mode)
    )
    return handle.value


def lsa_lookup_authentication_package(lsa_handle, package_name):
    if not isinstance(package_name, bytes):
        package_name = package_name.encode("mbcs")
    package_name = package_name[:127]
    buf = ctypes.create_string_buffer(package_name)
    name = STRING(len(package_name), len(buf), buf)
    package = wintypes.ULONG()
    secur32.LsaLookupAuthenticationPackage(
        lsa_handle, ctypes.byref(name), ctypes.byref(package)
    )
    return package.value


LOGONINFO = collections.namedtuple(
    "LOGONINFO", ("Token", "LogonId", "Profile", "Quotas")
)


def lsa_logon_user(
    auth_info,
    local_groups=None,
    origin_name=py_origin_name,
    source_context=None,
    auth_package=None,
    logon_type=None,
    lsa_handle=None,
):
    if local_groups is None:
        plocal_groups = LPTOKEN_GROUPS()
    else:
        plocal_groups = ctypes.byref(local_groups)
    if source_context is None:
        source_context = py_source_context
    if not isinstance(origin_name, bytes):
        origin_name = origin_name.encode("mbcs")
    buf = ctypes.create_string_buffer(origin_name)
    origin_name = STRING(len(origin_name), len(buf), buf)
    if auth_package is None:
        if isinstance(auth_info, MSV1_0_S4U_LOGON):
            auth_package = NEGOTIATE_PACKAGE_NAME
        elif isinstance(auth_info, KERB_S4U_LOGON):
            auth_package = MICROSOFT_KERBEROS_NAME
        else:
            auth_package = MSV1_0_PACKAGE_NAME
    if logon_type is None:
        if isinstance(auth_info, S4ULogon):
            logon_type = win32con.LOGON32_LOGON_NETWORK
        else:
            logon_type = Interactive
    profile_buffer = wintypes.LPVOID()
    profile_buffer_length = wintypes.ULONG()
    profile = None
    logonid = LUID()
    htoken = HANDLE()
    quotas = QUOTA_LIMITS()
    substatus = NTSTATUS()
    deregister = False
    if lsa_handle is None:
        lsa_handle = lsa_connect_untrusted()
        deregister = True
    try:
        if isinstance(auth_package, (str, bytes)):
            auth_package = lsa_lookup_authentication_package(lsa_handle, auth_package)
        try:
            secur32.LsaLogonUser(
                lsa_handle,
                ctypes.byref(origin_name),
                logon_type,
                auth_package,
                ctypes.byref(auth_info),
                ctypes.sizeof(auth_info),
                plocal_groups,
                ctypes.byref(source_context),
                ctypes.byref(profile_buffer),
                ctypes.byref(profile_buffer_length),
                ctypes.byref(logonid),
                ctypes.byref(htoken),
                ctypes.byref(quotas),
                ctypes.byref(substatus),
            )
        except WindowsError:  # pylint: disable=undefined-variable
            if substatus.value:
                raise ctypes.WinError(substatus.to_error())
            raise
        finally:
            if profile_buffer:
                address = profile_buffer.value
                buftype = PROFILE_BUFFER_TYPE.from_address(address).value
                if buftype == MsV1_0InteractiveLogon:
                    profile = MSV1_0_INTERACTIVE_PROFILE.from_address_copy(
                        address, profile_buffer_length.value
                    )
                secur32.LsaFreeReturnBuffer(address)
    finally:
        if deregister:
            secur32.LsaDeregisterLogonProcess(lsa_handle)
    return LOGONINFO(htoken, logonid, profile, quotas)


def logon_msv1(
    name,
    password,
    domain=None,
    local_groups=None,
    origin_name=py_origin_name,
    source_context=None,
):
    return lsa_logon_user(
        MSV1_0_INTERACTIVE_LOGON(name, password, domain),
        local_groups,
        origin_name,
        source_context,
    )


def logon_msv1_s4u(
    name, local_groups=None, origin_name=py_origin_name, source_context=None
):
    domain = ctypes.create_unicode_buffer(MAX_COMPUTER_NAME_LENGTH + 1)
    length = wintypes.DWORD(len(domain))
    kernel32.GetComputerNameW(domain, ctypes.byref(length))
    return lsa_logon_user(
        MSV1_0_S4U_LOGON(name, domain.value), local_groups, origin_name, source_context
    )


def logon_kerb_s4u(
    name,
    realm=None,
    local_groups=None,
    origin_name=py_origin_name,
    source_context=None,
    logon_process_name=py_logon_process_name,
):
    lsa_handle = lsa_register_logon_process(logon_process_name)
    try:
        return lsa_logon_user(
            KERB_S4U_LOGON(name, realm),
            local_groups,
            origin_name,
            source_context,
            lsa_handle=lsa_handle,
        )
    finally:
        secur32.LsaDeregisterLogonProcess(lsa_handle)


def DuplicateHandle(
    hsrc=kernel32.GetCurrentProcess(),
    srchandle=kernel32.GetCurrentProcess(),
    htgt=kernel32.GetCurrentProcess(),
    access=0,
    inherit=False,
    options=win32con.DUPLICATE_SAME_ACCESS,
):
    tgthandle = wintypes.HANDLE()
    kernel32.DuplicateHandle(
        hsrc, srchandle, htgt, ctypes.byref(tgthandle), access, inherit, options
    )
    return tgthandle.value


def CreatePipe(inherit_read=False, inherit_write=False):
    read, write = wintypes.HANDLE(), wintypes.HANDLE()
    kernel32.CreatePipe(ctypes.byref(read), ctypes.byref(write), None, 0)
    if inherit_read:
        kernel32.SetHandleInformation(
            read, win32con.HANDLE_FLAG_INHERIT, win32con.HANDLE_FLAG_INHERIT
        )
    if inherit_write:
        kernel32.SetHandleInformation(
            write, win32con.HANDLE_FLAG_INHERIT, win32con.HANDLE_FLAG_INHERIT
        )
    return read.value, write.value


def set_user_perm(obj, perm, sid):
    """
    Set an object permission for the given user sid
    """
    info = (
        win32security.OWNER_SECURITY_INFORMATION
        | win32security.GROUP_SECURITY_INFORMATION
        | win32security.DACL_SECURITY_INFORMATION
    )
    sd = win32security.GetUserObjectSecurity(obj, info)
    dacl = sd.GetSecurityDescriptorDacl()
    ace_cnt = dacl.GetAceCount()
    found = False
    for idx in range(0, ace_cnt):
        (aceType, aceFlags), ace_mask, ace_sid = dacl.GetAce(idx)
        ace_exists = (
            aceType == ntsecuritycon.ACCESS_ALLOWED_ACE_TYPE
            and ace_mask == perm
            and ace_sid == sid
        )
        if ace_exists:
            # If the ace already exists, do nothing
            break
    else:
        dacl.AddAccessAllowedAce(dacl.GetAclRevision(), perm, sid)
        sd.SetSecurityDescriptorDacl(1, dacl, 0)
        win32security.SetUserObjectSecurity(obj, info, sd)


def grant_winsta_and_desktop(th):
    """
    Grant the token's user access to the current process's window station and
    desktop.
    """
    current_sid = win32security.GetTokenInformation(th, win32security.TokenUser)[0]
    # Add permissions for the sid to the current windows station and thread id.
    # This prevents windows error 0xC0000142.
    winsta = win32process.GetProcessWindowStation()
    set_user_perm(winsta, WINSTA_ALL, current_sid)
    desktop = win32service.GetThreadDesktop(win32api.GetCurrentThreadId())
    set_user_perm(desktop, DESKTOP_ALL, current_sid)


def environment_string(env):
    senv = ""
    for k, v in env.items():
        senv += k + "=" + v + "\0"
    senv += "\0"
    return ctypes.create_unicode_buffer(senv)


def CreateProcessWithTokenW(
    token,
    logonflags=0,
    applicationname=None,
    commandline=None,
    creationflags=0,
    environment=None,
    currentdirectory=None,
    startupinfo=None,
):
    creationflags |= win32con.CREATE_UNICODE_ENVIRONMENT
    if commandline is not None:
        commandline = ctypes.create_unicode_buffer(commandline)
    if startupinfo is None:
        startupinfo = STARTUPINFO()
    if currentdirectory is not None:
        currentdirectory = ctypes.create_unicode_buffer(currentdirectory)
    if environment is not None:
        environment = ctypes.pointer(environment_string(environment))
    process_info = PROCESS_INFORMATION()
    ret = advapi32.CreateProcessWithTokenW(
        token,
        logonflags,
        applicationname,
        commandline,
        creationflags,
        environment,
        currentdirectory,
        ctypes.byref(startupinfo),
        ctypes.byref(process_info),
    )
    if ret == 0:
        winerr = win32api.GetLastError()
        # pylint: disable=undefined-variable
        exc = WindowsError(win32api.FormatMessage(winerr))
        # pylint: enable=undefined-variable
        exc.winerror = winerr
        raise exc
    return process_info


def enumerate_tokens(sid=None, session_id=None, privs=None):
    """
    Enumerate tokens from any existing processes that can be accessed.
    Optionally filter by sid.
    """
    for p in psutil.process_iter():
        if p.pid == 0:
            continue
        try:
            ph = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, 0, p.pid)
        except win32api.error as exc:
            if exc.winerror == 5:
                log.debug("Unable to OpenProcess pid=%d name=%s", p.pid, p.name())
                continue
            raise exc
        try:
            access = (
                win32security.TOKEN_DUPLICATE
                | win32security.TOKEN_QUERY
                | win32security.TOKEN_IMPERSONATE
                | win32security.TOKEN_ASSIGN_PRIMARY
            )
            th = win32security.OpenProcessToken(ph, access)
        except Exception as exc:  # pylint: disable=broad-except
            log.debug(
                "OpenProcessToken failed pid=%d name=%s user%s",
                p.pid,
                p.name(),
                p.username(),
            )
            continue
        try:
            process_sid = win32security.GetTokenInformation(
                th, win32security.TokenUser
            )[0]
        except Exception as exc:  # pylint: disable=broad-except
            log.exception(
                "GetTokenInformation pid=%d name=%s user%s",
                p.pid,
                p.name(),
                p.username(),
            )
            continue

        proc_sid = win32security.ConvertSidToStringSid(process_sid)
        if sid and sid != proc_sid:
            log.debug("Token for pid does not match user sid: %s", sid)
            continue

        if (
            session_id
            and win32security.GetTokenInformation(th, win32security.TokenSessionId)
            != session_id
        ):
            continue

        def has_priv(tok, priv):
            luid = win32security.LookupPrivilegeValue(None, priv)
            for priv_luid, flags in win32security.GetTokenInformation(
                tok, win32security.TokenPrivileges
            ):
                if priv_luid == luid:
                    return True
            return False

        if privs:
            has_all = True
            for name in privs:
                if not has_priv(th, name):
                    has_all = False
            if not has_all:
                continue
        yield dup_token(th)


def impersonate_sid(sid, session_id=None, privs=None):
    """
    Find an existing process token for the given sid and impersonate the token.
    """
    for tok in enumerate_tokens(sid, session_id, privs):
        tok = dup_token(tok)
        elevate_token(tok)
        if win32security.ImpersonateLoggedOnUser(tok) == 0:
            # pylint: disable=undefined-variable
            raise WindowsError("Impersonation failure")
            # pylint: enable=undefined-variable
        return tok
    raise WindowsError("Impersonation failure")  # pylint: disable=undefined-variable


def dup_token(th):
    """
    duplicate the access token
    """
    # TODO: is `duplicate_token` the same?
    sec_attr = win32security.SECURITY_ATTRIBUTES()
    sec_attr.bInheritHandle = True
    return win32security.DuplicateTokenEx(
        th,
        win32security.SecurityImpersonation,
        win32con.MAXIMUM_ALLOWED,
        win32security.TokenPrimary,
        sec_attr,
    )


def elevate_token(th):
    """
    Set all token privileges to enabled
    """
    # Get list of privileges this token contains
    privileges = win32security.GetTokenInformation(th, win32security.TokenPrivileges)

    # Create a set of all privileges to be enabled
    enable_privs = set()
    for luid, flags in privileges:
        enable_privs.add((luid, win32con.SE_PRIVILEGE_ENABLED))

    # Enable the privileges
    if win32security.AdjustTokenPrivileges(th, 0, enable_privs) == 0:
        # pylint: disable=undefined-variable
        raise WindowsError(win32api.FormatMessage(win32api.GetLastError()))
        # pylint: enable=undefined-variable


def make_inheritable(token):
    """Create an inheritable handle"""
    return win32api.DuplicateHandle(
        win32api.GetCurrentProcess(),
        token,
        win32api.GetCurrentProcess(),
        0,
        1,
        win32con.DUPLICATE_SAME_ACCESS,
    )


def CreateProcessWithLogonW(
    username=None,
    domain=None,
    password=None,
    logonflags=0,
    applicationname=None,
    commandline=None,
    creationflags=0,
    environment=None,
    currentdirectory=None,
    startupinfo=None,
):
    creationflags |= win32con.CREATE_UNICODE_ENVIRONMENT
    if commandline is not None:
        commandline = ctypes.create_unicode_buffer(commandline)
    if startupinfo is None:
        startupinfo = STARTUPINFO()
    if environment is not None:
        environment = ctypes.pointer(environment_string(environment))
    process_info = PROCESS_INFORMATION()
    advapi32.CreateProcessWithLogonW(
        username,
        domain,
        password,
        logonflags,
        applicationname,
        commandline,
        creationflags,
        environment,
        currentdirectory,
        ctypes.byref(startupinfo),
        ctypes.byref(process_info),
    )
    return process_info
