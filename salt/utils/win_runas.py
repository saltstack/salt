"""
Run processes as a different user in Windows
"""

# Import Python Libraries
import ctypes
import logging
import os
import time

from salt.exceptions import CommandExecutionError, TimedProcTimeoutError

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
    import winerror

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


def close_handle(handle):
    """
    Tries to close an object handle
    """
    if handle is not None:
        try:
            win32api.CloseHandle(handle)
        except pywintypes.error as exc:
            if exc.winerror != winerror.ERROR_INVALID_HANDLE:
                raise


def split_username(username):
    """
    Splits out the username from the domain name and returns both.
    """
    domain = "."
    user_name = username
    if "@" in username:
        user_name, domain = username.split("@")
    if "\\" in username:
        domain, user_name = username.split("\\")
    return user_name, domain


def create_env(user_token, inherit, timeout=1):
    """
    CreateEnvironmentBlock might fail when we close a login session and then
    try to re-open one very quickly. Run the method multiple times to work
    around the async nature of logoffs.
    """
    start = time.time()
    env = None
    exc = None
    while True:
        try:
            env = win32profile.CreateEnvironmentBlock(user_token, False)
        except pywintypes.error as exc:
            pass
        else:
            break
        if time.time() - start > timeout:
            break
    if env is not None:
        return env
    if exc is not None:
        raise exc


def create_default_env(username):
    """
    Creates an environment with default values.
    """
    result = {}

    systemdrive = os.environ.get("SystemDrive", r"C:")
    defaults = {
        "ALLUSERSPROFILE": r"C:\ProgramData",
        "CommonProgramFiles": r"C:\Program Files\Common Files",
        "CommonProgramFiles(x86)": r"C:\Program Files (x86)\Common Files",
        "CommonProgramW6432": r"C:\Program Files\Common Files",
        "ComputerName": None,
        "ComSpec": r"C:\Windows\system32\cmd.exe",
        "DriverData": r"C:\Windows\System32\Drivers\DriverData",
        "NUMBER_OF_PROCESSORS": None,
        "OS": None,
        "Path": r"C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0"
        "\\",
        "PATHEXT": r".COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC",
        "PROCESSOR_ARCHITECTURE": None,
        "PROCESSOR_IDENTIFIER": None,
        "PROCESSOR_LEVEL": None,
        "PROCESSOR_REVISION": None,
        "ProgramData": r"C:\ProgramData",
        "ProgramFiles": r"C:\Program Files",
        "ProgramFiles(x86)": r"C:\Program Files (x86)",
        "ProgramW6432": r"C:\Program Files",
        "PROMPT": r"$P$G",
        "PSModulePath": r"%ProgramFiles%\WindowsPowerShell\Modules;%SystemRoot%\system32\WindowsPowerShell\v1.0\Modules",
        "PUBLIC": r"C:\Users\Public",
        "SystemDrive": systemdrive,
        "SystemRoot": r"C:\Windows",
        "USERDOMAIN": None,
        "windir": r"C:\Windows",
    }
    user_specific = {
        "APPDATA": rf"{systemdrive}\Users\{username}\AppData\Roaming",
        "HOMEDRIVE": systemdrive,
        "HOMEPATH": rf"\Users\{username}",
        "LOCALAPPDATA": rf"{systemdrive}\Users\{username}\AppData\Local",
        "TEMP": rf"{systemdrive}\Users\{username}\AppData\Local\Temp",
        "TMP": rf"{systemdrive}\Users\{username}\AppData\Local\Temp",
        "USERNAME": rf"{username}",
        "USERPROFILE": rf"{systemdrive}\Users\{username}",
    }
    # set default variables based on the current user
    for key, val in defaults.items():
        item = os.environ.get(key, val)
        if key is not None:
            result.update({key: item})
    # set user specific variables
    result.update(user_specific)
    return result


