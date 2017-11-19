# -*- coding: utf-8 -*-
'''
Run processes as a different user in Windows

Based on a solution from http://stackoverflow.com/questions/29566330
'''
from __future__ import absolute_import

# Import Python Libraries
import os
import logging

# Import Third Party Libs
try:
    import win32con
    import win32api
    import win32process
    import win32security
    import win32pipe
    import win32event
    import win32profile
    import msvcrt
    import ctypes
    import winerror
    import salt.utils.win_functions
    from ctypes import wintypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Set up logging
log = logging.getLogger(__name__)


# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    '''
    Only load if Win32 Libraries are installed
    '''
    if not HAS_WIN32:
        return False, 'This utility requires pywin32'

    return 'win_runas'


if HAS_WIN32:
    # ctypes definitions
    kernel32 = ctypes.WinDLL('kernel32')
    advapi32 = ctypes.WinDLL('advapi32')

    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    INVALID_DWORD_VALUE = wintypes.DWORD(-1).value  # ~WinAPI
    INFINITE = INVALID_DWORD_VALUE

    LOGON_WITH_PROFILE = 0x00000001

    STD_INPUT_HANDLE = wintypes.DWORD(-10).value
    STD_OUTPUT_HANDLE = wintypes.DWORD(-11).value
    STD_ERROR_HANDLE = wintypes.DWORD(-12).value

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = (('nLength', wintypes.DWORD),
                    ('lpSecurityDescriptor', wintypes.LPVOID),
                    ('bInheritHandle', wintypes.BOOL))

        def __init__(self, **kwds):
            self.nLength = ctypes.sizeof(self)
            super(SECURITY_ATTRIBUTES, self).__init__(**kwds)

    LPSECURITY_ATTRIBUTES = ctypes.POINTER(SECURITY_ATTRIBUTES)
    LPBYTE = ctypes.POINTER(wintypes.BYTE)
    LPHANDLE = PHANDLE = ctypes.POINTER(ctypes.c_void_p)
    LPDWORD = ctypes.POINTER(ctypes.c_ulong)

    class STARTUPINFO(ctypes.Structure):
        """https://msdn.microsoft.com/en-us/library/ms686331"""
        _fields_ = (('cb', wintypes.DWORD),
                    ('lpReserved', wintypes.LPWSTR),
                    ('lpDesktop', wintypes.LPWSTR),
                    ('lpTitle', wintypes.LPWSTR),
                    ('dwX', wintypes.DWORD),
                    ('dwY', wintypes.DWORD),
                    ('dwXSize', wintypes.DWORD),
                    ('dwYSize', wintypes.DWORD),
                    ('dwXCountChars', wintypes.DWORD),
                    ('dwYCountChars', wintypes.DWORD),
                    ('dwFillAttribute', wintypes.DWORD),
                    ('dwFlags', wintypes.DWORD),
                    ('wShowWindow', wintypes.WORD),
                    ('cbReserved2', wintypes.WORD),
                    ('lpReserved2', LPBYTE),
                    ('hStdInput', wintypes.HANDLE),
                    ('hStdOutput', wintypes.HANDLE),
                    ('hStdError', wintypes.HANDLE))

        def __init__(self, **kwds):
            self.cb = ctypes.sizeof(self)
            super(STARTUPINFO, self).__init__(**kwds)

    if HAS_WIN32:
        LPSTARTUPINFO = ctypes.POINTER(STARTUPINFO)

    class PROC_THREAD_ATTRIBUTE_LIST(ctypes.Structure):
        pass

    PPROC_THREAD_ATTRIBUTE_LIST = ctypes.POINTER(PROC_THREAD_ATTRIBUTE_LIST)

    class STARTUPINFOEX(STARTUPINFO):
        _fields_ = (('lpAttributeList', PPROC_THREAD_ATTRIBUTE_LIST),)

    LPSTARTUPINFOEX = ctypes.POINTER(STARTUPINFOEX)

    class PROCESS_INFORMATION(ctypes.Structure):
        """https://msdn.microsoft.com/en-us/library/ms684873"""
        _fields_ = (('hProcess', wintypes.HANDLE),
                    ('hThread', wintypes.HANDLE),
                    ('dwProcessId', wintypes.DWORD),
                    ('dwThreadId', wintypes.DWORD))

    LPPROCESS_INFORMATION = ctypes.POINTER(PROCESS_INFORMATION)

    class HANDLE_IHV(wintypes.HANDLE):
        pass

    def errcheck_ihv(result, func, args):
        if result.value == INVALID_HANDLE_VALUE:
            raise ctypes.WinError()
        return result.value

    class DWORD_IDV(wintypes.DWORD):
        pass

    def errcheck_idv(result, func, args):
        if result.value == INVALID_DWORD_VALUE:
            raise ctypes.WinError()
        return result.value

    def errcheck_bool(result, func, args):
        if not result:
            raise ctypes.WinError()
        return args

    def _win(func, restype, *argtypes):
        func.restype = restype
        func.argtypes = argtypes
        if issubclass(restype, HANDLE_IHV):
            func.errcheck = errcheck_ihv
        elif issubclass(restype, DWORD_IDV):
            func.errcheck = errcheck_idv
        else:
            func.errcheck = errcheck_bool

    # https://msdn.microsoft.com/en-us/library/ms687032
    _win(kernel32.WaitForSingleObject, DWORD_IDV,
        wintypes.HANDLE,  # _In_ hHandle
        wintypes.DWORD)   # _In_ dwMilliseconds

    # https://msdn.microsoft.com/en-us/library/ms683231
    _win(kernel32.GetStdHandle, HANDLE_IHV,
        wintypes.DWORD)  # _In_ nStdHandle

    # https://msdn.microsoft.com/en-us/library/ms724211
    _win(kernel32.CloseHandle, wintypes.BOOL,
        wintypes.HANDLE)  # _In_ hObject

    # https://msdn.microsoft.com/en-us/library/ms724935
    _win(kernel32.SetHandleInformation, wintypes.BOOL,
        wintypes.HANDLE,  # _In_ hObject
        wintypes.DWORD,   # _In_ dwMask
        wintypes.DWORD)   # _In_ dwFlags

    # https://msdn.microsoft.com/en-us/library/ms724251
    _win(kernel32.DuplicateHandle, wintypes.BOOL,
        wintypes.HANDLE,  # _In_  hSourceProcessHandle,
        wintypes.HANDLE,  # _In_  hSourceHandle,
        wintypes.HANDLE,  # _In_  hTargetProcessHandle,
        LPHANDLE,         # _Out_ lpTargetHandle,
        wintypes.DWORD,   # _In_  dwDesiredAccess,
        wintypes.BOOL,    # _In_  bInheritHandle,
        wintypes.DWORD)   # _In_  dwOptions

    # https://msdn.microsoft.com/en-us/library/ms683179
    _win(kernel32.GetCurrentProcess, wintypes.HANDLE)

    # https://msdn.microsoft.com/en-us/library/ms683189
    _win(kernel32.GetExitCodeProcess, wintypes.BOOL,
        wintypes.HANDLE,  # _In_  hProcess,
        LPDWORD)          # _Out_ lpExitCode

    # https://msdn.microsoft.com/en-us/library/aa365152
    _win(kernel32.CreatePipe, wintypes.BOOL,
        PHANDLE,                # _Out_    hReadPipe,
        PHANDLE,                # _Out_    hWritePipe,
        LPSECURITY_ATTRIBUTES,  # _In_opt_ lpPipeAttributes,
        wintypes.DWORD)         # _In_     nSize

    # https://msdn.microsoft.com/en-us/library/ms682431
    _win(advapi32.CreateProcessWithLogonW, wintypes.BOOL,
        wintypes.LPCWSTR,       # _In_        lpUsername
        wintypes.LPCWSTR,       # _In_opt_    lpDomain
        wintypes.LPCWSTR,       # _In_        lpPassword
        wintypes.DWORD,         # _In_        dwLogonFlags
        wintypes.LPCWSTR,       # _In_opt_    lpApplicationName
        wintypes.LPWSTR,        # _Inout_opt_ lpCommandLine
        wintypes.DWORD,         # _In_        dwCreationFlags
        wintypes.LPCWSTR,       # _In_opt_    lpEnvironment
        wintypes.LPCWSTR,       # _In_opt_    lpCurrentDirectory
        LPSTARTUPINFO,          # _In_        lpStartupInfo
        LPPROCESS_INFORMATION)  # _Out_       lpProcessInformation

    # High-level wrappers
    def DuplicateHandle(hsrc=kernel32.GetCurrentProcess(),
                        srchandle=kernel32.GetCurrentProcess(),
                        htgt=kernel32.GetCurrentProcess(),
                        access=0, inherit=False,
                        options=win32con.DUPLICATE_SAME_ACCESS):
        tgthandle = wintypes.HANDLE()
        kernel32.DuplicateHandle(hsrc, srchandle,
                                 htgt, ctypes.byref(tgthandle),
                                 access, inherit, options)
        return tgthandle.value

    def CreatePipe(inherit_read=False, inherit_write=False):
        read, write = wintypes.HANDLE(), wintypes.HANDLE()
        kernel32.CreatePipe(ctypes.byref(read), ctypes.byref(write), None, 0)
        if inherit_read:
            kernel32.SetHandleInformation(read, win32con.HANDLE_FLAG_INHERIT,
                                          win32con.HANDLE_FLAG_INHERIT)
        if inherit_write:
            kernel32.SetHandleInformation(write, win32con.HANDLE_FLAG_INHERIT,
                                          win32con.HANDLE_FLAG_INHERIT)
        return read.value, write.value

    def CreateProcessWithLogonW(username=None,
                                domain=None,
                                password=None,
                                logonflags=0,
                                applicationname=None,
                                commandline=None,
                                creationflags=0,
                                environment=None,
                                currentdirectory=None,
                                startupinfo=None):
        creationflags |= win32con.CREATE_UNICODE_ENVIRONMENT
        if commandline is not None:
            commandline = ctypes.create_unicode_buffer(commandline)
        if startupinfo is None:
            startupinfo = STARTUPINFO()
        process_info = PROCESS_INFORMATION()
        advapi32.CreateProcessWithLogonW(username,
                                         domain,
                                         password,
                                         logonflags,
                                         applicationname,
                                         commandline,
                                         creationflags,
                                         environment,
                                         currentdirectory,
                                         ctypes.byref(startupinfo),
                                         ctypes.byref(process_info))
        return process_info


def make_inheritable(token):
    return win32api.DuplicateHandle(win32api.GetCurrentProcess(),
                                    token,
                                    win32api.GetCurrentProcess(),
                                    0,
                                    1,
                                    win32con.DUPLICATE_SAME_ACCESS)


def runas_system(cmd, username, password):
    # This only works as system, when salt is running as a service for example

    # Check for a domain
    domain = '.'
    if '@' in username:
        username, domain = username.split('@')
    if '\\' in username:
        domain, username = username.split('\\')

    # Load User and Get Token
    token = win32security.LogonUser(username,
                                    domain,
                                    password,
                                    win32con.LOGON32_LOGON_INTERACTIVE,
                                    win32con.LOGON32_PROVIDER_DEFAULT)

    # Load the User Profile
    handle_reg = win32profile.LoadUserProfile(token, {'UserName': username})

    try:
        # Get Unrestricted Token (UAC) if this is an Admin Account
        elevated_token = win32security.GetTokenInformation(
            token, win32security.TokenLinkedToken)

        # Get list of privileges this token contains
        privileges = win32security.GetTokenInformation(
            elevated_token, win32security.TokenPrivileges)

        # Create a set of all privileges to be enabled
        enable_privs = set()
        for luid, flags in privileges:
            enable_privs.add((luid, win32con.SE_PRIVILEGE_ENABLED))

        # Enable the privileges
        win32security.AdjustTokenPrivileges(elevated_token, 0, enable_privs)

    except win32security.error as exc:
        # User doesn't have admin, use existing token
        if exc[0] == winerror.ERROR_NO_SUCH_LOGON_SESSION \
                or exc[0] == winerror.ERROR_PRIVILEGE_NOT_HELD:
            elevated_token = token
        else:
            raise

    # Get Security Attributes
    security_attributes = win32security.SECURITY_ATTRIBUTES()
    security_attributes.bInheritHandle = 1

    # Create a pipe to set as stdout in the child. The write handle needs to be
    # inheritable.
    stdin_read, stdin_write = win32pipe.CreatePipe(security_attributes, 0)
    stdin_read = make_inheritable(stdin_read)

    stdout_read, stdout_write = win32pipe.CreatePipe(security_attributes, 0)
    stdout_write = make_inheritable(stdout_write)

    stderr_read, stderr_write = win32pipe.CreatePipe(security_attributes, 0)
    stderr_write = make_inheritable(stderr_write)

    # Get startup info structure
    startup_info = win32process.STARTUPINFO()
    startup_info.dwFlags = win32con.STARTF_USESTDHANDLES
    startup_info.hStdInput = stdin_read
    startup_info.hStdOutput = stdout_write
    startup_info.hStdError = stderr_write

    # Get User Environment
    user_environment = win32profile.CreateEnvironmentBlock(token, False)

    # Build command
    cmd = 'cmd /c {0}'.format(cmd)

    # Run command and return process info structure
    procArgs = (None,
                cmd,
                security_attributes,
                security_attributes,
                1,
                0,
                user_environment,
                None,
                startup_info)

    hProcess, hThread, PId, TId = \
        win32process.CreateProcessAsUser(elevated_token, *procArgs)

    if stdin_read is not None:
        stdin_read.Close()
    if stdout_write is not None:
        stdout_write.Close()
    if stderr_write is not None:
        stderr_write.Close()
    hThread.Close()

    # Initialize ret and set first element
    ret = {'pid': PId}

    # Get Standard Out
    fd_out = msvcrt.open_osfhandle(stdout_read, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_out, 'r') as f_out:
        ret['stdout'] = f_out.read()

    # Get Standard Error
    fd_err = msvcrt.open_osfhandle(stderr_read, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_err, 'r') as f_err:
        ret['stderr'] = f_err.read()

    # Get Return Code
    if win32event.WaitForSingleObject(hProcess, win32event.INFINITE) == win32con.WAIT_OBJECT_0:
        exitcode = win32process.GetExitCodeProcess(hProcess)
        ret['retcode'] = exitcode

    # Close handle to process
    win32api.CloseHandle(hProcess)

    # Unload the User Profile
    win32profile.UnloadUserProfile(token, handle_reg)

    return ret


def runas(cmd, username, password, cwd=None):
    # This only works when not running under the system account
    # Debug mode for example
    if salt.utils.win_functions.get_current_user() == 'SYSTEM':
        return runas_system(cmd, username, password)

    # Create a pipe to set as stdout in the child. The write handle needs to be
    # inheritable.
    c2pread, c2pwrite = CreatePipe(inherit_read=False, inherit_write=True)
    errread, errwrite = CreatePipe(inherit_read=False, inherit_write=True)

    # Create inheritable copy of the stdin
    stdin = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    dupin = DuplicateHandle(srchandle=stdin, inherit=True)

    # Get startup info structure
    startup_info = STARTUPINFO(dwFlags=win32con.STARTF_USESTDHANDLES,
                               hStdInput=dupin,
                               hStdOutput=c2pwrite,
                               hStdError=errwrite)

    # Build command
    cmd = 'cmd /c {0}'.format(cmd)

    # Check for a domain
    domain = None
    if '@' in username:
        username, domain = username.split('@')
    if '\\' in username:
        domain, username = username.split('\\')

    # Run command and return process info structure
    process_info = CreateProcessWithLogonW(username=username,
                                           domain=domain,
                                           password=password,
                                           logonflags=LOGON_WITH_PROFILE,
                                           commandline=cmd,
                                           startupinfo=startup_info,
                                           currentdirectory=cwd)

    kernel32.CloseHandle(dupin)
    kernel32.CloseHandle(c2pwrite)
    kernel32.CloseHandle(errwrite)
    kernel32.CloseHandle(process_info.hThread)

    # Initialize ret and set first element
    ret = {'pid': process_info.dwProcessId}

    # Get Standard Out
    fd_out = msvcrt.open_osfhandle(c2pread, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_out, 'r') as f_out:
        ret['stdout'] = f_out.read()

    # Get Standard Error
    fd_err = msvcrt.open_osfhandle(errread, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_err, 'r') as f_err:
        ret['stderr'] = f_err.read()

    # Get Return Code
    if kernel32.WaitForSingleObject(process_info.hProcess, INFINITE) == \
            win32con.WAIT_OBJECT_0:
        exitcode = wintypes.DWORD()
        kernel32.GetExitCodeProcess(process_info.hProcess,
                                    ctypes.byref(exitcode))
        ret['retcode'] = exitcode.value

    # Close handle to process
    kernel32.CloseHandle(process_info.hProcess)

    return ret
