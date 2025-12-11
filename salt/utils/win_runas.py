"""
Run processes as a different user in Windows
"""

# Import Python Libraries
import ctypes
import logging
import os
import subprocess
import time

import salt.platform.win
import salt.utils.path
from salt.exceptions import CommandExecutionError

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import msvcrt

    import pywintypes
    import win32api
    import win32con
    import win32event
    import win32pipe
    import win32process
    import win32profile
    import win32security

    import salt.platform.win

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


log = logging.getLogger(__name__)


# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    """
    Only load if Win32 Libraries are installed
    """
    if not HAS_WIN32 or not HAS_PSUTIL:
        return False, "This utility requires pywin32 and psutil"

    return "win_runas"


def split_username(username):
    """
    Splits out the username from the domain name and returns both.
    """
    domain = "."
    user_name = str(username)
    # Domain users with User Principal Name (UPN): user@DOMAIN
    if "@" in user_name:
        user_name, domain = user_name.split("@", maxsplit=1)
        domain = domain.removesuffix(".local")
    # Domain users with Down-Level Logon Name: DOMAIN\user
    if "\\" in user_name:
        domain, user_name = user_name.split("\\", maxsplit=1)
    return str(user_name), str(domain)


def create_env(username, user_token, inherit=False, timeout=1):
    """
    CreateEnvironmentBlock might fail when we close a login session and then
    try to re-open one very quickly. Run the method multiple times to work
    around the async nature of logoffs.
    """
    start = time.time()
    env = None
    exc = None
    profile_info_dict = {"UserName": username}
    try:
        profile_handle = win32profile.LoadUserProfile(user_token, profile_info_dict)
        while True:
            try:
                env = win32profile.CreateEnvironmentBlock(user_token, inherit)
                if env is not None:
                    break
            except pywintypes.error as exc:
                pass
            else:
                break
            if time.time() - start > timeout:
                break
    except (win32api.error, pywintypes.error) as e:
        msg = f"Failed to load user profile: {e}"
        raise CommandExecutionError(msg)

    try:
        win32profile.UnloadUserProfile(user_token, profile_handle)
    except (win32api.error, pywintypes.error) as e:
        msg = f"Failed to unload user profile: {e}"
        raise CommandExecutionError(msg)

    if env is not None:
        return env
    if exc is not None:
        raise exc


def runas(cmd, username, password=None, cwd=None):
    """
    Run a command as another user. If the process is running as an admin or
    system account, this method does not require a password. Other
    non-privileged accounts need to provide a password for the user to "runas".
    Commands are run in with the highest level privileges possible for the
    account provided.
    """
    # Sometimes this comes in as an int. LookupAccountName can't handle an int
    # Let's make it a string if it's anything other than a string
    if not isinstance(username, str):
        username = str(username)
    # Validate the domain and sid exist for the username
    try:
        _, domain, _ = win32security.LookupAccountName(None, username)
        username, _ = split_username(username)
    except pywintypes.error as exc:
        message = win32api.FormatMessage(exc.winerror).rstrip("\n")
        raise CommandExecutionError(message)

    # Elevate the token from the current process
    access = win32security.TOKEN_QUERY | win32security.TOKEN_ADJUST_PRIVILEGES
    th = win32security.OpenProcessToken(win32api.GetCurrentProcess(), access)
    import salt.platform.win

    salt.platform.win.elevate_token(th)

    # Try to impersonate the SYSTEM user. This process needs to be running as a
    # user who has been granted the SeImpersonatePrivilege, Administrator
    # accounts have this permission by default.
    try:
        impersonation_token = salt.platform.win.impersonate_sid(
            salt.platform.win.SYSTEM_SID,
            session_id=0,
            privs=["SeTcbPrivilege"],
        )
    except OSError:
        log.debug("Unable to impersonate SYSTEM user")
        impersonation_token = None
        win32api.CloseHandle(th)

    if isinstance(cmd, (list, tuple)):
        # CreateProcess parameter lpCommandLine must be a string.
        # Since it is called directly and not via the subprocess module,
        # the arguments must be processed manually.
        cmd = subprocess.list2cmdline(cmd)

    # Impersonation of the SYSTEM user failed. Fallback to an un-privileged
    # runas.
    if not impersonation_token:
        log.debug("No impersonation token, using unprivileged runas")
        return runas_unpriv(cmd, username, password, cwd)

    if domain == "NT AUTHORITY":
        # Logon as a system level account, SYSTEM, LOCAL SERVICE, or NETWORK
        # SERVICE.
        user_token = win32security.LogonUser(
            username,
            domain,
            "",
            win32con.LOGON32_LOGON_SERVICE,
            win32con.LOGON32_PROVIDER_DEFAULT,
        )
    elif password:
        # Login with a password.
        user_token = win32security.LogonUser(
            username,
            domain,
            password,
            win32con.LOGON32_LOGON_INTERACTIVE,
            win32con.LOGON32_PROVIDER_DEFAULT,
        )
    else:
        # Login without a password. This always returns an elevated token.
        user_token = salt.platform.win.logon_msv1_s4u(username).Token

    # Get a linked user token to elevate if needed
    elevation_type = win32security.GetTokenInformation(
        user_token, win32security.TokenElevationType
    )
    if elevation_type > 1:
        user_token = win32security.GetTokenInformation(
            user_token, win32security.TokenLinkedToken
        )

    # Elevate the user token
    salt.platform.win.elevate_token(user_token)

    # Make sure the user's token has access to a windows station and desktop
    salt.platform.win.grant_winsta_and_desktop(user_token)

    # Create pipes for standard in, out and error streams
    security_attributes = win32security.SECURITY_ATTRIBUTES()
    security_attributes.bInheritHandle = 1

    stdin_read, stdin_write = win32pipe.CreatePipe(security_attributes, 0)
    stdin_read = salt.platform.win.make_inheritable(stdin_read)

    stdout_read, stdout_write = win32pipe.CreatePipe(security_attributes, 0)
    stdout_write = salt.platform.win.make_inheritable(stdout_write)

    stderr_read, stderr_write = win32pipe.CreatePipe(security_attributes, 0)
    stderr_write = salt.platform.win.make_inheritable(stderr_write)

    # Run the process without showing a window.
    creationflags = (
        win32process.CREATE_NO_WINDOW
        | win32process.CREATE_NEW_CONSOLE
        | win32process.CREATE_SUSPENDED
    )

    flags = win32con.STARTF_USESTDHANDLES
    flags |= win32con.STARTF_USESHOWWINDOW
    startup_info = salt.platform.win.STARTUPINFO(
        dwFlags=flags,
        hStdInput=stdin_read.handle,
        hStdOutput=stdout_write.handle,
        hStdError=stderr_write.handle,
    )

    # Create the environment for the user
    env = create_env(username, user_token, inherit=False)
    application_name = None
    # TODO: Maybe it has something to do with applicationname
    # application_name = salt.utils.path.which("cmd.exe")
    # application_name = cmd
    # import salt.utils.args
    # if salt.utils.args.shlex_split(cmd)[0].endswith((".bat", "cmd", "cmd.exe")):
    #     application_name = salt.utils.path.which("cmd.exe")

    hProcess = None
    try:
        # Start the process in a suspended state.
        process_info = salt.platform.win.CreateProcessWithTokenW(
            int(user_token),
            logonflags=1,
            applicationname=application_name,
            commandline=cmd,
            currentdirectory=cwd,
            creationflags=creationflags,
            startupinfo=startup_info,
            environment=env,
        )

        hProcess = process_info.hProcess
        hThread = process_info.hThread
        dwProcessId = process_info.dwProcessId
        dwThreadId = process_info.dwThreadId

        # We don't use these, so let's close the handle
        salt.platform.win.kernel32.CloseHandle(stdin_write.handle)
        salt.platform.win.kernel32.CloseHandle(stdout_write.handle)
        salt.platform.win.kernel32.CloseHandle(stderr_write.handle)

        ret = {"pid": dwProcessId}
        # Resume the process
        psutil.Process(dwProcessId).resume()

        # Wait for the process to exit and get its return code.
        if (
            win32event.WaitForSingleObject(hProcess, win32event.INFINITE)
            == win32con.WAIT_OBJECT_0
        ):
            exitcode = win32process.GetExitCodeProcess(hProcess)
            ret["retcode"] = exitcode

        # Read standard out
        fd_out = msvcrt.open_osfhandle(stdout_read.handle, os.O_RDONLY | os.O_TEXT)
        with os.fdopen(fd_out, "r") as f_out:
            stdout = f_out.read()
            ret["stdout"] = stdout.strip()

        # Read standard error
        fd_err = msvcrt.open_osfhandle(stderr_read.handle, os.O_RDONLY | os.O_TEXT)
        with os.fdopen(fd_err, "r") as f_err:
            stderr = f_err.read()
            ret["stderr"] = stderr
    finally:
        if hProcess is not None:
            salt.platform.win.kernel32.CloseHandle(hProcess)
        win32api.CloseHandle(th)
        win32api.CloseHandle(user_token)
        if impersonation_token:
            win32security.RevertToSelf()
        win32api.CloseHandle(impersonation_token)

    return ret


def runas_unpriv(cmd, username, password, cwd=None):
    """
    Runas that works for non-privileged users
    """
    # Sometimes this comes in as an int. LookupAccountName can't handle an int
    # Let's make it a string if it's anything other than a string
    if not isinstance(username, str):
        username = str(username)
    # Validate the domain and sid exist for the username
    try:
        _, domain, _ = win32security.LookupAccountName(None, username)
        username, _ = split_username(username)
    except pywintypes.error as exc:
        message = win32api.FormatMessage(exc.winerror).rstrip("\n")
        raise CommandExecutionError(message)

    # Create a pipe to set as stdout in the child. The write handle needs to be
    # inheritable.
    c2pread, c2pwrite = salt.platform.win.CreatePipe(
        inherit_read=False,
        inherit_write=True,
    )
    errread, errwrite = salt.platform.win.CreatePipe(
        inherit_read=False,
        inherit_write=True,
    )

    # Create inheritable copy of the stdin
    stdin = salt.platform.win.kernel32.GetStdHandle(
        salt.platform.win.STD_INPUT_HANDLE,
    )
    dupin = salt.platform.win.DuplicateHandle(srchandle=stdin, inherit=True)

    # Get startup info structure
    flags = win32con.STARTF_USESTDHANDLES
    flags |= win32con.STARTF_USESHOWWINDOW
    startup_info = salt.platform.win.STARTUPINFO(
        dwFlags=flags,
        hStdInput=dupin,
        hStdOutput=c2pwrite,
        hStdError=errwrite,
    )

    try:
        # Run command and return process info structure
        process_info = salt.platform.win.CreateProcessWithLogonW(
            username=username,
            domain=domain,
            password=password,
            logonflags=salt.platform.win.LOGON_WITH_PROFILE,
            commandline=cmd,
            startupinfo=startup_info,
            currentdirectory=cwd,
        )
        salt.platform.win.kernel32.CloseHandle(process_info.hThread)
    finally:
        salt.platform.win.kernel32.CloseHandle(dupin)
        salt.platform.win.kernel32.CloseHandle(c2pwrite)
        salt.platform.win.kernel32.CloseHandle(errwrite)

    # Initialize ret and set first element
    ret = {"pid": process_info.dwProcessId}

    # Get Standard Out
    fd_out = msvcrt.open_osfhandle(c2pread, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_out, "r") as f_out:
        ret["stdout"] = f_out.read()

    # Get Standard Error
    fd_err = msvcrt.open_osfhandle(errread, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_err, "r") as f_err:
        ret["stderr"] = f_err.read()

    # Get Return Code
    if (
        salt.platform.win.kernel32.WaitForSingleObject(
            process_info.hProcess, win32event.INFINITE
        )
        == win32con.WAIT_OBJECT_0
    ):
        exitcode = salt.platform.win.wintypes.DWORD()
        salt.platform.win.kernel32.GetExitCodeProcess(
            process_info.hProcess, ctypes.byref(exitcode)
        )
        ret["retcode"] = exitcode.value

    # Close handle to process
    salt.platform.win.kernel32.CloseHandle(process_info.hProcess)

    return ret