def runas(cmd, username, password=None, **kwargs):
    """
    Run a command as another user. If the process is running as an admin or
    system account this method does not require a password. Other non
    privileged accounts need to provide a password for the user to runas.
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
    salt.platform.win.elevate_token(th)

    # Try to impersonate the SYSTEM user. This process needs to be running as a
    # user who as been granted the SeImpersonatePrivilege, Administrator
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

    # Impersonation of the SYSTEM user failed. Fallback to an un-privileged
    # runas.
    if not impersonation_token:
        log.debug("No impersonation token, using unprivileged runas")
        return runas_unpriv(cmd, username, password, **kwargs)

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
        | win32process.CREATE_SUSPENDED
        | win32process.CREATE_UNICODE_ENVIRONMENT
    )

    flags = win32con.STARTF_USESHOWWINDOW | win32con.STARTF_USESTDHANDLES
    startup_args = {
        "dwFlags": flags,
        "hStdInput": stdin_read.handle,
        "hStdOutput": stdout_write.handle,
    }
    if kwargs.get("redirect_stderr", False):
        startup_args.update({"hStdError": stdout_write.handle})
    else:
        startup_args.update({"hStdError": stderr_write.handle})
    startup_info = salt.platform.win.STARTUPINFO(**startup_args)

    # Create the environment for the user
    env = create_env(user_token, False)
    if kwargs.get("env", {}):
        env.update(kwargs["env"])

    # Set an optional timeout
    timeout = kwargs.get("timeout", None)
    if timeout:
        timeout = timeout * 1000
    else:
        timeout = win32event.INFINITE

    wait = not kwargs.get("bg", False)

    hProcess = None
    hThread = None
    result = None
    ret = {}
    try:
        # Start the process in a suspended state.
        process_info = salt.platform.win.CreateProcessWithTokenW(
            int(user_token),
            logonflags=salt.platform.win.LOGON_WITH_PROFILE,
            applicationname=None,
            commandline=cmd,
            creationflags=creationflags,
            environment=env,
            currentdirectory=kwargs.get("cwd"),
            startupinfo=startup_info,
        )
        hProcess = process_info.hProcess
        hThread = process_info.hThread
        dwProcessId = process_info.dwProcessId

        # We don't use these so let's close the handle
        salt.platform.win.kernel32.CloseHandle(stdin_write.handle)
        salt.platform.win.kernel32.CloseHandle(stdout_write.handle)
        salt.platform.win.kernel32.CloseHandle(stderr_write.handle)

        ret = {"pid": dwProcessId}

        # Resume the process
        psutil.Process(dwProcessId).resume()

        if wait:
            # Wait for the process to exit and get its return code
            result = win32event.WaitForSingleObject(hProcess, timeout)
            if result == win32con.WAIT_TIMEOUT:
                win32process.TerminateProcess(hProcess, 1)
            if result == win32con.WAIT_OBJECT_0:
                exitcode = win32process.GetExitCodeProcess(hProcess)
                ret["retcode"] = exitcode

            # Read standard out
            fd_out = msvcrt.open_osfhandle(stdout_read.handle, os.O_RDONLY | os.O_TEXT)
            with os.fdopen(fd_out, "rb") as f_out:
                stdout = f_out.read()
                ret["stdout"] = stdout

            # Read standard error
            fd_err = msvcrt.open_osfhandle(stderr_read.handle, os.O_RDONLY | os.O_TEXT)
            with os.fdopen(fd_err, "rb") as f_err:
                stderr = f_err.read()
                ret["stderr"] = stderr
    finally:
        close_handle(hProcess)
        close_handle(hThread)
        close_handle(th)
        close_handle(user_token)
        if impersonation_token is not None:
            win32security.RevertToSelf()
        close_handle(impersonation_token)
        close_handle(stdin_read.handle)
        close_handle(stdout_read.handle)
        close_handle(stderr_read.handle)

    if result == win32con.WAIT_TIMEOUT:
        raise TimedProcTimeoutError(
            "{} : Timed out after {} seconds".format(cmd, kwargs["timeout"])
        )

    return ret


def runas_unpriv(cmd, username, password, **kwargs):
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

    # Create inheritable copy of the stdin
    stdin = salt.platform.win.kernel32.GetStdHandle(
        salt.platform.win.STD_INPUT_HANDLE,
    )
    stdin_read_handle = salt.platform.win.DuplicateHandle(srchandle=stdin, inherit=True)

    # Create a pipe to set as stdout in the child. The write handle needs to be
    # inheritable.
    stdout_read_handle, stdout_write_handle = salt.platform.win.CreatePipe(
        inherit_read=False,
        inherit_write=True,
    )
    stderr_read_handle, stderr_write_handle = salt.platform.win.CreatePipe(
        inherit_read=False,
        inherit_write=True,
    )

    # Run the process without showing a window.
    creationflags = (
        salt.platform.win.CREATE_NO_WINDOW
        | salt.platform.win.CREATE_UNICODE_ENVIRONMENT
    )

    # Get startup info structure
    flags = (
        salt.platform.win.STARTF_USESHOWWINDOW | salt.platform.win.STARTF_USESTDHANDLES
    )
    startup_args = {
        "dwFlags": flags,
        "hStdInput": stdin_read_handle,
        "hStdOutput": stdout_write_handle,
    }
    if kwargs.get("redirect_stderr", False):
        startup_args.update({"hStdError": stdout_write_handle})
    else:
        startup_args.update({"hStdError": stderr_write_handle})
    startup_info = salt.platform.win.STARTUPINFO(**startup_args)

    # Create the environment for the user
    env = kwargs.get("env", None)
    if env:
        # Unprivileged users won't be able to call CreateEnvironmentBlock.
        # Create an environment block with sane defaults instead
        env = create_default_env(username)
        env.update(kwargs["env"])
        env = salt.platform.win.environment_string(env)

    # Set an optional timeout
    timeout = kwargs.get("timeout", None)
    if timeout:
        timeout = timeout * 1000
    else:
        timeout = win32event.INFINITE

    wait = not kwargs.get("bg", False)

    hProcess = None
    hThread = None
    result = None
    ret = {}
    try:
        # Run command and return process info structure
        process_info = salt.platform.win.CreateProcessWithLogonW(
            username=username,
            domain=domain,
            password=password,
            logonflags=salt.platform.win.LOGON_WITH_PROFILE,
            applicationname=None,
            commandline=cmd,
            creationflags=creationflags,
            environment=env,
            currentdirectory=kwargs.get("cwd"),
            startupinfo=startup_info,
        )
        hProcess = process_info.hProcess
        hThread = process_info.hThread
        dwProcessId = process_info.dwProcessId

        # We don't use these so let's close the handle
        salt.platform.win.kernel32.CloseHandle(stdin_read_handle)
        salt.platform.win.kernel32.CloseHandle(stdout_write_handle)
        salt.platform.win.kernel32.CloseHandle(stderr_write_handle)

        ret = {"pid": dwProcessId}

        if wait:
            # Wait for the process to exit and get its return code
            result = salt.platform.win.kernel32.WaitForSingleObject(hProcess, timeout)
            if result == win32con.WAIT_TIMEOUT:
                salt.platform.win.kernel32.TerminateProcess(hProcess, 1)
            elif result == win32con.WAIT_OBJECT_0:
                exitcode = salt.platform.win.wintypes.DWORD()
                salt.platform.win.kernel32.GetExitCodeProcess(
                    hProcess, ctypes.byref(exitcode)
                )
                ret["retcode"] = exitcode.value

            # Read Standard out
            fd_out = msvcrt.open_osfhandle(stdout_read_handle, os.O_RDONLY | os.O_TEXT)
            with os.fdopen(fd_out, "rb") as f_out:
                stdout = f_out.read()
                ret["stdout"] = stdout

            # Read Standard error
            fd_err = msvcrt.open_osfhandle(stderr_read_handle, os.O_RDONLY | os.O_TEXT)
            with os.fdopen(fd_err, "rb") as f_err:
                stderr = f_err.read()
                ret["stderr"] = stderr
    finally:
        if hProcess is not None:
            salt.platform.win.kernel32.CloseHandle(hProcess)
        if hThread is not None:
            salt.platform.win.kernel32.CloseHandle(hThread)
        if not wait:
            salt.platform.win.kernel32.CloseHandle(stdout_read_handle)
            salt.platform.win.kernel32.CloseHandle(stderr_read_handle)

    if result == win32con.WAIT_TIMEOUT:
        raise TimedProcTimeoutError(
            "{} : Timed out after {} seconds".format(cmd, kwargs["timeout"])
        )

    return ret
