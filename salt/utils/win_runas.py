# -*- coding: utf-8 -*-
'''
Run processes as a different user in Windows
'''
from __future__ import absolute_import, unicode_literals

# Import Python Libraries
import os
import logging

# Import Third Party Libs
import psutil

try:
    import win32con
    import win32process
    import win32security
    import win32pipe
    import win32event
    import win32profile
    import msvcrt
    import salt.winutil
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


def split_username(username):
    # TODO: Is there a windows api for this?
    domain = '.'
    if '@' in username:
        username, domain = username.split('@')
    if '\\' in username:
        domain, username = username.split('\\')
    return username, domain


def runas(cmdLine, username, password=None, cwd=None, elevated=True):

    impersonation_token = salt.utils.winutil.impersonate_sid(
        salt.utils.winutil.SYSTEM_SID,
        session_id=0,
        privs=['SeTcbPrivilege'],
    )

    username, domain = split_username(username)
    sid, domain, sidType = win32security.LookupAccountName(domain, username)
    if domain == 'NT AUTHORITY':
        log.warn("Logon system account: %s", username)
        logonType = win32con.LOGON32_LOGON_SERVICE
        user_token = win32security.LogonUser(
            username,
            domain,
            '',
            win32con.LOGON32_LOGON_SERVICE,
            win32con.LOGON32_PROVIDER_DEFAULT,
        )
    elif password:
        log.warn("Logon user with password: %s")
        #user_token = salt.utils.winutil.logon_msv1(
        #    username, password, domain=domain,
        #).Token
        user_token = win32security.LogonUser(
            username,
            domain,
            password,
            win32con.LOGON32_LOGON_INTERACTIVE,
            win32con.LOGON32_PROVIDER_DEFAULT,
        )
    else:
        log.warn("Logon user without password: %s")
        user_token = salt.utils.winutil.logon_msv1_s4u(username).Token


    elevation_type = win32security.GetTokenInformation(
        user_token, win32security.TokenElevationType
    )
    if elevation_type > 1:
        user_token = win32security.GetTokenInformation(
            user_token,
            win32security.TokenLinkedToken
        )
        salt.utils.winutil.elevate_token(user_token)

    handle_reg = win32profile.LoadUserProfile(user_token, {'UserName': username})
    salt.utils.winutil.grant_winsta_and_desktop(user_token)

    security_attributes = win32security.SECURITY_ATTRIBUTES()
    security_attributes.bInheritHandle = 1

    stdin_read, stdin_write = win32pipe.CreatePipe(security_attributes, 0)
    stdin_read = salt.utils.winutil.make_inheritable(stdin_read)

    stdout_read, stdout_write = win32pipe.CreatePipe(security_attributes, 0)
    stdout_write = salt.utils.winutil.make_inheritable(stdout_write)

    stderr_read, stderr_write = win32pipe.CreatePipe(security_attributes, 0)
    stderr_write = salt.utils.winutil.make_inheritable(stderr_write)

    creationflags = (
        win32process.CREATE_NO_WINDOW |
        win32process.CREATE_NEW_CONSOLE |
        win32process.CREATE_SUSPENDED
    )

    startup_info = salt.utils.winutil.STARTUPINFO(
        dwFlags=win32con.STARTF_USESTDHANDLES,
        hStdInput = stdin_read.handle,
        hStdOutput = stdout_write.handle,
        hStdError = stderr_write.handle,
    )

    env = win32profile.CreateEnvironmentBlock(user_token, False)

    process_info = salt.utils.winutil.CreateProcessWithTokenW(
        int(user_token),
        logonflags=1,
        applicationname=None,
        commandline=cmdLine,
        currentdirectory=cwd,
        creationflags=creationflags,
        startupinfo=startup_info,
        environment=env,
    )

    hProcess = process_info.hProcess
    hThread = process_info.hThread
    dwProcessId = process_info.dwProcessId
    dwThreadId = process_info.dwThreadId

    salt.utils.winutil.kernel32.CloseHandle(stdin_write.handle)
    salt.utils.winutil.kernel32.CloseHandle(stdout_write.handle)
    salt.utils.winutil.kernel32.CloseHandle(stderr_write.handle)

    ret = {'pid': dwProcessId}
    psutil.Process(dwProcessId).resume()

    if win32event.WaitForSingleObject(hProcess, win32event.INFINITE) == win32con.WAIT_OBJECT_0:
        exitcode = win32process.GetExitCodeProcess(hProcess)
        ret['retcode'] = exitcode

    fd_out = msvcrt.open_osfhandle(stdout_read.handle, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_out, 'r') as f_out:
        stdout = f_out.read()
        ret['stdout'] = stdout

    fd_err = msvcrt.open_osfhandle(stderr_read.handle, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_err, 'r') as f_err:
        stderr = f_err.read()
        ret['stderr'] = stderr

    win32profile.UnloadUserProfile(user_token, handle_reg)
#    salt.utils.winutil.kernel32.CloseHandle(handle_reg)
    salt.utils.winutil.kernel32.CloseHandle(hProcess)
#    salt.utils.winutil.kernel32.CloseHandle(user_token)
    if impersonation_token:
        win32security.RevertToSelf()
#    salt.utils.winutil.kernel32.CloseHandle(impersonation_token)

    return ret
